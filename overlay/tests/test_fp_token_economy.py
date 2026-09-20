"""The transcript is replayed on every model call, so payload size is a contract.

Measured on a real session (~3.9M input tokens for ONE infographic): `fp_render` and
`fp_research` arguments were 42% of it, fetched page bodies 17%, and `fp_inspect` echoed
the whole document before every edit. These tests pin the paths that fixed that:

- an edit names a change (pointer ops) instead of resending the document,
- inspect returns an outline and hashes, with readers for the parts,
- web_fetch returns the head of a page and keeps every byte in the receipt.

They are size assertions on purpose. A "harmless" re-add of the full document to a tool
result is exactly the regression that cost the tokens, and it is invisible in behaviour.
"""
import json
import tempfile


import pytest

from coworker import permissions, risk
from coworker.fp import design
from coworker.fp.common import ConflictError, dumps
from coworker.fp.patch import PatchError, apply_ops, outline
from coworker.fp.rendering import RenderController
from coworker.fp.research import review_document
from coworker.fp.store import Store
from coworker.tools.fp import WRITE_TOOLS, fp_tools

from test_fp_core_v03 import acknowledge, rendered


@pytest.fixture
def tools(tmp_path, monkeypatch):
    monkeypatch.setattr(RenderController, 'run',
                        lambda self, value, workspace, **kw: rendered(value.get('title', 'x')))
    funcs = {fn.__name__: fn for fn in fp_tools(tmp_path)}
    # Every render needs the user's light/dark declaration first; these tests stand for a
    # conversation where they said dark.
    Store(tmp_path).set_appearance('dark', 'dark mode', 'message')
    render, edit = funcs['fp_render'], funcs['fp_edit']

    def render_with_rules(input_json, rev, research_rev, design_rules='', **kw):
        return render(input_json, rev, research_rev, design_rules or acknowledge(input_json), **kw)

    def edit_with_rules(ops_json, rev, research_rev, design_rules='', **kw):
        # The skills a document requires follow from its grammars, which an edit rarely
        # changes; fp_inspect's receipt.design_rules carries the last render's set.
        name = kw.get('name', 'infographic')
        current = Store(tmp_path).get(name)
        rules = design_rules or dumps(
            {n: design.digest(n) for n in design.required(current['input'] if current else {})})
        return edit(ops_json, rev, research_rev, rules, **kw)

    funcs['fp_render'] = render_with_rules
    funcs['fp_edit'] = edit_with_rules
    return funcs


def table_document(rows: int = 120) -> dict:
    """A document of realistic size: the thing an edit must not resend."""
    return {'title': 'Quarterly network comparison', 'source': 'Example Corp',
            'dateAsOf': '2026-09-13', 'note': 'Draft',
            'noteRequest': 'the user asked for a "Draft" label in the footer',
            'blocks': [{'kind': 'table', 'template': 'table',
                        'rows': [{'id': f'r{i}', 'cells': [f'Network {i}', str(i * 3), 'stable'],
                                  'note': 'measured under the same denominator'} for i in range(rows)]}]}


def chars(payload) -> int:
    return len(json.dumps(payload, ensure_ascii=False, default=str))


# ---------------------------------------------------------------- pointer ops

def test_ops_change_exactly_what_they_name():
    doc = {'a': {'b': [1, 2, 3]}, 'keep': 'me'}
    out = apply_ops(doc, [{'op': 'set', 'pointer': '/a/b/1', 'value': 9},
                          {'op': 'append', 'pointer': '/a/b', 'value': 4},
                          {'op': 'insert', 'pointer': '/a/b/0', 'value': 0},
                          {'op': 'remove', 'pointer': '/keep'},
                          {'op': 'set', 'pointer': '/new', 'value': True}])
    assert out == {'a': {'b': [0, 1, 9, 3, 4]}, 'new': True}
    assert doc == {'a': {'b': [1, 2, 3]}, 'keep': 'me'}  # input untouched


