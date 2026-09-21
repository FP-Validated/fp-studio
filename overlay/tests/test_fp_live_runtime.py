"""MANDATORY Mac/package integration. Missing compiler/fonts/resvg fails, never skips.
No model credentials are used. This tests the actual pinned compiler, not a mock renderer.
"""
import json
import os
import pytest
from coworker.fp import design
from coworker.fp.rendering import RenderController, validate_artifacts
from coworker.tools.fp import fp_tools
from coworker.fp.store import Store

def test_real_fp_compiler_to_svg_png_and_revision(tmp_path):
    assert os.environ.get('FP_STUDIO_TESTING')!='1'
    source={'title':'FP runtime verification','blocks':[{'kind':'text','text':'Actual compiler output. 실제 렌더링 검증.'}]}
    Store(tmp_path).set_appearance('dark', 'dark mode', 'message')
    tools={t.__name__:t for t in fp_tools(tmp_path)}
    # The shipped design rules are part of the package under test: a bundle that cannot
    # serve them cannot render at all, so acknowledge them from the installed files.
    rules=json.dumps({n:design.digest(n) for n in design.required(source)})
    first=tools['fp_render'](json.dumps(source,ensure_ascii=False),0,0,rules)
    assert first['ok'] and first['committed']
    assert first['receipt']['compiler'].startswith('fp-kit/17c89e7')
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


def test_the_paired_bar_grammar_reaches_the_real_compiler(tmp_path):
    """A source with two bars per row is drawable, and the route is the one the card names.

    Before this grammar existed, a redraw of a paired bar chart had nowhere to put the
    second series: the conversation that found it indexed one series to 100 and shipped
    seven identical bars.
    """
    assert os.environ.get('FP_STUDIO_TESTING') != '1'
    rows = [
        {'id': 'v', 'Measure': 'Validators', 'Group': 'VALIDATOR SET',
         'Oct 29, 2024': '146', 'Sep 15, 2026': '84', 'Change': '-42%'},
        {'id': 'p', 'Measure': 'APT price', 'Unit': 'USD', 'Group': 'VALIDATOR ECONOMICS',
         'Oct 29, 2024': '$9.50', 'Sep 15, 2026': '$0.58', 'Change': '-94%'},
    ]
    source = {'title': 'Aptos validator economics', 'source': 'Aptos Explorer',
              'colorMode': 'pair',
              'blocks': [{'kind': 'chart', 'template': 'bar', 'style': 'paired', 'rows': rows,
                          'fields': {'category': 'Measure', 'columns': ['Oct 29, 2024', 'Sep 15, 2026'],
                                     'unit': 'Unit', 'delta': 'Change', 'group': 'Group'}}]}
    Store(tmp_path).set_appearance('dark', 'dark mode', 'message')
    tools = {t.__name__: t for t in fp_tools(tmp_path)}
    guide = tools['fp_guide']('draw', 'bar', True)
    # The catalog tells the model this reading exists; it used to have to guess or grep.
    assert any(s['id'] == 'paired' for s in guide['grammars'][0]['styles'])
    out = tools['fp_render'](json.dumps(source, ensure_ascii=False), 0, 0,
                             json.dumps(guide['acknowledge']))
    assert out['ok'] and out['committed'] and not out['audit']['findings']
    png = (tmp_path / 'fp/infographic.png').read_bytes()
    assert png.startswith(b'\x89PNG') and len(png) > 80_000
    # Geometry is asserted in the kit's own suite; what belongs here is that the SHIPPED
    # compiler serves this reading and still refuses a pair with one series in it.
    single = dict(source, blocks=[dict(source['blocks'][0],
                                       fields={'category': 'Measure', 'columns': ['Oct 29, 2024']})])
    try:
        tools['fp_render'](json.dumps(single, ensure_ascii=False), 1, 0,
                           json.dumps(guide['acknowledge']))
    except RuntimeError as refusal:
        assert 'two or three series' in str(refusal)
    else:
        raise AssertionError('a paired chart with one series was drawn anyway')


