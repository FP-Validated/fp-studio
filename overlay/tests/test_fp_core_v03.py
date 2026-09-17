"""Real storage/validation/tool tests; renderer is explicitly replaced by a test double."""
import base64
import io
import json
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
import struct
import zlib
from coworker.fp.common import ConflictError, loads, dumps, valid_name, pointer_get
from coworker.fp.store import Store
from coworker.fp.research import validate_research, review_document, capture_file
from coworker.fp.rendering import RenderController, validate_artifacts
from coworker.fp import design
from coworker.tools.fp import fp_tools, write_targets


def rendered(title='example'):
    def chunk(tag,data):
        return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',32,16,8,6,0,0,0))+chunk(b'IDAT',zlib.compress((b'\x00'+b'\x00\x00\x00\xff'*32)*16))+chunk(b'IEND',b'')
    return {'ok':True,'svg':f'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="16"><title>{title}</title><path d="M0 0L1 1"/></svg>',
            'png_base64':base64.b64encode(png).decode(),'frame':{'width':32,'height':16},
            'audit':{'ok':True,'findings':[]},'renderer_fingerprint':'a'*64,'compiler':'EXPLICIT_TEST_DOUBLE'}

def acknowledge(input_json: str) -> str:
    """The design-rule digests a document requires. Every render in this suite passes the
    gate with REAL acknowledgements; the refusal paths live in test_fp_design_rules.py."""
    try:
        value=loads(input_json)
    except Exception:
        value={}
    return dumps({n:design.digest(n) for n in design.required(value if isinstance(value,dict) else {})})


@pytest.fixture
def tools(tmp_path,monkeypatch):
    monkeypatch.setattr(RenderController,'run',lambda self,value,workspace,**kw:rendered(value.get('title','x')))
    funcs={fn.__name__:fn for fn in fp_tools(tmp_path)}
    render=funcs['fp_render']

    def render_with_rules(input_json,expected_revision,expected_research_revision,design_rules='',**kw):
        return render(input_json,expected_revision,expected_research_revision,
                      design_rules or acknowledge(input_json),**kw)

    funcs['fp_render']=render_with_rules
    return funcs

def research(store, value=10):
    src=store.capture('https://example.test/report',f'Network A has value {value}.',{'kind':'local_file','origin':'transport','truncated':False})
    return {'brief':{'goal':'Explain comparison','audience':'Researchers','main_message':'A comparison','as_of':'2026-09-11'},
            'claims':[{'id':'a','statement':'Value of A','status':'supported','source_id':src['id'],
                       'excerpt':f'Network A has value {value}.','bindings':[{'pointer':'/content/0/value','value':value}]}],
            'open_questions':[],'decisions':['Keep source units']}

@pytest.mark.parametrize('name',['..','.', '../abc','a/b','/abs','','x'*65,'가','a\\b'])
def test_invalid_names(name):
    with pytest.raises(ValueError): valid_name(name)

@pytest.mark.parametrize('raw',['{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}','{"__proto__":{}}','{"a":9007199254740992}'])
def test_strict_json(raw):
    with pytest.raises(ValueError):loads(raw)

def test_nested_hash_material_preserved():
    assert dumps({'a':{'z':2,'b':1}})=='{"a":{"b":1,"z":2}}'
    assert dumps({'a':{'z':2}})!=dumps({'a':{'z':3}})

def test_deep_input_rejected():
    v=1
    for _ in range(66):v=[v]
    with pytest.raises(ValueError):dumps(v)

def test_json_pointer_typed_and_escaped():
    assert pointer_get({'a/b':[{'~x':'00123'}]},'/a~1b/0/~0x')=='00123'
    with pytest.raises(ValueError):pointer_get([1],'/01')

