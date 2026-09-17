"""The last gate: the design rules come back, by grammar, before anything is published.

Reading the rules at the start of a session and declaring the work done at the end are
separated by everything that happened in between. The rules that get forgotten are the
ones no compiler can check — slanted x-axis labels, a legend marker that mirrors the
render type, a first column that must not be shaded, a colour the sample had and the
redraw dropped.

So `fp_review` serves those lines back with an id each, scoped to the grammars this
document actually uses, and `fp_publish` refuses until every id has a verdict. What that
proves is that the rule was put in front of the model and answered — not that the answer
is true. The receipt says so, and so do these tests.
"""

import json

import pytest

from coworker.fp import design
from coworker.fp.common import dumps
from coworker.fp.store import Store

from test_fp_core_v03 import inspected, research, tools  # noqa: F401  (tools is a fixture)


TABLE = '{"title":"Networks","blocks":[{"kind":"table","columns":["a"],"rows":[{"label":"x"}]}]}'
CHART = ('{"title":"Networks","blocks":[{"kind":"chart","template":"bar",'
         '"categories":["Q1"],"series":[{"label":"Direct","values":[41.2]}]}]}')


def published_doc(tools, tmp_path, document=TABLE):
    store = Store(tmp_path)
    tools['fp_research'](json.dumps(research(store)), 0)
    body = json.loads(document)
    body['content'] = [{'value': 10}]          # the bound metric the review demands
    tools['fp_render'](dumps(body), 0, 1)
    return tools['fp_review']()['final_checklist']


# -- what is served ------------------------------------------------------------------


def test_the_checklist_is_the_rules_themselves_scoped_by_grammar(tools, tmp_path):
    checklist = published_doc(tools, tmp_path, TABLE)
    assert set(checklist['skills']) == {'fp-design-system', 'fp-design-table'}
    rules = [item['rule'] for item in checklist['items']]
    # Verbatim lines from the shipped guideline, not a paraphrase of them.
    assert "Don't shrink columns to text width — full 1696px unless asked." in rules
    assert any(r.startswith("Don't make the first column brighter") for r in rules)
    # A table document is never asked about chart rules.
    assert not any('legend' in r.lower() for r in rules)
    assert {item['verb'] for item in checklist['items']} == {'must', 'never'}


def test_a_chart_document_is_asked_the_chart_rules(tools, tmp_path):
    checklist = published_doc(tools, tmp_path, CHART)
    assert 'fp-design-chart' in checklist['skills']
    rules = [item['rule'] for item in checklist['items']]
    assert "Don't drop the axis titles, and don't leave x-axis labels horizontal — always slant them." in rules
    assert any('Match the marker to the render type' in r for r in rules)
    assert any("style:'paired'" in r for r in rules)


def test_every_item_is_addressable_and_traceable(tools, tmp_path):
    checklist = published_doc(tools, tmp_path, TABLE)
    ids = [item['id'] for item in checklist['items']]
    assert len(ids) == len(set(ids)) and all(len(i) == 8 for i in ids)
    assert all(item['skill'] in checklist['skills'] for item in checklist['items'])
    assert all(item['section'] for item in checklist['items'])


def test_the_checklist_never_rides_a_write_result(tools, tmp_path):
    """It is served once, at the gate — not appended to every render and edit."""
    out = tools['fp_render'](TABLE, 0, 0)
    assert 'final_checklist' not in json.dumps(out)
    edit = tools['fp_edit'](dumps([{'op': 'set', 'pointer': '/title', 'value': 'B'}]), 1, 0,
                            dumps({n: design.digest(n) for n in design.required(json.loads(TABLE))}))
    assert 'final_checklist' not in json.dumps(edit)
    assert 'final_checklist' not in json.dumps(tools['fp_review'](checklist=False))


# -- what it refuses -------------------------------------------------------------------


def test_publishing_without_an_inspection_is_refused(tools, tmp_path):
    published_doc(tools, tmp_path)
    with pytest.raises(design.DesignRulesError, match='Final inspection is mandatory'):
        tools['fp_publish'](1, 1)


def test_an_unanswered_rule_is_named(tools, tmp_path):
    checklist = published_doc(tools, tmp_path)
    partial = {item['id']: {'verdict': 'pass'} for item in checklist['items'][:-2]}
    skipped = [item['id'] for item in checklist['items'][-2:]]
    with pytest.raises(design.DesignRulesError) as error:
        tools['fp_publish'](1, 1, dumps({'skills': checklist['skills'], 'checks': partial}))
    assert '2 design rules were not inspected' in str(error.value)
    assert all(i in str(error.value) for i in skipped)


def test_a_rule_that_is_not_passing_blocks_publication(tools, tmp_path):
    checklist = published_doc(tools, tmp_path)
    checks = {item['id']: {'verdict': 'pass'} for item in checklist['items']}
    failing = checklist['items'][3]['id']
    checks[failing] = {'verdict': 'fail', 'note': 'axis labels are horizontal'}
    with pytest.raises(design.DesignRulesError, match='neither passing nor explained'):
        tools['fp_publish'](1, 1, dumps({'skills': checklist['skills'], 'checks': checks}))


def test_not_applicable_needs_a_reason(tools, tmp_path):
    checklist = published_doc(tools, tmp_path)
    checks = {item['id']: {'verdict': 'pass'} for item in checklist['items']}
    excused = checklist['items'][5]['id']
    checks[excused] = {'verdict': 'n/a'}
    with pytest.raises(design.DesignRulesError, match='neither passing nor explained'):
        tools['fp_publish'](1, 1, dumps({'skills': checklist['skills'], 'checks': checks}))
    checks[excused] = {'verdict': 'n/a', 'note': 'this document has no merged key cells'}
    assert tools['fp_publish'](1, 1, dumps({'skills': checklist['skills'], 'checks': checks}))['ok']


def test_an_inspection_signed_against_older_rules_is_refused(tools, tmp_path):
    checklist = published_doc(tools, tmp_path)
    checks = {item['id']: {'verdict': 'pass'} for item in checklist['items']}
    stale = dict(checklist['skills'], **{'fp-design-table': 'a' * 64})
    with pytest.raises(design.DesignRulesError, match='older rules'):
        tools['fp_publish'](1, 1, dumps({'skills': stale, 'checks': checks}))


# -- what it records ---------------------------------------------------------------------


def test_the_publication_receipt_records_the_inspection(tools, tmp_path):
    published_doc(tools, tmp_path)
    out = tools['fp_publish'](1, 1, inspected(tools))
    assert out['final_inspection']['inspected'] > 40
    assert set(out['final_inspection']['skills']) == {'fp-design-system', 'fp-design-table'}
    report = (tmp_path / out['artifacts']['sources']).read_text('utf-8')
    assert '## Design inspection' in report
    assert 'rules inspected against the rendered artifact' in report
    assert 'not a human design review' in report