def test_ops_accept_negative_index_and_escaped_tokens():
    assert apply_ops({'x': [1, 2]}, [{'op': 'set', 'pointer': '/x/-1', 'value': 5}]) == {'x': [1, 5]}
    assert apply_ops({'a/b': 1}, [{'op': 'set', 'pointer': '/a~1b', 'value': 2}]) == {'a/b': 2}


@pytest.mark.parametrize('ops', [
    [{'op': 'set', 'pointer': '/blocks/9/title', 'value': 'x'}],   # invented branch
    [{'op': 'remove', 'pointer': '/gone'}],                        # already absent
    [{'op': 'set', 'pointer': '/blocks/0/rows/99', 'value': 1}],   # index out of range
    [{'op': 'append', 'pointer': '/title', 'value': 'x'}],         # not a list
    [{'op': 'set', 'pointer': 'blocks', 'value': 1}],              # not a pointer
    [{'op': 'set', 'pointer': '/title'}],                          # no value
    [{'op': 'remove', 'pointer': '/title', 'value': 1}],           # value with remove
    [{'op': 'patch', 'pointer': '/title', 'value': 1}],            # unknown op
    [{'op': 'set', 'pointer': '', 'value': 'scalar root'}],        # root must stay an object
    [],                                                            # nothing to do
    {'op': 'set'},                                                 # not a list
])
def test_ops_refuse_anything_they_cannot_apply_exactly(ops):
    with pytest.raises(PatchError):
        apply_ops({'title': 't', 'blocks': [{'rows': [1]}]}, ops)


def test_ops_payload_is_bounded():
    with pytest.raises(PatchError, match='too large'):
        apply_ops({'t': 1}, [{'op': 'set', 'pointer': '/t', 'value': 'x' * 70_000}])
    with pytest.raises(PatchError, match='200 ops'):
        apply_ops({'t': 1}, [{'op': 'set', 'pointer': '/t', 'value': 1}] * 201)


def test_outline_maps_structure_without_content():
    body = outline(table_document(120))
    assert body[0]['pointer'] == '/blocks/0' and body[0]['rows_count'] == 120
    assert 'Network 7' not in json.dumps(body)


# ---------------------------------------------------------------- fp_edit

def test_edit_revises_one_value_for_a_fraction_of_the_document(tools):
    doc = table_document()
    tools['fp_render'](dumps(doc), 0, 0)
    ops = [{'op': 'set', 'pointer': '/blocks/0/rows/3/cells/1', 'value': '41.2'},
           {'op': 'set', 'pointer': '/note', 'value': 'Revised after review'}]
    result = tools['fp_edit'](dumps(ops), 1, 0)
    assert result['committed'] and result['revision'] == 2
    assert result['ops_applied'] == ['/blocks/0/rows/3/cells/1', '/note']
    stored = tools['fp_inspect'](include_source=True)['input']
    assert stored['blocks'][0]['rows'][3]['cells'][1] == '41.2'
    assert stored['note'] == 'Revised after review'
    assert stored['blocks'][0]['rows'][4] == doc['blocks'][0]['rows'][4]
    # The economics, not a style preference: naming the change costs ~1% of resending it.
    assert chars(ops) * 20 < chars(doc)


def test_edit_keeps_every_gate_a_full_render_has(tools):
    doc = table_document(8)
    tools['fp_render'](dumps(doc), 0, 0)
    ops = dumps([{'op': 'set', 'pointer': '/title', 'value': 'Second look'}])
    with pytest.raises(ConflictError):      # stale document revision
        tools['fp_edit'](ops, 0, 0)
    with pytest.raises(ConflictError):      # stale research revision
        tools['fp_edit'](ops, 1, 7)
    with pytest.raises(design.DesignRulesError):   # unacknowledged design rules
        tools['fp_edit'](ops, 1, 0, design_rules='{}')
    with pytest.raises(PatchError):         # a pointer that does not resolve
        tools['fp_edit'](dumps([{'op': 'set', 'pointer': '/blocks/4/title', 'value': 'x'}]), 1, 0)
    assert tools['fp_inspect']()['revision'] == 1   # nothing committed by the refusals