def test_a_render_describes_itself_so_nobody_reads_outlined_glyphs(tmp_path):
    """The readback that replaces reading the SVG.

    The conversation that found the paired-bar defect read the rendered SVG twice and then
    grepped the codebase for two hex colours - trying to learn, from outlined glyph paths,
    what the frame had drawn. An outlined SVG has no text nodes and no rects, so both reads
    answered nothing and were re-sent on every later model call of the turn.
    """
    assert os.environ.get('FP_STUDIO_TESTING') != '1'
    source = {'title': 'Validator set and its economics', 'source': 'Aptos Explorer',
              'colorMode': 'pair',
              'blocks': [{'kind': 'chart', 'template': 'bar', 'style': 'paired',
                          'rows': [{'id': 'v', 'M': 'Validators', 'A': 146, 'B': 84},
                                   {'id': 's', 'M': 'Total staked', 'A': 839800000, 'B': 753200000}],
                          'fields': {'category': 'M', 'columns': ['A', 'B']}}]}
    Store(tmp_path).set_appearance('dark', 'dark mode', 'message')
    tools = {t.__name__: t for t in fp_tools(tmp_path)}
    guide = tools['fp_guide']('draw', 'bar', True)
    out = tools['fp_render'](json.dumps(source, ensure_ascii=False), 0, 0,
                             json.dumps(guide['acknowledge']))
    layout = out['layout']
    assert layout['blocks'] == [{'kind': 'chart', 'template': 'bar', 'style': 'paired'}]
    assert layout['frame']['colorMode'] == 'pair'
    # The two hexes that conversation grepped for, handed over with the series they belong to.
    assert [s['label'] for s in layout['swatches']] == ['A', 'B']
    assert len({s['color'] for s in layout['swatches']}) == 2
    assert all(s['color'].startswith('#') for s in layout['swatches'])
    # A printed string nobody authored is the renderer's own: a thousands separator here,
    # an indexed 100 in a botched redraw.
    assert '839,800,000' in layout['derived'] and 'Validators' not in layout['derived']
    assert layout['clipped'] == [] and layout['warnings'] == []
    # The SVG is still delivered; the label says what reading it would buy.
    assert 'outlined glyphs' in out['artifacts']['svg']
    assert out['artifacts']['png'] == 'fp/infographic.png'
    # And it stays with the revision, so a later turn can ask without re-rendering.
    assert Store(tmp_path).get('infographic')['receipt']['layout'] == layout


def test_the_shipped_bundle_renders_the_declared_light_pack(tmp_path):
    """Light or dark is the user's call, and both packs must be IN the installed bundle.

    The gate that asks the question is worthless if the answer cannot be drawn: a bundle
    missing `fp-v1-light.json` would refuse dark (the user said light) and fail light (no
    such pack), which is a product that cannot draw at all.
    """
    assert os.environ.get('FP_STUDIO_TESTING') != '1'
    source = {'title': 'Paper', 'source': 'test', 'colorMode': 'sequential',
              'blocks': [{'kind': 'chart', 'template': 'bar',
                          'rows': [{'id': 'a', 'K': 'A', 'V': 3}, {'id': 'b', 'K': 'B', 'V': 5}]}]}
    tools = {t.__name__: t for t in fp_tools(tmp_path)}
    rules = json.dumps({n: design.digest(n) for n in design.required(source)})
    # No declaration: the real tool refuses and names the one call that fixes it.
    with pytest.raises(design.DesignRulesError, match='ask_user'):
        tools['fp_render'](json.dumps(source), 0, 0, rules)
    Store(tmp_path).set_appearance('light', '라이트 모드로', 'message')
    with pytest.raises(design.DesignRulesError, match='fp-v1-light'):
        tools['fp_render'](json.dumps(source), 0, 0, rules)
    light = dict(source, theme='fp-v1-light')
    out = tools['fp_render'](json.dumps(light), 0, 0,
                             json.dumps({n: design.digest(n) for n in design.required(light)}))
    assert out['ok'] and out['committed'] and not out['audit']['findings']
    assert out['layout']['frame']['appearance'] == 'light'
    # The committed receipt pins both files: the light pack IS the dark pack plus a delta,
    # so a base edited afterwards must move the fingerprint too.
    theme = Store(tmp_path).get('infographic')['receipt']['theme']
    assert {'fp-v1.json', 'fp-v1-light.json'} <= {asset['name'] for asset in theme['assets']}
    assert theme['inherits'] == ['fp-v1'] and theme['id'] == 'fp-v1-light'
    png = (tmp_path / 'fp/infographic.png').read_bytes()
    assert png.startswith(b'\x89PNG') and len(png) > 50_000