def test_render_cas_and_exact_restore(tools,tmp_path):
    a=tools['fp_render']('{"title":"A"}',0,0)
    b=tools['fp_render']('{"title":"B"}',1,0)
    assert (a['revision'],b['revision'])==(1,2)
    restored=tools['fp_restore'](1,2,0)
    db=Store(tmp_path)
    assert restored['revision']==3
    assert db.get('infographic',1)['svg']==db.get('infographic',3)['svg']
    assert db.get('infographic',1)['png']==db.get('infographic',3)['png']
    with pytest.raises(ConflictError):tools['fp_render']('{"title":"lost"}',1,0)
    assert db.current_revision('infographic')==3

def test_read_does_not_repair_without_write_tool(tools,tmp_path):
    tools['fp_render']('{"title":"A"}',0,0)
    p=tmp_path/'fp/infographic.png';p.write_bytes(b'corrupt')
    assert tools['fp_inspect']()['cache_error']
    assert p.read_bytes()==b'corrupt'
    tools['fp_repair']()
    assert p.read_bytes()==Store(tmp_path).get('infographic')['png']

def test_failed_render_preserves_head(tools,monkeypatch,tmp_path):
    tools['fp_render']('{"title":"A"}',0,0)
    before=(tmp_path/'fp/infographic.svg').read_bytes()
    def bad(*a,**k):raise RuntimeError('compile failed')
    monkeypatch.setattr(RenderController,'run',bad)
    with pytest.raises(RuntimeError):tools['fp_render']('{"title":"B"}',1,0)
    assert Store(tmp_path).current_revision('infographic')==1
    assert (tmp_path/'fp/infographic.svg').read_bytes()==before

def test_interruption_before_commit_is_not_a_revision(tmp_path):
    st=Store(tmp_path);r=rendered();svg,png=validate_artifacts(r)
    with pytest.raises(InterruptedError):st.commit('x',0,{},svg,png,r,0,cancelled=lambda:True)
    assert st.current_revision('x')==0

def test_two_writers_cannot_lose_revision(tmp_path):
    st=Store(tmp_path);r=rendered();svg,png=validate_artifacts(r)
    barrier=threading.Barrier(2)
    def put(i):
        barrier.wait()
        try:return st.commit('x',0,{'title':str(i)},svg,png,r,0)['revision']
        except ConflictError:return 'conflict'
    with ThreadPoolExecutor(2) as pool:result=list(pool.map(put,[1,2]))
    assert sorted(map(str,result))==['1','conflict']

def test_cache_failure_does_not_destroy_committed_bytes(tmp_path,monkeypatch):
    st=Store(tmp_path);r=rendered();svg,png=validate_artifacts(r)
    monkeypatch.setattr(st,'materialize',lambda *a,**k: (_ for _ in ()).throw(OSError('disk failure')))
    result=st.commit('x',0,{},svg,png,r,0)
    assert result['cache_error']=='disk failure'
    assert st.get('x')['svg']==svg
    Store(tmp_path).materialize('x')
    assert (tmp_path/'fp/x.png').read_bytes()==png

def test_research_update_conflict(tmp_path):
    st=Store(tmp_path);v=research(st)
    st.set_research('x',validate_research(v,st),0)
    with pytest.raises(ConflictError):st.set_research('x',v,0)

def test_source_snapshot_is_immutable(tmp_path):
    st=Store(tmp_path)
    one=st.capture('https://example.test','one',{'origin':'transport'})
    two=st.capture('https://example.test','two',{'origin':'transport'})
    assert one['id']!=two['id']
    assert st.source(one['id'])['text']=='one'

def test_search_snippet_or_invented_source_cannot_be_bound(tmp_path):
    st=Store(tmp_path);v=research(st)
    v['claims'][0]['source_id']='invented'
    with pytest.raises(ValueError):validate_research(v,st)

def test_nonverbatim_evidence_cannot_claim_supported(tmp_path):
    st=Store(tmp_path);v=research(st);v['claims'][0]['excerpt']='does not exist'
    with pytest.raises(ValueError):validate_research(v,st)