def test_edit_refuses_a_document_that_breaks_the_design_rules(tools):
    tools['fp_render'](dumps(table_document(4)), 0, 0)
    # An empty required frame field is a decidable violation, and an edit can create one.
    with pytest.raises(design.DesignRulesError):
        tools['fp_edit'](dumps([{'op': 'set', 'pointer': '/title', 'value': ''}]), 1, 0)


def test_edit_needs_a_first_revision(tools):
    with pytest.raises(ValueError, match='fp_render'):
        tools['fp_edit'](dumps([{'op': 'set', 'pointer': '/title', 'value': 'x'}]), 0, 0)


# ---------------------------------------------------------------- readers

def test_inspect_returns_an_outline_not_the_document(tools):
    doc = table_document(120)
    tools['fp_render'](dumps(doc), 0, 0)
    view = tools['fp_inspect']()
    assert 'input' not in view
    assert view['outline'][0]['rows_count'] == 120
    assert view['source_sha256'] and view['frame']['title'] == doc['title']
    # Inspect runs before every edit; it must not scale with the document.
    assert chars(view) < 2_500 < chars(doc)
    assert chars(tools['fp_inspect'](include_source=True)) > chars(doc)


def test_inspect_summarises_research_without_the_excerpts(tmp_path, tools):
    store = Store(tmp_path)
    page = 'Network A reported 41.2 percent in Q3. ' + 'context filler. ' * 400
    src = store.capture('https://example.test/q3', page,
                        {'kind': 'local_file', 'origin': 'transport', 'truncated': False})
    excerpt = 'Network A reported 41.2 percent in Q3.'
    tools['fp_research'](dumps({
        'brief': {'goal': 'g', 'audience': 'a', 'main_message': 'm', 'as_of': '2026-09-13'},
        'claims': [{'id': 'a', 'statement': 'A reported 41.2', 'status': 'supported',
                    'source_id': src['id'], 'excerpt': excerpt,
                    'bindings': [{'pointer': '/blocks/0/rows/0/cells/1', 'value': '41.2'}]}],
        'decisions': ['Use Q3'], 'open_questions': []}), 0)
    view = tools['fp_inspect']()
    body = json.dumps(view, ensure_ascii=False)
    assert excerpt not in body and page[:60] not in body
    claim = view['research']['claims'][0]
    assert claim == {'pointer': '/claims/0', 'id': 'a', 'status': 'supported',
                     'source_id': src['id'], 'bindings': 1, 'statement': 'A reported 41.2'}
    assert view['sources']['count'] == 1 and view['sources']['latest'][0]['id'] == src['id']
    # And the excerpt is still readable, by pointer, when it is actually needed.
    assert tools['fp_source']('/claims/0', doc='research')['value']['excerpt'] == excerpt


def test_source_reads_a_slice_and_reports_shape_when_too_large(tools):
    tools['fp_render'](dumps(table_document(120)), 0, 0)
    assert tools['fp_source']('/blocks/0/rows/2/cells')['value'] == ['Network 2', '6', 'stable']
    big = tools['fp_source']('/blocks/0/rows')
    assert big['too_large'] and 'value' not in big
    assert big['shape_chars_per_child'][0]['pointer'] == '/blocks/0/rows/0'
    with pytest.raises(ValueError, match='No such path'):
        tools['fp_source']('/blocks/9')


def test_source_text_pages_and_searches_the_captured_page(tmp_path, tools):
    store = Store(tmp_path)
    page = 'head. ' * 500 + 'THE NUMBER IS 41.2 percent. ' + 'tail. ' * 500
    src = store.capture('https://example.test/p', page,
                        {'kind': 'local_file', 'origin': 'transport', 'truncated': False})
    first = tools['fp_source_text'](src['id'], limit=1000)
    assert first['total_chars'] == len(page) and len(first['text']) == 1000
    assert first['next_offset'] == 1000
    second = tools['fp_source_text'](src['id'], offset=first['next_offset'], limit=1000)
    assert second['text'] == page[1000:2000]
    found = tools['fp_source_text'](src['id'], find='THE NUMBER IS 41.2', limit=400)
    assert found['matches'] == 1 and 'THE NUMBER IS 41.2 percent.' in found['windows'][0]['text']
    assert chars(found) < 1_500 < len(page)