def test_the_shipped_bundle_serves_tinted_nodes_and_named_categories(tmp_path):
    """The two primitives the delivered frames use, through the installed compiler.

    A category that fills its box (rather than washing it) and a row of chips naming those
    categories are what a delivered frame does; a bundle whose catalog advertises `tinted`
    but whose renderer ignores it would be a documented feature that does not exist.
    """
    assert os.environ.get('FP_STUDIO_TESTING') != '1'
    diagram = {'nodes': [{'id': 'a', 'label': 'User action', 'group': 'Actor'},
                         {'id': 'b', 'label': 'Atomic execution', 'group': 'Execution'},
                         {'id': 'c', 'label': 'validateUserOp()', 'group': 'Validation'}],
               'edges': [{'from': 'a', 'to': 'b'}, {'from': 'b', 'to': 'c'}]}
    source = {'title': 'Account and transaction abstraction', 'source': 'Four Pillars',
              'colorMode': 'categorical',
              'blocks': [{'kind': 'chart', 'template': 'flowchart', 'style': 'tinted',
                          'legend': True, 'diagram': diagram}]}
    Store(tmp_path).set_appearance('light', '라이트 모드로', 'message')
    tools = {t.__name__: t for t in fp_tools(tmp_path)}
    # The catalog is how a model learns the reading exists.
    guide = tools['fp_guide']('draw', 'flowchart', True)
    assert any(s['id'] == 'tinted' for s in guide['grammars'][0]['styles'])
    document = dict(source, theme='fp-v1-light')
    out = tools['fp_render'](json.dumps(document, ensure_ascii=False), 0, 0,
                             json.dumps(guide['acknowledge']))
    assert out['ok'] and out['committed'] and not out['audit']['findings']
    # Three declared categories, three authorised hues, named under the graphic.
    swatches = {s['label'] for s in out['layout']['swatches']}
    assert {'Actor', 'Execution', 'Validation'} <= swatches, out['layout']['swatches']
    png = (tmp_path / 'fp/infographic.png').read_bytes()
    assert png.startswith(b'\x89PNG') and len(png) > 50_000


def test_the_footer_band_stacks_instead_of_painting_over_the_brand_mark(tmp_path):
    """The band a shipped frame drew over the FOUR PILLARS mark.

    A 79-character note plus `Source X(@VitalikButerin)` plus a date were placed left to
    right from a running x with no right edge: "X(@VitalikButerin)" landed on top of the
    wordmark and "Date as of" was drawn at x=1988 on a 1920px frame - off the picture.
    The band now wraps a value to a second line and moves an entry that no longer fits
    down a row, and the frame reserves the height that takes.
    """
    assert os.environ.get('FP_STUDIO_TESTING') != '1'
    document = {'title': 'Vitalik roadmap posts', 'source': 'X(@VitalikButerin)',
                'dateAsOf': '2026-09-20', 'theme': 'fp-v1', 'colorMode': 'categorical',
                'note': 'Includes only posts on changes, updates, or redefinitions of '
                        'roadmap direction.',
                'noteRequest': 'user: "only roadmap-direction posts"',
                'blocks': [{'kind': 'text', 'text': 'body'}]}
    Store(tmp_path).set_appearance('dark', 'dark', 'message')
    tools = {t.__name__: t for t in fp_tools(tmp_path)}
    rules = json.dumps({n: design.digest(n) for n in design.required(document)})
    out = tools['fp_render'](json.dumps(document, ensure_ascii=False), 0, 0, rules)
    # Nothing was cut, and every entry the author wrote is still in the frame.
    assert out['ok'] and out['layout']['clipped'] == []
    # The note the designer's own reference frame carries wraps rather than overflowing.
    long_note = dict(document, note='The Ether Machine went private in Apr 2026. n/d: ETH '
                                    'units not disclosed for ETFs. ETHB operator reports '
                                    'conflict (Figment/Galaxy/Attestant vs Coinbase '
                                    'Prime); unresolved.')
    wrapped = tools['fp_render'](json.dumps(long_note, ensure_ascii=False), 1, 0, rules)
    assert wrapped['ok'] and wrapped['layout']['clipped'] == []
    # Text the band genuinely cannot hold is refused, not silently truncated: Korean
    # costs a full em per character, so 170 of them do not fit two lines.
    overflowing = dict(document, note='로드맵 방향의 변경, 업데이트 또는 재정의에 해당하는 '
                                      '게시물만 포함하며, ' + '세부 조건은 별도로 명시한다. ' * 6)
    with pytest.raises(ValueError, match='footer cannot hold'):
        tools['fp_render'](json.dumps(overflowing, ensure_ascii=False), 2, 0, rules)
