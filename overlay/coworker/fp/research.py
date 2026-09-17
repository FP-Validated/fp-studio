"""Evidence receipts, editorial brief and mechanical publication checks.

A captured passage is evidence of what the fetch returned, NOT proof that a claim is
true. Source reliability, causation, aesthetics and endorsement remain review judgments.
"""
from __future__ import annotations
from functools import wraps
import json
from pathlib import Path
import re
from .common import dumps, pointer_get
from .store import Store


# A fetched page returned in full is not read once - it stays in the conversation and is
# re-sent on every later model call. Measured on a real session, page bodies were 17% of
# ~3.9M input tokens. The receipt keeps every byte (that is what provenance needs); the
# model gets the head and reads the rest, or searches it, with fp_source_text.
EXCERPT_CHARS = 4000


def capture_web_fetch(tool, workspace):
    if workspace is None:
        return tool
    @wraps(tool)
    def wrapped(*args, **kwargs):
        result = tool(*args, **kwargs)
        if not isinstance(result, dict) or result.get('error') or not result.get('text'):
            return result
        out = dict(result)
        text = result['text']
        try:
            receipt = Store(workspace).capture(
                str(result.get('url') or kwargs.get('url') or (args[0] if args else '')),
                text,
                {'kind':'web_fetch', 'content_type':result.get('content_type'),
                 'truncated':bool(result.get('truncated')), 'origin':'transport'})
            out['fp_evidence'] = receipt
            # Only shorten what is recoverable: with no receipt, this text is the only copy.
            if len(text) > EXCERPT_CHARS:
                out['text'] = text[:EXCERPT_CHARS]
                out['fp_excerpt'] = {
                    'source_id': receipt['id'], 'returned_chars': EXCERPT_CHARS,
                    'total_chars': len(text),
                    'read': "The full captured text is stored: fp_source_text(source_id, "
                            "find='…') searches it, or (source_id, offset=…) pages it. "
                            'Quote from there, not from memory.'}
        except (OSError,ValueError) as e:
            out['fp_evidence_error'] = str(e)[:300]
        return out
    # wraps carries upstream tool name, explicit JSON schema and metadata, retaining
    # web_fetch's EGRESS risk and the original URL/address guard.
    return wrapped


def capture_file(store: Store, path: str, roots=None):
    """Only explicitly granted readable roots; caller never chooses its own grants."""
    p = Path(path).expanduser()
    p = (store.root / p).resolve() if not p.is_absolute() else p.resolve()
    allowed = [store.root]
    for r in roots or []:
        rp = r.get('path') if isinstance(r,dict) else getattr(r,'path',r)
        allowed.append(Path(rp).expanduser().resolve())
    if not any(p.is_relative_to(r) for r in allowed):
        raise ValueError("Source is outside the session's granted roots")
    if not p.is_file() or p.stat().st_size > 1024*1024:
        raise ValueError("Source must be a UTF-8 text/CSV/JSON/Markdown file of at most 1 MiB")
    text = p.read_text('utf-8')
    return store.capture(str(p),text,{'kind':'local_file','origin':'transport','truncated':False})