def test_history_stays_flat_as_revisions_accumulate(tools):
    tools['fp_render'](dumps(table_document(6)), 0, 0)
    for revision in range(1, 4):
        tools['fp_edit'](dumps([{'op': 'set', 'pointer': '/title', 'value': f't{revision}'}]),
                         revision, 0)
    listing = tools['fp_history']()
    assert [r['revision'] for r in listing['revisions']] == [4, 3, 2, 1]
    body = json.dumps(listing)
    assert 'Pretendard' not in body and 'fonts' not in body
    assert chars(listing) < 2_000


# ---------------------------------------------------------------- no web surface

def test_the_fp_build_registers_no_web_search_or_fetch():
    """The product draws what the user hands over; there is no page to research.

    A user attached two source images and asked for two infographics. The model searched
    the web, read four pages and composed frames out of them instead - and the numbers on
    the delivered frame came from a page, not from the image in the message. The capability
    is removed rather than discouraged: an instruction competes with the tool that is
    right there, and the tool wins.
    """
    from coworker import agent as agent_mod
    import inspect
    source = inspect.getsource(agent_mod.build_engine)
    assert 'make_web_search_tool' not in source
    assert 'make_web_fetch_tool' not in source
    assert 'ask_user_tool()' in source, 'the human-in-the-loop primitive stays'


def test_no_fp_tool_routes_to_the_web(tools):
    names = {name for name in tools if name.startswith('fp_')}
    surface = json.dumps([tools[n].__doc__ or '' for n in sorted(names)])
    for word in ('web_fetch', 'web_search', 'URL', 'http'):
        assert word not in surface, f'{word} is still advertised by an FP tool'


# ---------------------------------------------------------------- research edits

def test_research_edit_revalidates_the_whole_result(tmp_path, tools):
    store = Store(tmp_path)
    src = store.capture('https://example.test/r', 'Network A has value 10.',
                        {'kind': 'local_file', 'origin': 'transport', 'truncated': False})
    tools['fp_research'](dumps({
        'brief': {'goal': 'g', 'audience': 'a', 'main_message': 'm', 'as_of': '2026-09-13'},
        'claims': [{'id': 'a', 'statement': 'value', 'status': 'unresolved',
                    'bindings': [{'pointer': '/blocks/0/rows/0/cells/1', 'value': '10'}]}],
        'open_questions': ['Confirm the denominator']}), 0)
    # Promoting a claim still needs a verbatim passage from a captured receipt.
    with pytest.raises(ValueError, match='verbatim passage'):
        tools['fp_research_edit'](dumps([
            {'op': 'set', 'pointer': '/claims/0/status', 'value': 'supported'},
            {'op': 'set', 'pointer': '/claims/0/source_id', 'value': src['id']},
            {'op': 'set', 'pointer': '/claims/0/excerpt', 'value': 'Network A has value 99.'}]), 1)
    saved = tools['fp_research_edit'](dumps([
        {'op': 'set', 'pointer': '/claims/0/status', 'value': 'supported'},
        {'op': 'set', 'pointer': '/claims/0/source_id', 'value': src['id']},
        {'op': 'set', 'pointer': '/claims/0/excerpt', 'value': 'Network A has value 10.'},
        {'op': 'set', 'pointer': '/open_questions', 'value': []}]), 1)
    assert saved['revision'] == 2
    assert saved['research']['claims'][0]['status'] == 'supported'
    assert saved['research']['open_questions'] == []
    with pytest.raises(ConflictError):
        tools['fp_research_edit'](dumps([{'op': 'set', 'pointer': '/claims/0/note', 'value': 'x'}]), 1)


