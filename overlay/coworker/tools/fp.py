"""Chat-native FP tools. Stock OpenWorker owns GUI, sessions, approvals and models."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from ..fp.common import ConflictError, atomic_write, checked_path, loads, pointer_get, valid_name
from ..fp import design, sdk
from ..fp.patch import apply_ops, outline
from ..fp.reference import capture_image
from ..fp import reference as reference_mode
from ..fp.research import capture_file, review_document, validate_research
from ..fp.rendering import RenderController, kit_root, validate_artifacts
from ..fp.store import Store

WRITE_TOOLS=frozenset({'fp_render','fp_edit','fp_restore','fp_research','fp_research_edit',
                       'fp_capture_source','fp_capture_image','fp_publish','fp_repair'})
# Tool results are replayed on every later model call, so a result carries what the next
# decision needs and a pointer to the rest - never an echo of the stored document.
SUMMARY_LIMITS={'claims':60,'sources':10,'findings':40,'statement':120,'brief':600,'note':200}
# The renderer's readback is the only cheap way to check a render, so it is generous -
# but it grows with the document, and an unbounded result is replayed on every later call.
LAYOUT_BUDGET=8000
LAYOUT_PART=1500


def write_targets(name: str) -> list[str]:
    valid_name(name)
    return ['.fpstudio',f'fp/{name}.svg',f'fp/{name}.png',f'fp/{name}.fp.json','fp']


def fp_tools(workspace: str | Path, roots=None) -> list:
    ws=Path(workspace).expanduser().resolve()
    store=Store(ws)
    controller=RenderController()
    # What THIS conversation has already been handed in full. The tool set is built once
    # per session and cached with it, so the closure's lifetime is the transcript's: a key
    # recorded here is provably still scrollable. The ledger used to live in the
    # workspace database, which outlives the conversation - a second chat on the same
    # project was told to "scroll back" to text it had never been sent.
    delivered: set[str]=set()

    def _clip(value,limit: int) -> str:
        text=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)
        return text if len(text)<=limit else text[:limit]+'…'

    def _sources_summary() -> dict:
        rows=store.sources()
        cap=SUMMARY_LIMITS['sources']
        return {'count':len(rows),
                'latest':[{'id':r.get('id'),'locator':_clip(r.get('locator',''),160),
                           'sha256':r.get('sha256'),'truncated':bool(r.get('truncated'))}
                          for r in rows[:cap]],
                'read':'fp_source_text(source_id, find=…) returns the captured text.'}

    def _research_summary(research: dict) -> dict:
        """Brief, claim status and binding counts - not the excerpts.

        Excerpts are verbatim passages of up to 4000 chars each and up to 200 claims;
        echoing them on every inspect was the single largest research cost. They stay in
        the store and are reachable with fp_source(pointer, doc='research')."""
        value=research.get('value') or {}
        claims=value.get('claims') or []
        cap=SUMMARY_LIMITS['claims']
        rows=[{'pointer':f'/claims/{i}','id':c.get('id'),
               'status':c.get('status','unresolved'),'source_id':c.get('source_id'),
               'bindings':len(c.get('bindings') or []),
               'statement':_clip(c.get('statement',''),SUMMARY_LIMITS['statement'])}
              for i,c in enumerate(claims[:cap])]
        out={'revision':research.get('revision',0),
             'brief':{k:_clip(v,SUMMARY_LIMITS['brief']) for k,v in (value.get('brief') or {}).items()},
             'claims':rows,
             'decisions':[_clip(s,SUMMARY_LIMITS['note']) for s in (value.get('decisions') or [])],
             'open_questions':[_clip(s,SUMMARY_LIMITS['note']) for s in (value.get('open_questions') or [])],
             'read':"fp_source(pointer, doc='research') for excerpts and bindings; "
                    'fp_research_edit(ops) to change them.'}
        if len(claims)>cap:
            out['claims_omitted']=len(claims)-cap
        return out

    def _review_summary(review: dict) -> dict:
        out={k:review.get(k) for k in ('ok','revision','research_revision')}
        cap=SUMMARY_LIMITS['findings']
        for key in ('failures','warnings'):
            items=review.get(key) or []
            out[key]=items[:cap]
            if len(items)>cap:
                out[key+'_omitted']=len(items)-cap
        out['source_ids']=[s.get('id') for s in review.get('sources') or []]
        return out

    def _review_brief(review: dict) -> dict:
        """What a WRITE result carries: what is wrong, once - not the standing advisory.

        Every write's review is replayed on every later call, so the invariant warnings
        and the one-line-per-pointer families (forty of them on a wide table) are paid
        for all turn. The findings stay, collapsed by family; fp_review serves the full
        list and the warnings when the document is being judged.
        """
        groups: dict[str,list[str]]={}
        order: list[str]=[]
        for item in review.get('failures') or []:
            head,_,tail=item.partition(': ')
            if head not in groups:
                groups[head]=[]
                order.append(head)
            groups[head].append(tail)
        lines: list[str]=[]
        for head in order:
            rest=groups[head]
            if len(rest)<3:
                lines.extend(f'{head}: {r}' if r else head for r in rest)
            else:
                lines.append(f'{head}: '+', '.join(rest[:3])+f' (+{len(rest)-3} more)')
        cap=SUMMARY_LIMITS['findings']
        out={k:review.get(k) for k in ('ok','revision','research_revision')}
        out['failures']=lines[:cap]
        if len(lines)>cap:
            out['failures_omitted']=len(lines)-cap
        out['warnings_count']=len(review.get('warnings') or [])
        out['read']='fp_review(name) lists every finding and warning in full.'
        return out

    def _gate(rules: dict) -> dict:
        """The gate's verdict. WHAT it checks is a constant, so say it once.

        `design_rules` names what governed this particular render and always rides along.
        The two lists below are the same sentences on every write; after the first one
        the transcript carries them, and repeating them is paid for on every later call.
        """
        out={'design_rules':rules['design_rules']}
        key='gate:'+'|'.join(rules['checked'])
        if key not in delivered:
            delivered.add(key)
            out['checked'],out['not_checked']=rules['checked'],rules['not_checked']
        return out

    def _layout(layout: Any,name: str) -> Any:
        """The renderer's readback, within a budget.

        This is how a render is checked without reading the SVG, so it is served in full
        whenever it fits. A wide document's readback can outgrow the document itself, and
        it is committed with the revision either way - so an oversized part is replaced by
        its size and the pointer that reads it.
        """
        if len(json.dumps(layout,ensure_ascii=False))<=LAYOUT_BUDGET or not isinstance(layout,dict):
            return layout
        out={}
        for key,part in layout.items():
            chars=len(json.dumps(part,ensure_ascii=False))
            out[key]=part if chars<=LAYOUT_PART else {'too_large':True,'chars':chars,'pointer':f'/{key}'}
        out['read']=(f"fp_source(pointer, doc='layout', name='{name}') reads a part of the "
                     'readback that did not fit.')
        return out

    def _appearance() -> dict:
        """What the conversation decided about light or dark, and the pack that follows."""
        record=store.appearance()
        if not record:
            return {'declared':False,
                    'ask':"ask_user(question='Light or dark?', options=['Dark','Light','Both'])"}
        mode=record['mode']
        return {'declared':mode,'theme':'fp-v1 or fp-v1-light' if mode=='both'
                else design.APPEARANCE_PACKS[mode]}

    def fp_inspect(name: str='infographic', include_source: bool=False) -> dict:
        """Read structure, brief, evidence and review before editing.

        Returns the OUTLINE (block pointers, kinds, counts), hashes and review - not the
        document. include_source=True returns the whole JSON; only a wholesale rewrite
        needs it.
        """
        current=store.get(name)
        research=store.research_current(name)
        refs=[{'source_id':r.get('id'),'kind':r.get('kind'),'form':r.get('form'),
               'locator':_clip(r.get('locator',''),160),'file':r.get('file'),
               'width':r.get('width'),'height':r.get('height'),'lines':r.get('lines')}
              for r in reference_mode.reference_sources(store)[:SUMMARY_LIMITS['sources']]]
        if not current:
            legacy=(ws/'.fpstudio'/valid_name(name)/'state.json').exists()
            return {'exists':False,'revision':0,'research':_research_summary(research),
                    'sources':_sources_summary(),'references':refs,'legacy_v02_detected':legacy,
                    'appearance':_appearance(),
                    # Say what this workspace HAS, so a name that missed is one call, not
                    # a guessing round per candidate.
                    'documents':store.names(),
                    'notice':'Import v0.2 history before editing this name.' if legacy
                             else ('Redraw the supplied source: transcribe it into reference and keep its grammar, structure, wiring and copy.'
                                   if refs else 'Compose from the user content; no template selection.')}
        artifacts={'svg':f'fp/{name}.svg','png':f'fp/{name}.png','source':f'fp/{name}.fp.json'}
        cache_error=None
        try:
            for ext in ('svg','png'):
                path=checked_path(ws,artifacts[ext])
                if not path.is_file() or path.read_bytes()!=current[ext]:
                    cache_error='Presentation cache is missing/stale; call fp_repair.'
        except (OSError,ValueError) as e:
            cache_error=str(e)
        value=current['input']
        receipt=current['receipt']
        out={'exists':True,'revision':current['revision'],
             'frame':{k:_clip(value[k],SUMMARY_LIMITS['statement']) for k in
                      ('title','subtitle','source','dateAsOf','note','theme','template') if k in value},
             'outline':outline(value),
             'source_sha256':receipt.get('source_sha256'),
             'receipt':{k:receipt.get(k) for k in ('compiler','renderer_fingerprint','audit','design_rules','status')},
             'references':refs,'reference':receipt.get('reference'),'appearance':_appearance(),
             # A committed revision can be unfaithful - the gate widens, or the revision
             # predates it - and then the only thing that says so is a human holding the
             # source next to the frame. One user did; the document claimed 100 where the
             # image said 146.
             **({'reference_drift':reference_mode.fidelity_violations(value)}
                if isinstance(value.get('reference'),dict) else {}),
             'artifacts':artifacts,'cache_error':cache_error,
             'review':_review_brief(review_document(store,name)),
             'read':'fp_source(pointer) reads a slice; fp_edit(ops) changes one.'}
        if include_source:
            out['input']=value
        return out

    def fp_source(pointer: str='', name: str='infographic', doc: str='source', limit: int=6000) -> dict:
        """Read ONE slice of the stored document, research or layout by JSON pointer.

        pointer '' is the root, '/blocks/2/rows' a branch. doc: 'source', 'research' or
        'layout' (the renderer's readback, when a part did not fit). A slice over `limit`
        chars returns its SHAPE (chars per child), so the next pointer can be narrower.
        """
        if doc not in ('source','research','layout'):
            raise ValueError("doc must be 'source', 'research' or 'layout'")
        stamp: dict={}
        if doc=='research':
            value=store.research_current(name)['value']
        else:
            current=store.get(name)
            if not current:
                raise ValueError('No rendered revision for this name')
            value=current['receipt'].get('layout') if doc=='layout' else current['input']
            # A readback belongs to the render that produced it, and the next write replaces
            # it. Name the revision so a pointer carried over from an earlier result is read
            # as the current readback, not mistaken for the one it was summarized from.
            if doc=='layout':
                stamp={'revision':current['revision']}
        # The root is '', and a model that reaches for '/' or a quoted '""' - both of
        # which happened, three wasted calls in one turn - means the same thing. Accept
        # them, and name the form in the refusal for anything else.
        pointer=(pointer or '').strip().strip('"\'')
        if pointer in ('', '/', '#'):
            pointer=''
        try:
            node=pointer_get(value,pointer) if pointer else value
        except (KeyError,IndexError,TypeError,ValueError):
            raise ValueError(f"No such path: {pointer} (the root is pointer='', a branch "
                             "is '/blocks/0')") from None
        limit=max(200,min(int(limit),20_000))
        body=json.dumps(node,ensure_ascii=False)
        if len(body)<=limit:
            return {'pointer':pointer,'doc':doc,**stamp,'value':node,'chars':len(body)}
        shape: Any
        if isinstance(node,dict):
            shape={k:len(json.dumps(v,ensure_ascii=False)) for k,v in node.items()}
        elif isinstance(node,list):
            shape=[{'pointer':f'{pointer}/{i}','kind':(v.get('kind') if isinstance(v,dict) else type(v).__name__),
                    'chars':len(json.dumps(v,ensure_ascii=False))} for i,v in enumerate(node[:60])]
        else:
            return {'pointer':pointer,'doc':doc,**stamp,'value':body[:limit],'chars':len(body),'clipped':True}
        return {'pointer':pointer,'doc':doc,**stamp,'chars':len(body),'too_large':True,
                'shape_chars_per_child':shape,
                'read':'Ask for a narrower pointer, or raise limit if you truly need it all.'}

    def fp_source_text(source_id: str, offset: int=0, limit: int=4000, find: str='') -> dict:
        """Read a window of a CAPTURED source's text, to quote a verbatim passage.

        A capture keeps every byte of what the user supplied. `find`
        returns the windows around each match - prefer it to paging.
        """
        record=store.source(source_id)
        text=record['text']
        limit=max(200,min(int(limit),8000))
        head={'id':record.get('id'),'locator':_clip(record.get('locator',''),300),
              'sha256':record.get('sha256'),'total_chars':len(text)}
        if find:
            if len(find)>200:
                raise ValueError('find is a short needle, not a passage')
            hits=[]
            start=0
            while len(hits)<5:
                at=text.find(find,start)
                if at<0:
                    break
                lo=max(0,at-limit//2)
                hits.append({'offset':lo,'text':text[lo:lo+limit]})
                start=at+max(1,len(find))
            return {**head,'find':find,'matches':len(hits),'windows':hits,
                    'notice':'Captured text is evidence of the fetch, not proof of the claim.'}
        offset=max(0,min(int(offset),len(text)))
        window=text[offset:offset+limit]
        return {**head,'offset':offset,'text':window,
                'next_offset':offset+len(window) if offset+len(window)<len(text) else None,
                'notice':'Captured text is evidence of the fetch, not proof of the claim.'}

    def _pointer(key: str, held: str) -> dict:
        """What a second request for an already delivered contract gets instead."""
        return {'served_earlier': True, 'holding': held,
                'read': 'This conversation already carries it in full; re-sending it '
                        'would be paid for on every later call. Scroll back. If a '
                        'compaction dropped it, ask again with again=True.'}

    def fp_guide(topic: str='vocabulary', name: str='', redraw: bool=False,
                 again: bool=False) -> dict:
        """Read the FP SDK authoring contracts, one grammar at a time.

        topics: vocabulary (catalog: id, intent, triggers, budget, styles; start here),
        draw (THE route, ONE call: `name`'s contracts - comma separated - the frame fields,
        every rule card and digest; redraw=True adds the reproduce rules), grammar, input,
        language. A contract already served returns a pointer; again=True forces the text.
        """
        if topic == 'vocabulary':
            payload = sdk.index()
        elif topic == 'draw':
            names = [n for n in (name or '').replace(',', ' ').split() if n]
            if not names:
                raise ValueError(
                    "fp_guide('draw') needs name='<grammar>[,<grammar>]'; call "
                    "fp_guide('vocabulary') for the ids."
                )
            document = {'blocks': [{'template': n} for n in names]}
            if redraw:
                document['reference'] = {}
            needed = design.required(document)
            key = 'draw:' + ','.join(sorted(names)) + (':redraw' if redraw else '')
            # Each piece is tracked on its own, so the second `draw` of the same grammar
            # (redraw first, then plain) re-sends only what this call adds. That call cost
            # 14,000 characters of already-delivered contract in a recorded turn.
            pieces = ({'input'} | {f'grammar:{n}' for n in names}
                      | {f'rules:{n}' for n in needed}
                      | ({'reproduce'} if redraw else set()))
            missing = pieces if again else pieces - delivered
            acknowledge = {n: design.digest(n) for n in needed}
            if not missing:
                return {'topic': topic, 'acknowledge': acknowledge,
                        'appearance': _appearance(),
                        **_pointer(key, f"the {', '.join(names)} contract, the frame "
                                        f"fields and {len(needed)} rule cards")}
            payload = {
                'acknowledge': acknowledge,
                # Light or dark is the user's, and this is the call before the render:
                # without it the model cannot tell a missing declaration from one it
                # already has, so it asks again - four times, in a recorded turn.
                'appearance': _appearance(),
                'next': 'Render with design_rules=<the acknowledge map>. No further '
                        'rule call is needed; fp_design_rules(kind, appendix=True) serves '
                        'a frame value or exact stroke behind a card when one is in doubt.',
            }
            if [n for n in names if f'grammar:{n}' in missing]:
                payload['grammars'] = [sdk.grammar(n) for n in names
                                       if f'grammar:{n}' in missing]
            if 'input' in missing:
                payload['input'] = sdk.input_contract()
            if [n for n in needed if f'rules:{n}' in missing]:
                payload['design_rules'] = [design.load(n) for n in needed
                                           if f'rules:{n}' in missing]
            if 'reproduce' in missing:
                # The shape of the transcription the render gate demands. Without it the
                # only way to learn it is to read another document's stored reference.
                payload['reproduce'] = reference_mode.CONTRACT
            held = sorted(pieces - missing)
            if held:
                payload['served_earlier'] = held
            delivered.update((key, *pieces))
        elif topic == 'grammar':
            if not name:
                raise ValueError(
                    "fp_guide('grammar') needs name=<id>; call fp_guide('vocabulary') "
                    "for the ids."
                )
            if not again and f'grammar:{name}' in delivered:
                return {'topic': topic, **_pointer(f'grammar:{name}',
                                                   f"the {name} contract")}
            payload = sdk.grammar(name)
            delivered.add(f'grammar:{name}')
        elif topic == 'input':
            if not again and 'input' in delivered:
                return {'topic': topic, **_pointer('input', 'the frame fields')}
            payload = sdk.input_contract()
            delivered.add('input')
        elif topic == 'language':
            if not again and 'language' in delivered:
                return {'topic': topic, **_pointer('language', 'the design tokens')}
            payload = {'content': sdk._read('docs/DESIGN-LANGUAGE.md')}
            delivered.add('language')
        else:
            raise ValueError(
                "Invalid guide topic. Use vocabulary, draw (with name), grammar (with "
                "name), input or language."
            )
        return {'topic': topic, **payload,
                'model': 'Compose freely from the contract. Grammars are vocabulary, not pre-made layouts.',
                'rules': 'Use published FP contracts; show early drafts; preserve facts; never execute agent-generated JS in the app.'}

    def fp_design_rules(kind: str='', appendix: bool=False, again: bool=False) -> dict:
        """Read the MANDATORY FOUR PILLARS design rules. Renders are refused without them.

        fp_guide('draw') already serves every card a document requires; a repeat returns a
        pointer (again=True forces it). appendix=True gives the verbatim frame arithmetic,
        fills, strokes and marker geometry behind a card. kind: fp-design-system (index),
        -table, -chart, -flowchart, -reproduce.
        """
        name=(kind or design.INDEX_SKILL).strip()
        if appendix:
            # The appendix is the larger half of a skill (9,113 characters for the table
            # rules), and a turn that re-read the same one paid for it twice.
            if not again and f'appendix:{name}' in delivered:
                return {'name':name,'digest':design.digest(name),'available':design.SKILLS,
                        **_pointer(f'appendix:{name}', f'the {name} appendix')}
            loaded=design.appendix(name)
            delivered.add(f'appendix:{name}')
        else:
            if not again and f'rules:{name}' in delivered:
                return {'name':name,'digest':design.digest(name),'available':design.SKILLS,
                        **_pointer(f'rules:{name}', f'the {name} card')}
            loaded=design.load(name)
            delivered.add(f'rules:{name}')
        return {**loaded,'available':design.SKILLS,
                'binding':'These rules are enforced, not advisory: fp_render rejects a '
                          'document whose design_rules omit a required skill, and '
                          'mechanically checks the type scale, palette binding and empty '
                          'frame fields. The remaining rules are on you.'}

    def fp_capture_source(path: str, name: str='infographic') -> dict:
        """Capture an already granted UTF-8 text/CSV/JSON file as a provenance receipt.

        Images to redraw go through fp_capture_image; attachments and pasted structures
        are captured already - fp_inspect lists them under `references`.
        """
        valid_name(name)
        return capture_file(store,path,roots)

    def fp_capture_image(path: str='', source_id: str='') -> dict:
        """Capture an image to REDRAW as a reference, and get the source id for it.

        Attachments and structures pasted in a message are captured already: call
        fp_inspect and use `references`. `path` captures an image file from a granted
        root; `source_id` re-reads an earlier capture. The id goes into the document's
        `reference.source_id`, and the receipt pins which source was redrawn.
        """
        if source_id:
            row=store.source(source_id)
            if row.get('kind')!='image':
                raise ValueError(f'{source_id} is not a captured image')
            return {k:v for k,v in row.items() if k!='text'}
        if not path:
            raise ValueError('Pass a path to an image file, or a source_id to re-read one')
        target=Path(path).expanduser()
        target=(ws/target).resolve() if not target.is_absolute() else target.resolve()
        allowed=[ws]+[Path((r.get('path') if isinstance(r,dict) else getattr(r,'path',r))).expanduser().resolve()
                      for r in roots or []]
        if not any(target.is_relative_to(root) for root in allowed):
            raise ValueError("Image is outside the session's granted roots")
        if not target.is_file():
            raise ValueError('No such image file')
        return capture_image(store,target.read_bytes(),str(target),origin='local_file')

    def fp_research(research_json: str, expected_research_revision: int, name: str='infographic') -> dict:
        """Write the FIRST research revision: brief, claims, decisions, open questions.

        JSON fields: brief {goal,audience,main_message,as_of,scope,mode}, claims
        [{id,statement,status,source_id,excerpt,bindings:[{pointer,value}],note}],
        decisions [text], open_questions [text]. status is supported/unresolved/
        conflicted/assumption; a supported claim quotes a passage from a captured
        receipt. Change it afterwards with fp_research_edit(ops).
        """
        valid_name(name)
        value=validate_research(loads(research_json),store)
        saved=store.set_research(name,value,expected_research_revision)
        return {'revision':saved['revision'],'research':_research_summary(saved)}

    def fp_render(input_json: str, expected_revision: int, expected_research_revision: int,
                  design_rules: str='', name: str='infographic', runtime_upgrade: bool=False) -> dict:
        """Render the FIRST revision or a wholesale rewrite; updates the stock viewer.

        input_json is the whole semantic document. Expected revisions are mandatory
        (CAS). design_rules is the {skill: digest} map
        fp_guide('draw') returns, and the document is mechanically checked against the
        decidable rules before anything is rendered.
        """
        value=loads(input_json)
        if not isinstance(value,dict):
            raise ValueError('FP input must be an object')
        return _render(value,expected_revision,expected_research_revision,design_rules,name,runtime_upgrade)

    def _render(value: dict, expected_revision, expected_research_revision, design_rules: str,
                name: str, runtime_upgrade: bool, applied=None) -> dict:
        """The one render/commit path, shared by a full render and a pointer edit.

        An edit is not a cheaper kind of write: it runs the same grammar check, the same
        mandatory design gate, the same revision CAS and the same compiler."""
        valid_name(name)
        # Light or dark first: the pack decides every colour in the frame, so a render
        # before the user has chosen one is a guess dressed as a result.
        design.appearance_gate(store.appearance(),value)
        # A grammar the kit does not serve is a typo or an invention; catch it before
        # the compiler does, and before a "rendered" claim.
        unknown=sdk.validate_templates(value)
        if unknown:
            raise ValueError('Unknown FP grammar: '+', '.join(unknown)+". Call fp_guide('vocabulary') for the available ids.")
        rules=design.enforce(value,loads(design_rules) if design_rules.strip() else None)
        # Reproduce mode: resolve the source this document claims to redraw BEFORE the
        # compiler runs - an unresolvable reference is a refusal, not a wasted render.
        redrawn=reference_mode.receipt(value,store)
        # And a source the user supplied is never silently ignored: transcribe it, or
        # say in the document why the user wanted something else.
        ignored=reference_mode.unconsumed(store,value)
        if ignored:
            raise ValueError(
                'The user supplied a source to redraw ('+', '.join(ignored[:4])+
                "). Reproduce it: fp_inspect lists it under `references`, transcribe it "
                'into `reference` {source_id, blocks} and keep its grammar, structure, '
                'wiring and copy. One document per source - a source another document '
                'already redrew is done. Researching a supplied source is not redrawing '
                "it. If the user asked for something else, quote them: "
                'referenceWaiver={"'+ignored[0]+'": "<what they said>"}.'
            )
        current=store.get(name)
        if not current and (ws/'.fpstudio'/name/'state.json').exists():
            raise ValueError('Legacy v0.2 document detected; import it before rendering')
        if type(expected_revision) is not int or (current['revision'] if current else 0)!=expected_revision:
            raise ConflictError('Stale document revision; fp_inspect again')
        if store.research_current(name)['revision']!=expected_research_revision:
            raise ConflictError('Stale research revision; fp_inspect again')
        result=controller.run(value,ws)
        svg,png=validate_artifacts(result)
        # A table cell may end in an ellipsis; a field in the frame's chrome may not. The
        # footer carries the user's own note, source and date, and the band now wraps and
        # stacks to fit them - so a cut there means the text genuinely does not fit the
        # frame, and truncating it silently would publish a half sentence as a fact.
        cut=[c for c in (result.get('layout') or {}).get('clipped') or []
             if isinstance(c,dict) and c.get('role')=='footer']
        if cut:
            raise ValueError(
                'The footer cannot hold this text: '+'; '.join(
                    f"{c.get('wanted','')!r} was cut to {c.get('shown','')!r}" for c in cut[:2])+
                '. The band wraps to two lines and stacks its entries, so this is longer '
                'than the frame can show. Shorten it, or move the explanation into the '
                'body where a paragraph belongs.'
            )
        fingerprint=result.get('renderer_fingerprint')
        if not isinstance(fingerprint,str) or len(fingerprint)!=64:
            raise ValueError('Renderer fingerprint missing')
        old=current['receipt'].get('renderer_fingerprint') if current else None
        if old and old!=fingerprint and not runtime_upgrade:
            was=(current['receipt'].get('theme') or {}).get('id') if current else None
            now=(result.get('theme') or {}).get('id')
            if was and now and was!=now:
                raise ValueError(
                    f"This document was drawn with theme='{was}'; rendering it as '{now}' "
                    'would replace it. A light version and a dark version are two '
                    f"artifacts: render the other one under its own name (name='...-{('light' if 'light' in now else 'dark')}')."
                )
            raise ValueError('Compiler/theme/fonts changed. Discuss the upgrade, then explicitly render with runtime_upgrade=true. Prior artifacts are preserved.')
        receipt={k:result.get(k) for k in ('compiler','renderer_fingerprint','input_hash','frame','audit','fonts','theme','layout')}
        # Which design rules (and which exact revision of them) governed this render.
        receipt['design_rules']={n:design.digest(n) for n in rules['design_rules']}
        if redrawn is not None:
            receipt['reference']=redrawn
        if old and old!=fingerprint:
            receipt['upgraded_from']=old
        state=store.commit(name,expected_revision,value,svg,png,receipt,expected_research_revision,
                           cancelled=controller.cancelled.is_set)
        # The full receipt (fonts, theme, frame geometry) is committed and readable through
        # fp_history; repeating it here would be paid for on every following model call.
        committed=state['receipt']
        out={'ok':state['cache_error'] is None,'revision':state['revision'],
             'cache_error':state['cache_error'],'committed':True,'name':name,**_gate(rules),
             'receipt':{k:committed.get(k) for k in
                        ('compiler','renderer_fingerprint','source_sha256','design_rules','reference','status')},
             'audit':committed.get('audit'),
             # What the renderer actually laid out. The delivered SVG is outlined glyphs -
             # no text nodes, every rect a path - so reading it answers nothing and costs
             # tens of thousands of tokens. This is the readback; the PNG is the picture.
             'layout':_layout(committed.get('layout'),name),
             '_display':{'fp_preview':{'path':f'fp/{name}.svg','revision':state['revision']}} if not state['cache_error'] else {},
             'artifacts':{'png':f'fp/{name}.png','svg':f'fp/{name}.svg (outlined glyphs; read the PNG, not this)'},
             'review':_review_brief(review_document(store,name)),
             'notice':'Draft rendered. Check `layout` against the source, then discuss the result with the user; do not claim final verification.'}
        if applied is not None:
            out['ops_applied']=applied
        return out

    def fp_edit(ops_json: str, expected_revision: int, expected_research_revision: int,
                design_rules: str='', name: str='infographic', runtime_upgrade: bool=False) -> dict:
        """Revise the stored document by JSON pointer and re-render. Default for any change.

        ops_json: [{"op":"set","pointer":"/blocks/2/rows/0/value","value":41.2}, …]. ops
        are set (key or list item), append, insert (before an index) and remove; every
        pointer must already resolve - check one with fp_source. Same gate as fp_render
        (grammar, design_rules, revision CAS, compiler); reuse the digests from
        fp_inspect's receipt.design_rules.
        """
        valid_name(name)
        current=store.get(name)
        if not current:
            raise ValueError('Nothing to edit yet; render the first draft with fp_render')
        ops=loads(ops_json)
        if type(expected_revision) is not int or current['revision']!=expected_revision:
            raise ConflictError('Stale document revision; fp_inspect again')
        value=apply_ops(current['input'],ops)
        return _render(value,expected_revision,expected_research_revision,design_rules,name,
                       runtime_upgrade,applied=[op.get('pointer','') for op in ops])

    def fp_research_edit(ops_json: str, expected_research_revision: int, name: str='infographic') -> dict:
        """Change the stored research by JSON pointer: brief, claims, decisions, questions.

        Same ops as fp_edit. The whole result is re-validated: a supported claim still
        needs a verbatim passage from a captured receipt.
        """
        valid_name(name)
        current=store.research_current(name)
        if type(expected_research_revision) is not int or current['revision']!=expected_research_revision:
            raise ConflictError('Stale research revision; fp_inspect again')
        ops=loads(ops_json)
        value=validate_research(apply_ops(current['value'] or {},ops),store)
        saved=store.set_research(name,value,expected_research_revision)
        return {'revision':saved['revision'],'ops_applied':[op.get('pointer','') for op in ops],
                'research':_research_summary(saved)}

    def fp_history(name: str='infographic') -> dict:
        """List the newest immutable revisions. Restore does not invoke a new renderer.

        One line per revision: fingerprints and hashes, not the stored font/theme/frame
        receipts.
        """
        rows=[]
        for r in store.history(name)[:40]:
            receipt=r.get('receipt') or {}
            rows.append({'revision':r['revision'],'created_at':r['created_at'],
                         'research_revision':r['research_revision'],'restored_from':r['restored_from'],
                         'status':receipt.get('status'),'compiler':receipt.get('compiler'),
                         'renderer_fingerprint':str(receipt.get('renderer_fingerprint') or '')[:12],
                         'source_sha256':str(receipt.get('source_sha256') or '')[:12],
                         'audit_ok':bool((receipt.get('audit') or {}).get('ok')),
                         'design_rules':sorted(receipt.get('design_rules') or {})})
        return {'name':name,'revisions':rows,
                'read':'fp_restore(revision) restores bytes; fp_source reads the current source.'}

    def fp_restore(revision: int, expected_revision: int, expected_research_revision: int,
                   name: str='infographic') -> dict:
        """Restore the exact stored SVG/PNG and source as a NEW revision, without re-render drift."""
        if type(revision) is not int or revision<1:
            raise ValueError('Revision must be a positive integer')
        old=store.get(name,revision)
        if not old:
            raise ValueError('Requested revision does not exist')
        result=store.commit(name,expected_revision,old['input'],old['svg'],old['png'],old['receipt'],
                            expected_research_revision,restored_from=revision)
        return {'ok':result['cache_error'] is None,'revision':result['revision'],
                'cache_error':result['cache_error'],'committed':True,'name':name,
                '_display':{'fp_preview':{'path':f'fp/{name}.svg','revision':result['revision']}} if not result['cache_error'] else {},
                'restored_from':revision,'artifacts':{'svg':f'fp/{name}.svg','png':f'fp/{name}.png'},
                'review':_review_brief(review_document(store,name))}

    def fp_review(name: str='infographic', checklist: bool=True, again: bool=False) -> dict:
        """Mechanical checks PLUS the design rules this document must be inspected against.

        `checklist` returns every Do / Do not line of the skills this document's grammars
        require, each with an id; fp_publish refuses until every id has a verdict. A
        checklist already served returns a pointer, digests and all; again=True forces
        it. Mechanical validation is not factual verification or a quality score.
        """
        out=_review_summary(review_document(store,name))
        if checklist:
            current=store.get(name)
            if not current:
                raise ValueError('Nothing to inspect yet; render a draft first')
            full=design.checklist(current['input'])
            # The rules, not the document, decide the key: the same grammars under the
            # same digests produce the identical twenty thousand characters, and the
            # second copy is carried by every call that follows it. A document that
            # gains a grammar - or a rule that is edited - is a different checklist.
            key='checklist:'+','.join(f'{n}@{d}' for n,d in sorted(full['skills'].items()))
            if not again and key in delivered:
                out['final_checklist']={'skills':full['skills'],'item_count':len(full['items']),
                                        **_pointer(key,f"{len(full['items'])} checklist items for "
                                                       +', '.join(sorted(full['skills'])))}
            else:
                delivered.add(key)
                out['final_checklist']=full
        return out

    def fp_publish(expected_revision: int, expected_research_revision: int,
                   final_checks: str='', name: str='infographic') -> dict:
        """Create the immutable SVG/PNG artifact links when the user asks for final files.

        final_checks is the inspection from fp_review's checklist:
        {"skills":{skill:digest},"checks":{"<id>":{"verdict":"pass"}, "<id>":
        {"verdict":"n/a","note":"no legend in this grammar"}}}. Every id must be answered.
        Also refuses unresolved or conflicting claims, stale numeric bindings and failed
        compiler checks. No external upload; aesthetic review stays in chat.
        """
        # Rendering one document per source is enough to keep drawing; delivery is where
        # a source the user handed over and nobody redrew becomes a broken promise.
        waiting=reference_mode.pending(store,(store.get(name) or {}).get('input'))
        if waiting:
            raise ValueError(
                'The user supplied '+str(len(waiting))+' source(s) nothing has redrawn ('
                +', '.join(waiting[:4])+"). Redraw each one, or quote the user's words "
                'in that document\'s referenceWaiver, before publishing.'
            )
        review=review_document(store,name)
        if review.get('revision')!=expected_revision or review.get('research_revision')!=expected_research_revision:
            raise ConflictError('Review snapshot differs from the requested publication revision')
        if not review['ok']:
            return {'ok':False,'review':_review_summary(review),'notice':'Continue research or revise the draft in this chat.'}
        inspection=design.check_final(store.get(name)['input'],
                                      loads(final_checks) if final_checks.strip() else None)
        artifacts=store.publish(name,expected_revision,expected_research_revision,review)
        report=f'fp/exports/{name}/r{expected_revision:06d}-e{expected_research_revision:06d}.sources.md'
        lines=['# Research and export receipt','',f'Visual revision: {expected_revision}',
               f'Research revision: {expected_research_revision}','','## Captured sources']
        for s in review['sources']:
            lines.extend(['','```text',s['locator'].replace('```','[backticks]'),'```',f'SHA-256 of captured text: `{s["sha256"]}`'])
        # A redraw's evidence is the source it transcribes, not a research claim. Without
        # this the receipt of a published redraw says "captured sources:" and nothing.
        redrawn=(store.get(name)['receipt'] or {}).get('reference')
        if isinstance(redrawn,dict):
            lines.extend(['','## Redrawn source',
                          f'- {redrawn.get("kind")} `{redrawn.get("source_id")}`: '
                          +str(redrawn.get('locator','')).replace('`','')[:200],
                          f'- SHA-256 of the captured source: `{redrawn.get("image_sha256") or redrawn.get("structure_sha256")}`',
                          '- Fidelity is checked against the transcription in `reference`, '
                          'not against the source itself.'])
        lines.extend(['','## Design inspection',
                      f'{inspection["inspected"]} rules inspected against the rendered artifact.',
                      *[f'- `{n}` @ `{d[:12]}`' for n,d in sorted(inspection['skills'].items())],
                      'Mechanical checks plus the agent\'s inspection; not a human design review.'])
        lines.extend(['','## Limitations',*['- '+x for x in review['warnings']]])
        atomic_write(checked_path(ws,report,create_parent=True),('\n'.join(lines)+'\n').encode('utf-8'))
        artifacts['sources']=report
        return {'ok':True,'revision':expected_revision,'artifacts':artifacts,
                'final_inspection':inspection,'review':_review_summary(review)}

    def fp_repair(name: str='infographic') -> dict:
        """Rebuild live artifact files from the committed database after an interrupted save."""
        return {'ok':True,'artifacts':store.materialize(name)}

    fp_render.__fp_interrupt__=controller.interrupt
    fp_edit.__fp_interrupt__=controller.interrupt
    funcs=[fp_inspect,fp_source,fp_source_text,fp_guide,fp_design_rules,fp_capture_source,
           fp_capture_image,fp_research,fp_research_edit,fp_render,fp_edit,fp_history,
           fp_restore,fp_review,fp_publish,fp_repair]
    return funcs
