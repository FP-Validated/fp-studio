"""Routed SDK access: choose a grammar, then read only that grammar.

The regression these guard: `fp_guide` used to serve the kit's whole 21 KB contract file
(paged), so every document — a four-row table included — paid for the schema of all 45
grammars. The fix is structural, not advisory: there is no topic that returns the whole
SDK, so a model cannot skip the choice and read everything instead.
"""

from __future__ import annotations

import json
import tempfile

import pytest

from coworker.fp import sdk
from coworker.fp.sdk import SdkError
from coworker.fp.store import Store
from coworker.tools.fp import fp_tools


@pytest.fixture
def guide():
    return {f.__name__: f for f in fp_tools(tempfile.mkdtemp())}["fp_guide"]


def _chars(payload) -> int:
    return len(json.dumps(payload, ensure_ascii=False))


# -- the catalog is the entry point -------------------------------------------------


def test_catalog_lists_every_grammar_without_any_schema(guide):
    catalog = guide("vocabulary")
    ids = [row["id"] for row in catalog["grammars"]]
    assert len(ids) == len(set(ids)) >= 40
    assert "table" in ids and "bar" in ids and "flowchart" in ids
    # Choosing needs intent + triggers + budget, and nothing else.
    row = next(r for r in catalog["grammars"] if r["id"] == "bar")
    assert row["intent"] == "compare" and row["trigger"] and row["budget"]
    assert row["family"] == "cartesian"
    # No contract text leaks into the catalog — that is the whole point.
    blob = json.dumps(catalog)
    assert "interface" not in blob and "BlockBase" not in blob


def test_a_grammar_slice_carries_only_what_it_references(guide):
    bar = guide("grammar", "bar")
    assert "kind: 'chart'" in bar["contract"]
    assert "interface Row" in bar["contract"]
    # The other 44 grammars' variants are absent.
    for foreign in ("kind: 'table'", "kind: 'kpi'", "kind: 'stages'"):
        assert foreign not in bar["contract"]
    table = guide("grammar", "table")
    assert "kind: 'table'" in table["contract"]
    assert "kind: 'chart'" not in table["contract"]


def test_each_grammar_names_the_design_skill_that_governs_it(guide):
    assert guide("grammar", "table")["design_skill"] == "fp-design-table"
    assert guide("grammar", "bar")["design_skill"] == "fp-design-chart"
    assert guide("grammar", "flowchart")["design_skill"] == "fp-design-flowchart"
    # A grammar in no chart family inherits the diagram rules rather than none.
    assert sdk.design_skill_for("swimlane") == "fp-design-flowchart"


def test_there_is_no_whole_sdk_topic(guide):
    # The old escape hatch, by name and by shape.
    for topic in ("composition", "types", "all", "everything"):
        with pytest.raises(ValueError, match="Invalid guide topic"):
            guide(topic)
    with pytest.raises(ValueError, match="needs name"):
        guide("grammar")
    with pytest.raises(SdkError, match="Unknown grammar"):
        guide("grammar", "isometric-3d-donut")


def test_frame_contract_excludes_the_grammar_variants(guide):
    contract = guide("input")["contract"]
    assert "interface FPInput" in contract
    assert "dateAsOf" in contract and "blocks?" in contract
    # The union itself is not inlined here; grammars are read one at a time.
    assert "kind: 'chart'" not in contract


# -- the cost, measured -------------------------------------------------------------


def test_authoring_one_grammar_costs_far_less_than_the_whole_kit(guide):
    kit = sdk.kit_root()
    whole_sdk = (
        len((kit / "src/types.ts").read_text())
        + len((kit / "templates/registry.json").read_text())
    )
    one_pass = (
        _chars(guide("vocabulary")) + _chars(guide("input")) + _chars(guide("grammar", "bar"))
    )
    # The old path served the contract file AND the raw registry; the routed path serves
    # a catalog, the frame fields and one grammar. Keep the win big enough to matter.
    assert one_pass < whole_sdk * 0.45, (one_pass, whole_sdk)
    # And a second grammar in the same document is incremental, not another whole read.
    assert _chars(guide("grammar", "table")) < 2500


# -- naming a grammar is mandatory and checked --------------------------------------


def test_render_refuses_a_grammar_the_kit_does_not_serve(tmp_path):
    Store(tmp_path).set_appearance('dark', 'dark mode', 'message')
    tools = {f.__name__: f for f in fp_tools(tmp_path)}
    from coworker.fp import design

    document = {
        "title": "Revenue",
        "blocks": [{"kind": "chart", "template": "bar-3d", "rows": [{"q": "Q1", "v": 1}]}],
    }
    acks = json.dumps({n: design.digest(n) for n in design.required(document)})
    with pytest.raises(ValueError, match="Unknown FP grammar: bar-3d"):
        tools["fp_render"](json.dumps(document), 0, 0, acks)


def test_validation_is_skipped_when_no_grammar_is_named():
    # A free-composition document (text/cards only) names no template; nothing to check.
    assert sdk.validate_templates({"title": "x", "blocks": [{"kind": "text", "text": "a"}]}) == []
    assert sdk.validate_templates({"title": "x", "template": "auto"}) == []


def test_an_absent_kit_cannot_block_a_valid_document(monkeypatch, tmp_path):
    # An installation whose kit is missing: every contract read fails.
    monkeypatch.setattr(sdk, "kit_root", lambda: tmp_path / "no-kit")
    sdk.cache_clear()
    try:
        # No installed kit to check against: the renderer is the backstop, so a document
        # naming a real grammar must not be refused here.
        assert sdk.validate_templates({"blocks": [{"template": "bar"}]}) == []
        with pytest.raises(SdkError, match="absent|incomplete"):
            sdk.index()
    finally:
        sdk.cache_clear()