def test_research_write_result_is_a_summary_not_an_echo(tmp_path, tools):
    store = Store(tmp_path)
    long_statement = 'A reported the figure under a stable denominator. ' * 20
    src = store.capture('https://example.test/e', 'Network A has value 10.',
                        {'kind': 'local_file', 'origin': 'transport', 'truncated': False})
    saved = tools['fp_research'](dumps({
        'brief': {'goal': 'g', 'audience': 'a', 'main_message': 'm'},
        'claims': [{'id': 'a', 'statement': long_statement, 'status': 'supported',
                    'source_id': src['id'], 'excerpt': 'Network A has value 10.', 'bindings': []}]}), 0)
    assert saved['revision'] == 1
    assert 'Network A has value 10.' not in json.dumps(saved)
    assert saved['research']['claims'][0]['statement'].endswith('…')


# ---------------------------------------------------------------- wiring

def test_every_fp_write_tool_is_risk_classified_and_root_scoped():
    """A write tool missing from either table writes without root scoping."""
    for name in WRITE_TOOLS:
        assert risk.classify(name) is risk.RiskClass.WRITE_LOCAL, name
        paths, located = permissions.write_paths(name, {'name': 'infographic'})
        assert located and paths, name


def test_the_fixed_per_call_cost_stays_within_its_budget():
    """Instructions + tool schemas are re-sent on EVERY model call of the conversation.

    Unlike a tool result, this cost is invisible in any single exchange: it is paid once
    per iteration, up to twelve times per user turn. The budget is what stops policy from
    being restated in a docstring, or a tool's mechanics from being restated in the
    prompt. Raising it is a product decision, not a refactor.

    It has been raised four times, each time for a capability: reproduce mode
    (`fp_capture_image` and the redraw rule), the final inspection gate (`fp_review`'s
    checklist and `fp_publish`'s verdicts), routing a source the user SUPPLIES - a pasted
    diagram is captured like an attachment, and the prompt now has to say so and name
    `referenceWaiver` - and the one-call draw route (`fp_guide('draw')` serving the
    contracts with every required rule card and digest, plus `appendix=True` for the frame
    arithmetic behind a card). 15,479 chars before the duplication was removed, 12,762
    after, 15,009 with the first two capabilities, 15,158 with the third, 15,681 with the
    fourth - bought by removing two round trips per document, each of which replayed the
    entire transcript.
    """
    from coworker.tools.registry import ToolRegistry
    from coworker.fp.prompt import INSTRUCTIONS

    registry = ToolRegistry()
    for fn in fp_tools(tempfile.mkdtemp()):
        registry.register(fn)
    schemas = registry.schemas()
    assert len(schemas) == 16

    per_tool = {(s.get('function') or s)['name']: chars(s) for s in schemas}
    assert max(per_tool.values()) <= 1_300, per_tool
    assert chars(schemas) + len(INSTRUCTIONS) <= 15_800, (chars(schemas), len(INSTRUCTIONS))


# ---------------------------------------------------------------- the rules a document reads

def test_a_rule_card_stays_within_its_byte_cap():
    """A card is replayed on every authoring call of the conversation; the appendix is
    read once, on demand, and only when a frame value is in doubt.

    Before the split the mandatory reading for a table document was 11,167 chars of
    guideline, most of it Figma authoring mechanics (clone the frame, set the footer Y
    last, cell fill sizing) that fp-kit draws deterministically from the Frame Guide and
    the model cannot author. The cap is what stops that text from coming back.
    """
    for name in design.SKILLS:
        size = len(design.skill_path(name).read_bytes())
        assert size <= design.MAX_CARD_BYTES, (name, size)
    for document, ceiling in (
        (table_document(), 6_600),
        ({'title': 'x', 'blocks': [{'kind': 'chart', 'template': 'bar'}]}, 7_500),
        ({'title': 'x', 'blocks': [{'kind': 'chart', 'template': 'flowchart'}]}, 7_800),
    ):
        read = sum(len(design.load(n)['rules']) for n in design.required(document))
        assert read <= ceiling, (design.required(document), read)