def validate_research(value: dict, store: Store) -> dict:
    if not isinstance(value,dict) or set(value) - {'brief','claims','decisions','open_questions'}:
        raise ValueError("Research accepts brief, claims, decisions and open_questions only")
    brief = value.get('brief',{})
    if not isinstance(brief,dict) or set(brief)-{'goal','audience','main_message','as_of','scope','mode'}:
        raise ValueError("Invalid editorial brief")
    if any(not isinstance(v,str) or len(v)>4000 for v in brief.values()):
        raise ValueError("Brief values must be bounded strings")
    if brief.get('mode','factual') not in {'factual','illustrative'}:
        raise ValueError("brief.mode must be factual or illustrative")
    for key in ('decisions','open_questions'):
        arr=value.get(key,[])
        if not isinstance(arr,list) or len(arr)>40 or any(not isinstance(s,str) or len(s)>2000 for s in arr):
            raise ValueError(f"Invalid {key}")
    claims=value.get('claims',[])
    if not isinstance(claims,list) or len(claims)>200:
        raise ValueError("At most 200 claims per research revision")
    ids=set()
    for claim in claims:
        if not isinstance(claim,dict) or set(claim)-{'id','statement','source_id','excerpt','bindings','status','note'}:
            raise ValueError("Invalid claim fields")
        cid=claim.get('id')
        if not isinstance(cid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',cid) or cid in ids:
            raise ValueError("Claims require unique stable IDs")
        ids.add(cid)
        if not isinstance(claim.get('statement'),str) or not 1<=len(claim['statement'])<=4000:
            raise ValueError("Claim statement is required")
        status=claim.get('status','unresolved')
        if status not in {'supported','unresolved','conflicted','assumption'}:
            raise ValueError("Invalid claim status")
        bindings=claim.get('bindings',[])
        if not isinstance(bindings,list) or len(bindings)>300:
            raise ValueError("Invalid claim bindings")
        for binding in bindings:
            if not isinstance(binding,dict) or set(binding)!={'pointer','value'} or not isinstance(binding['pointer'],str) or not binding['pointer'].startswith('/'):
                raise ValueError("Each binding requires pointer and exact typed value")
        if status=='supported':
            src=store.source(claim.get('source_id',''))
            excerpt=claim.get('excerpt','')
            if not isinstance(excerpt,str) or not 1<=len(excerpt)<=4000 or excerpt not in src['text']:
                raise ValueError(f"Claim {cid} has no verbatim passage in captured source")
    # Roundtrip severs all caller-held mutable references.
    return json.loads(dumps(value))


def data_numeric_paths(value, path='', in_data=False):
    """Find numeric payload leaves, excluding geometry/style. Coverage is not semantic proof."""
    if isinstance(value,dict):
        for k,v in value.items():
            if k in {'style','chartStyle','direction','options'}:
                continue
            esc=k.replace('~','~0').replace('/','~1')
            nested=in_data or k in {'content','data','value','values','amount','percentage'}
            yield from data_numeric_paths(v,path+'/'+esc,nested)
    elif isinstance(value,list):
        for i,v in enumerate(value):
            yield from data_numeric_paths(v,path+'/'+str(i),in_data)
    elif in_data and ((isinstance(value,(int,float)) and not isinstance(value,bool)) or
                      (isinstance(value,str) and bool(re.fullmatch(r'[$€₩]?[-+]?\d[\d,.]*(?:[%BKMbkm])?',value)))):
        yield path


def review_document(store: Store, name: str) -> dict:
    doc=store.get(name)
    research=store.research_current(name)
    failures=[]; warnings=[]; bound=set()
    if not doc:
        return {'ok':False,'failures':['No rendered revision'],'warnings':[]}
    val=research['value']; brief=val.get('brief',{})
    if not doc['receipt'].get('audit',{}).get('ok'):
        failures.append('Compiler audit has not passed')
    for key in ('goal','audience','main_message'):
        if not brief.get(key):
            failures.append(f'Editorial brief missing {key}')
    if val.get('open_questions'):
        failures.append('Unresolved research questions remain')
    illustrative=brief.get('mode')=='illustrative'
    if not illustrative and not val.get('claims'):
        failures.append('Factual output needs captured-source-backed claims')
    for claim in val.get('claims',[]):
        cid=claim['id']
        if claim.get('status')!='supported':
            if illustrative and claim.get('status')=='assumption':
                warnings.append(f'{cid}: illustrative assumption, not a factual result')
            else:
                failures.append(f'{cid}: {claim.get("status","unresolved")}')
        else:
            try:
                src=store.source(claim['source_id'])
                if claim.get('excerpt','') not in src['text']:
                    failures.append(f'{cid}: passage no longer matches evidence')
                if src.get('truncated'):
                    warnings.append(f'{cid}: captured page was truncated')
            except ValueError:
                failures.append(f'{cid}: missing evidence receipt')
        for binding in claim.get('bindings',[]):
            p=binding['pointer']
            try:
                if dumps(pointer_get(doc['input'],p)) != dumps(binding['value']):
                    failures.append(f'{cid}: stale value at {p}')
                else:
                    bound.add(p)
            except (KeyError,IndexError,TypeError,ValueError):
                failures.append(f'{cid}: missing binding {p}')
    if not illustrative:
        for p in sorted(set(data_numeric_paths(doc['input']))-bound):
            failures.append(f'Unbound numeric value: {p}')
    else:
        # The label has to be VISIBLE, not in one prescribed slot. Forcing it into the
        # footer note is what produced a sentence long enough to run under the brand
        # mark; a subtitle carries it better and the reader sees it sooner.
        label=' '.join(str(doc['input'].get(k,'')) for k in ('title','subtitle','note')).lower()
        if not any(w in label for w in ('illustrative','hypothetical','sample data','예시','가상','데모')):
            failures.append('Illustrative output must say so in the visible title, subtitle or note')
        warnings.append('Illustrative mode: not verified factual data')
    if not brief.get('as_of'):
        warnings.append('No explicit as-of date; check temporal relevance with the user')
    warnings.append('Mechanical checks do not prove source truth, semantic entailment or visual quality')
    return {'ok':not failures,'revision':doc['revision'],'research_revision':research['revision'],
            'failures':failures,'warnings':warnings,'sources':_used_sources(store,val.get('claims',[]))}


def _used_sources(store, claims):
    found=[]
    for sid in sorted({c['source_id'] for c in claims if c.get('source_id')}):
        try:
            item=store.source(sid);item.pop('text',None);found.append(item)
        except ValueError:
            continue
    return found
