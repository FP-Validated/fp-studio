"""Evidence receipts, editorial brief and mechanical publication checks.

A captured passage is evidence of what a source said, NOT proof that a claim is true.
Source reliability, causation, aesthetics and endorsement remain review judgments.

Evidence is what the user hands over: an attached image, a pasted structure, a granted
file. This product has no web research surface - a page the model found is not the source
the user asked for, and the failure it exists to prevent is a confident picture assembled
from somewhere else.
"""
from __future__ import annotations
import json
from pathlib import Path
import re
from .common import dumps, pointer_get
from .reference import fidelity_violations
from .store import Store


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
    # A REDRAW is judged against the source it transcribes. Its evidence is the captured
    # image or structure, which the render gate already resolved and the fidelity check
    # compares against - so demanding an editorial brief and captured claims here asks a
    # document that was told to do no research to invent some, and then reports every
    # value it faithfully copied as unbound.
    reproduce=isinstance(doc['input'].get('reference'),dict)
    if not doc['receipt'].get('audit',{}).get('ok'):
        failures.append('Compiler audit has not passed')
    if not reproduce:
        for key in ('goal','audience','main_message'):
            if not brief.get(key):
                failures.append(f'Editorial brief missing {key}')
    if val.get('open_questions'):
        failures.append('Unresolved research questions remain')
    illustrative=brief.get('mode')=='illustrative'
    if not illustrative and not reproduce and not val.get('claims'):
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
    if reproduce:
        # The decidable half of a redraw: same grammar, same blocks, same graph, no value
        # or label the transcription did not read from the source.
        failures.extend(fidelity_violations(doc['input']))
        warnings.append('Reproduce mode: checked against the transcription, not against '
                        'the source itself - hold the rendered PNG next to what the user supplied')
    elif illustrative:
        # The label has to be VISIBLE, not in one prescribed slot. Forcing it into the
        # footer note is what produced a sentence long enough to run under the brand
        # mark; a subtitle carries it better and the reader sees it sooner.
        label=' '.join(str(doc['input'].get(k,'')) for k in ('title','subtitle','note')).lower()
        if not any(w in label for w in ('illustrative','hypothetical','sample data','예시','가상','데모')):
            failures.append('Illustrative output must say so in the visible title, subtitle or note')
        warnings.append('Illustrative mode: not verified factual data')
    else:
        # `reference` is a copy of the source, not a measurement this document makes;
        # counting it reported every redrawn value twice.
        drawn={k:v for k,v in doc['input'].items() if k!='reference'}
        for p in sorted(set(data_numeric_paths(drawn))-bound):
            failures.append(f'Unbound numeric value: {p}')
    if not reproduce and not brief.get('as_of'):
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