def test_one_call_serves_the_contract_and_every_rule_it_requires(tools, tmp_path):
    """The read side of a first render is one round trip, not four.

    Every round trip replays the whole transcript, so fp_guide('vocabulary') +
    fp_guide('grammar') + fp_design_rules(index) + fp_design_rules(grammar) paid for the
    conversation three extra times before a single block was authored.
    """
    guide = tools['fp_guide']('draw', 'table')
    assert [g['id'] for g in guide['grammars']] == ['table']
    assert [r['name'] for r in guide['design_rules']] == ['fp-design-system', 'fp-design-table']
    assert set(guide['acknowledge']) == {'fp-design-system', 'fp-design-table'}
    assert 'FPInput' in guide['input']['contract']
    # The digest map the same call returned is accepted by the gate as it stands.
    out = tools['fp_render'](dumps(table_document(4)), 0, 0, json.dumps(guide['acknowledge']))
    assert out['committed'] is True
    # A redraw needs the reproduce rules in the same single call.
    assert 'fp-design-reproduce' in tools['fp_guide']('draw', 'flowchart', True)['acknowledge']
    # The appendix never rides along.
    assert 'Gap between the title and the infographic is 98px' not in json.dumps(guide)


def test_a_contract_already_delivered_comes_back_as_a_pointer(tools):
    """The second copy is the expensive one: it is re-sent on every later call.

    A real conversation called fp_guide('draw', 'bar', redraw=True) and then asked for
    the same grammar, the frame fields and the chart card again, one by one - four extra
    payloads that the transcript then carried for the rest of the turn.
    """
    first = tools['fp_guide']('draw', 'bar', True)
    assert first['grammars'][0]['id'] == 'bar'

    again = tools['fp_guide']('draw', 'bar', True)
    assert again.get('served_earlier') is True and 'grammars' not in again
    # The digest map still comes back: the render gate needs it, and it is two hashes.
    assert set(again['acknowledge']) == set(first['acknowledge'])

    for repeat in (tools['fp_guide']('grammar', 'bar'), tools['fp_guide']('input'),
                   tools['fp_design_rules']('fp-design-chart')):
        assert repeat.get('served_earlier') is True, repeat
        assert 'contract' not in repeat and 'rules' not in repeat

    # A compaction can drop it, so the text stays reachable on request.
    assert 'FPInput' in tools['fp_guide']('input', again=True)['contract']
    assert "style:'paired'" in tools['fp_design_rules']('fp-design-chart', again=True)['rules']
    # An appendix is read once, on demand, and is never suppressed.
    for _ in range(2):
        assert 'slanted (~48°)' in tools['fp_design_rules']('fp-design-chart', appendix=True)['rules']


def test_the_final_checklist_is_served_once_per_conversation(tools, tmp_path):
    """Twenty thousand characters, carried by every call that follows the second copy.

    fp_review's checklist is the largest payload this capability produces - 107 rules for
    a redraw. Nothing stopped it being served twice: a refused publish, a second opinion
    or a helper that just calls fp_review again paid for the whole thing a second time.
    """
    tools['fp_render'](dumps(table_document(4)), 0, 0)
    first = tools['fp_review']()['final_checklist']
    assert len(first['items']) > 30 and json.dumps(first)

    repeat = tools['fp_review']()['final_checklist']
    assert repeat.get('served_earlier') is True and 'items' not in repeat
    assert chars(repeat) < chars(first) / 8
    # The digests survive it: fp_publish needs them beside the verdicts, and they are
    # two hashes, not the rules.
    assert repeat['skills'] == first['skills'] and repeat['item_count'] == len(first['items'])
    # The mechanical review itself is not suppressed - only the rule text is.
    assert tools['fp_review']()['failures'] == tools['fp_review'](checklist=False)['failures']
    # A compaction can drop it, so the text stays reachable on request.
    assert tools['fp_review'](again=True)['final_checklist']['items'] == first['items']