def test_evidence_is_what_the_user_handed_over(tmp_path):
    """There is no transport capture left to test: the web tools are not registered.

    Evidence kinds are the ones a user supplies - an attached image, a pasted structure,
    a granted file. A page the model found is not one of them.
    """
    st=Store(tmp_path)
    kinds={row.get('kind') for row in st.sources()}
    assert kinds <= {'image','structure','local_file'}
    from coworker.fp import research as research_mod
    assert not hasattr(research_mod,'capture_web_fetch')

def test_local_capture_cannot_read_other_root(tmp_path):
    st=Store(tmp_path/'work');outside=tmp_path/'secret';outside.write_text('private')
    with pytest.raises(ValueError):capture_file(st,str(outside))
    allowed=capture_file(st,str(outside),[{'path':str(tmp_path),'writable':False}])
    assert allowed['kind']=='local_file'

def test_symlink_workspace_storage_rejected(tmp_path):
    target=tmp_path/'outside';target.mkdir()
    workspace=tmp_path/'work';workspace.mkdir();(workspace/'.fpstudio').symlink_to(target,target_is_directory=True)
    with pytest.raises(ValueError):Store(workspace)

def test_output_symlink_not_followed(tools,tmp_path):
    outside=tmp_path/'outside';outside.write_text('must stay')
    (tmp_path/'fp').mkdir();(tmp_path/'fp/infographic.svg').symlink_to(outside)
    result=tools['fp_render']('{"title":"A"}',0,0)
    assert result['committed'] and not result['ok']
    assert outside.read_text()=='must stay'

def inspected(tools, name='infographic') -> str:
    """A full pass of the final design inspection fp_publish now demands.

    The gate itself — what happens when an id is missing, unanswered or signed against
    older rules — is tested in test_fp_final_gate.py; here it is just the price of
    publishing."""
    checklist=tools['fp_review'](name)['final_checklist']
    return dumps({'skills':checklist['skills'],
                  'checks':{item['id']:{'verdict':'pass'} for item in checklist['items']}})

def test_factual_publish_with_bindings(tools,tmp_path):
    st=Store(tmp_path);v=research(st)
    tools['fp_research'](json.dumps(v),0)
    tools['fp_render']('{"title":"A","content":[{"value":10}]}',0,1)
    assert tools['fp_review']()['ok']
    pub=tools['fp_publish'](1,1,inspected(tools))
    assert pub['ok']
    assert (tmp_path/pub['artifacts']['svg']).read_bytes()==st.get('infographic')['svg']
    assert (tmp_path/pub['artifacts']['sources']).is_file()

def test_factual_publish_blocks_changed_metric(tools,tmp_path):
    st=Store(tmp_path);tools['fp_research'](json.dumps(research(st)),0)
    tools['fp_render']('{"title":"A","content":[{"value":11}]}',0,1)
    result=tools['fp_publish'](1,1)
    assert not result['ok']
    assert any('stale value' in f for f in result['review']['failures'])

def test_factual_publish_blocks_uncovered_metric(tools,tmp_path):
    st=Store(tmp_path);tools['fp_research'](json.dumps(research(st)),0)
    tools['fp_render']('{"title":"A","content":[{"value":10},{"value":42}]}',0,1)
    assert any('Unbound numeric' in f for f in tools['fp_review']()['failures'])

@pytest.mark.parametrize('status',['unresolved','conflicted','assumption'])
def test_factual_publish_blocks_unresolved_claims(status,tools,tmp_path):
    v=research(Store(tmp_path));v['claims'][0]['status']=status
    tools['fp_research'](json.dumps(v),0);tools['fp_render']('{"title":"A","content":[{"value":10}]}',0,1)
    assert not tools['fp_review']()['ok']

def test_research_change_during_render_rejected(tools,tmp_path,monkeypatch):
    def render(*args,**kwargs):
        Store(tmp_path).set_research('infographic',{},0)
        return rendered()
    monkeypatch.setattr(RenderController,'run',render)
    with pytest.raises(ConflictError):tools['fp_render']('{"title":"A"}',0,0)
    assert Store(tmp_path).current_revision('infographic')==0

