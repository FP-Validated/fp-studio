"""MANDATORY Mac/package integration. Missing compiler/fonts/resvg fails, never skips.
No model credentials are used. This tests the actual pinned compiler, not a mock renderer.
"""
import json
import os
from coworker.fp import design
from coworker.fp.rendering import RenderController, validate_artifacts
from coworker.tools.fp import fp_tools
from coworker.fp.store import Store

def test_real_fp_compiler_to_svg_png_and_revision(tmp_path):
    assert os.environ.get('FP_STUDIO_TESTING')!='1'
    source={'title':'FP runtime verification','blocks':[{'kind':'text','text':'Actual compiler output. 실제 렌더링 검증.'}]}
    tools={t.__name__:t for t in fp_tools(tmp_path)}
    # The shipped design rules are part of the package under test: a bundle that cannot
    # serve them cannot render at all, so acknowledge them from the installed files.
    rules=json.dumps({n:design.digest(n) for n in design.required(source)})
    first=tools['fp_render'](json.dumps(source,ensure_ascii=False),0,0,rules)
    assert first['ok'] and first['committed']
    assert first['receipt']['compiler'].startswith('fp-kit/ecf6d9c0')
    a=Store(tmp_path).get('infographic')
    # Font identity is committed with the revision; the tool result stays small because
    # every tool result is replayed on each later model call.
    assert a['receipt']['fonts'] and 'fonts' not in first['receipt']
    assert b'<text' not in a['svg']
    second=tools['fp_render'](json.dumps(source,ensure_ascii=False),1,0,rules)
    b=Store(tmp_path).get('infographic')
    assert a['svg']==b['svg'] and a['png']==b['png']
    assert first['receipt']['renderer_fingerprint']==second['receipt']['renderer_fingerprint']
    assert (tmp_path/'fp/infographic.svg').read_bytes()==b['svg']
    assert (tmp_path/'fp/infographic.png').read_bytes()==b['png']