def test_a_new_conversation_is_not_told_to_scroll_back(tmp_path, monkeypatch):
    """The ledger's scope is the transcript, not the project directory.

    The pointer says "this conversation already carries it in full". When the record
    lived in the workspace database it outlived the conversation, so the SECOND chat
    about the same project was told to scroll back to a contract it had never been sent -
    and handed the acknowledgement digests that let it render anyway.
    """
    monkeypatch.setattr(RenderController, 'run',
                        lambda self, value, workspace, **kw: rendered('x'))
    first_chat = {fn.__name__: fn for fn in fp_tools(tmp_path)}
    assert 'style' in first_chat['fp_design_rules']('fp-design-chart')['rules']
    assert first_chat['fp_design_rules']('fp-design-chart').get('served_earlier') is True

    second_chat = {fn.__name__: fn for fn in fp_tools(tmp_path)}
    served = second_chat['fp_design_rules']('fp-design-chart')
    assert served.get('served_earlier') is None
    assert 'style' in served['rules']


def test_an_oversized_readback_is_replaced_by_the_pointer_that_reads_it(tmp_path, monkeypatch):
    """`layout` is the cheap way to check a render - but it grows with the document.

    Every other summary on a write result has a cap; this one was copied out of the
    renderer whole, into the result AND the committed receipt, and then replayed on
    every later call of the turn. It stays whole while it fits.
    """
    big = {'frame': {'appearance': 'dark', 'colorMode': 'pair'},
           'blocks': [{'kind': 'table', 'template': 'table', 'row': f'Network {i}'}
                      for i in range(400)],
           'clipped': [], 'warnings': []}
    monkeypatch.setattr(RenderController, 'run',
                        lambda self, value, workspace, **kw: {**rendered('x'), 'layout': big})
    tools = {fn.__name__: fn for fn in fp_tools(tmp_path)}
    Store(tmp_path).set_appearance('dark', 'dark mode', 'message')
    out = tools['fp_render']('{"title":"A"}', 0, 0, acknowledge('{"title":"A"}'))

    assert chars(out['layout']) < chars(big) / 10
    # What a reader needs stays verbatim; only the part that did not fit is replaced.
    assert out['layout']['frame'] == big['frame'] and out['layout']['clipped'] == []
    assert out['layout']['blocks'] == {'too_large': True, 'chars': chars(big['blocks']),
                                       'pointer': '/blocks'}
    # And the whole readback is committed, so the pointer the result names reads it.
    assert Store(tmp_path).get('infographic')['receipt']['layout'] == big
    read = tools['fp_source']('/blocks/399', name='infographic', doc='layout')
    assert read['value'] == big['blocks'][399]
    # The next write replaces the readback, so the read says which revision answered it.
    assert read['revision'] == out['revision']


def test_a_write_result_carries_the_findings_not_the_standing_advisory(tools, tmp_path):
    """The review rides every render, edit, restore and inspect of the turn.

    Two of its parts are the same on all of them: the warnings, which say what mechanical
    checks cannot prove, and one line per unbound pointer - forty of them on a wide table.
    The findings are what the next edit acts on; the rest belongs at the gate.
    """
    document = {'title': 'A', 'content': [{'value': float(i)} for i in range(8)]}
    review = tools['fp_render'](dumps(document), 0, 0)['review']

    unbound = [f for f in review['failures'] if f.startswith('Unbound numeric value')]
    assert unbound == ['Unbound numeric value: /content/0/value, /content/1/value, '
                       '/content/2/value (+5 more)']
    assert 'Mechanical checks do not prove' not in json.dumps(review)
    assert review['warnings_count'] == 2
    # What it did NOT lose: the state of the document and every distinct problem with it.
    assert review['ok'] is False and review['revision'] == 1
    assert 'Editorial brief missing goal' in review['failures']

    full = tools['fp_review'](checklist=False)
    assert len([f for f in full['failures'] if f.startswith('Unbound numeric value')]) == 8
    assert any('Mechanical checks do not prove' in w for w in full['warnings'])