def test_runtime_upgrade_explicit(tools,monkeypatch):
    tools['fp_render']('{"title":"A"}',0,0)
    def render(*a,**k):r=rendered();r['renderer_fingerprint']='b'*64;return r
    monkeypatch.setattr(RenderController,'run',render)
    with pytest.raises(ValueError,match='changed'):tools['fp_render']('{"title":"A"}',1,0)
    assert tools['fp_render']('{"title":"A"}',1,0,runtime_upgrade=True)['revision']==2

@pytest.mark.parametrize('tag',['script','foreignObject','text','image'])
def test_unsafe_svg_rejected(tag):
    r=rendered();r['svg']=f'<svg xmlns="http://www.w3.org/2000/svg"><{tag}/></svg>'
    with pytest.raises(ValueError):validate_artifacts(r)

@pytest.mark.parametrize('content',['<path onclick="alert(1)"/>','<use href="https://evil.test"/>','<path fill="url(https://evil.test)"/>'])
def test_unsafe_svg_attributes(content):
    r=rendered();r['svg']='<svg xmlns="http://www.w3.org/2000/svg">'+content+'</svg>'
    with pytest.raises(ValueError):validate_artifacts(r)

def test_fake_png_header_rejected():
    r=rendered();r['png_base64']=base64.b64encode(b'\x89PNG\r\n\x1a\nFAKE').decode()
    with pytest.raises(ValueError):validate_artifacts(r)

def test_png_crc_and_dimension_rejected():
    r=rendered();png=bytearray(base64.b64decode(r['png_base64']));png[25]^=1;r['png_base64']=base64.b64encode(png).decode()
    with pytest.raises(ValueError):validate_artifacts(r)
    r=rendered();r['frame']['width']=33
    with pytest.raises(ValueError):validate_artifacts(r)

def test_failed_compiler_audit_rejected():
    r=rendered();r['audit']['ok']=False
    with pytest.raises(ValueError):validate_artifacts(r)

def test_export_namespace_cannot_collide_with_live_document_names(tools,tmp_path):
    st=Store(tmp_path)
    tools['fp_research'](json.dumps(research(st)),0)
    tools['fp_render']('{"title":"A","content":[{"value":10}]}',0,1)
    published=tools['fp_publish'](1,1,inspected(tools))
    path=tmp_path/published['artifacts']['svg'];before=path.read_bytes()
    tools['fp_render']('{"title":"different"}',0,0,name='infographic-r000001')
    assert path.read_bytes()==before
    assert path.parent==tmp_path/'fp/exports/infographic'

def test_publication_sources_pinned_to_research_revision(tools,tmp_path):
    st=Store(tmp_path);v=research(st)
    tools['fp_research'](json.dumps(v),0)
    tools['fp_render']('{"title":"A","content":[{"value":10}]}',0,1)
    first=tools['fp_publish'](1,1,inspected(tools))
    old=(tmp_path/first['artifacts']['sources']).read_bytes()
    v['decisions'].append('Rechecked against supplied context')
    tools['fp_research'](json.dumps(v),1)
    second=tools['fp_publish'](1,2,inspected(tools))
    assert first['artifacts']['sources']!=second['artifacts']['sources']
    assert (tmp_path/first['artifacts']['sources']).read_bytes()==old


def test_illustrative_final_requires_visible_note(tools,tmp_path):
    v={'brief':{'goal':'Explain idea','audience':'Team','main_message':'Example','mode':'illustrative'},'claims':[], 'decisions':[], 'open_questions':[]}
    tools['fp_research'](json.dumps(v),0)
    tools['fp_render']('{"title":"A","content":[{"value":10}]}',0,1)
    assert not tools['fp_review']()['ok']
    tools['fp_render']('{"title":"A","content":[{"value":10}],"note":"가상 예시 데이터"}',1,1)
    assert tools['fp_review']()['ok']
