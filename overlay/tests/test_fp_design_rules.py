"""The FOUR PILLARS design rules as an enforced runtime gate.

What these pin: a render cannot happen without the rules for the grammars in play, a
stale/edited rules file invalidates the acknowledgement instead of passing, the shipped
text is the customer's verbatim guideline (not a paraphrase), and the decidable subset of
the rules (type scale, palette binding, empty frame fields) is actually rejected.
"""

from __future__ import annotations

import json

import pytest

from coworker.fp import design
from coworker.fp.design import DesignRulesError
from coworker.tools.fp import fp_tools


def _tools(workspace):
    return {f.__name__: f for f in fp_tools(workspace)}


def _acks(*names):
    return json.dumps({name: design.digest(name) for name in names})


TABLE_DOC = {
    "title": "Fee comparison",
    "blocks": [{"kind": "table", "rows": [{"a": "1"}], "columns": ["a"]}],
}
CHART_DOC = {
    "title": "Revenue by quarter",
    "blocks": [{"kind": "chart", "template": "bar", "rows": [{"q": "Q1", "v": 1}]}],
}
FLOW_DOC = {
    "title": "Message routing",
    "blocks": [{"kind": "chart", "template": "flowchart", "diagram": {"nodes": []}}],
}


# -- what the shipped rules are -----------------------------------------------------


def test_every_shipped_rule_file_is_present():
    assert design.missing() == []
    assert design.SKILLS == (
        "fp-design-system",
        "fp-design-table",
        "fp-design-chart",
        "fp-design-flowchart",
        "fp-design-reproduce",
    )


def test_the_card_decides_and_the_appendix_keeps_the_guideline_verbatim():
    """The split is what cut the per-document cost: the card is what the model authors,
    the appendix is the frame arithmetic the renderer draws. Neither is a summary."""
    index = design.load("fp-design-system")["rules"]
    table = design.load("fp-design-table")["rules"]
    chart = design.load("fp-design-chart")["rules"]
    flow = design.load("fp-design-flowchart")["rules"]
    # Decisions, verbatim from the source guideline.
    assert "MINIMUM size is 24 (never 22)" in index
    assert "red → Coral/500 #D2705E = Semantic/Negative" in index
    assert "Clone the Frame Guide (209:3364) and use its existing chrome and background." in index
    assert "Don't delete the FOUR PILLARS watermark" in index
    assert "Don't shrink columns to text width — full 1696px unless asked." in table
    assert "Don't make a multi-series chart monochrome." in chart
    assert "Two bars per row (before/after, two dates) is `template:'bar'`" in chart
    assert "Count the COLORS in the sample, not the boxes." in flow
    # The renderer's own geometry is still shipped, one call away, unchanged.
    system_appendix = design.appendix("fp-design-system")["rules"]
    chart_appendix = design.appendix("fp-design-chart")["rules"]
    assert "Gap between the title and the infographic is 98px" in system_appendix
    assert "bottom red band 164px, sides 112px" in system_appendix
    assert "Text: Pretendard Bold 28 / line-height 38, Text/White." in design.appendix("fp-design-table")["rules"]
    assert "X-axis category labels: Pretendard Medium 26, Text/Grey 2, slanted (~48°)." in chart_appendix
    assert "bar / stacked / area → square (14×14, corner 3)" in chart_appendix
    flow_appendix = design.appendix("fp-design-flowchart")["rules"]
    assert "Boxes: text-box padding 24 vertical / 40 horizontal, gap 16, corner radius 10." in flow_appendix
    assert "Every arrow is a pen vector with a V-arrowhead" in flow_appendix
    # The redraw rules are all decision, so there is nothing to move out of the card.
    assert "Don't treat a pasted diagram as inspiration for a better one." in design.load(
        "fp-design-reproduce")["rules"]
    with pytest.raises(DesignRulesError, match="no appendix"):
        design.appendix("fp-design-reproduce")


def test_fp_design_rules_tool_returns_rules_and_digest(tmp_path):
    tools = _tools(tmp_path)
    default = tools["fp_design_rules"]()
    assert default["name"] == "fp-design-system"
    assert default["digest"] == design.digest("fp-design-system")
    assert "Frame & background" in default["rules"]
    chart = tools["fp_design_rules"]("fp-design-chart")
    assert chart["digest"] != default["digest"]
    # The appendix is the same document under the same digest, served on request only.
    book = tools["fp_design_rules"]("fp-design-table", appendix=True)
    assert book["part"] == "appendix"
    assert book["digest"] == design.digest("fp-design-table")
    assert "Corner radius 16, clip content." in book["rules"]
    assert "Corner radius 16, clip content." not in tools["fp_design_rules"]("fp-design-table")["rules"]
    with pytest.raises(DesignRulesError, match="Unknown design skill"):
        tools["fp_design_rules"]("fp-design-poster")


# -- routing: which rules a document is subject to ----------------------------------


def test_required_rules_follow_the_grammars_in_the_document():
    assert design.required({"title": "x"}) == ["fp-design-system"]
    assert design.required(TABLE_DOC) == ["fp-design-system", "fp-design-table"]
    assert design.required(CHART_DOC) == ["fp-design-system", "fp-design-chart"]
    assert design.required(FLOW_DOC) == ["fp-design-system", "fp-design-flowchart"]
    mixed = {"title": "x", "blocks": TABLE_DOC["blocks"] + CHART_DOC["blocks"]}
    assert design.required(mixed) == [
        "fp-design-system",
        "fp-design-table",
        "fp-design-chart",
    ]


def test_an_unclassified_grammar_does_not_escape_the_gate():
    # A future template id must inherit the diagram rules rather than render ungoverned.
    doc = {"title": "x", "blocks": [{"kind": "chart", "template": "hyper-loop"}]}
    assert design.required(doc) == ["fp-design-system", "fp-design-flowchart"]


# -- the gate ----------------------------------------------------------------------


def test_render_refuses_without_acknowledged_rules(tmp_path):
    render = _tools(tmp_path)["fp_render"]
    with pytest.raises(DesignRulesError, match="Design rules are mandatory"):
        render(json.dumps(CHART_DOC), 0, 0)


def test_render_refuses_when_a_required_grammar_rule_is_missing(tmp_path):
    render = _tools(tmp_path)["fp_render"]
    with pytest.raises(DesignRulesError, match="fp-design-chart"):
        render(json.dumps(CHART_DOC), 0, 0, _acks("fp-design-system"))


def test_editing_either_part_invalidates_a_stale_acknowledgement(tmp_path, monkeypatch):
    # The digest is of the rules' bytes - card AND appendix: change either in the bundle
    # and yesterday's acknowledgement stops being valid instead of quietly passing.
    stale = _acks("fp-design-system", "fp-design-table")
    skills = tmp_path / "skills"

    def stage(amend_card: bool) -> None:
        for name in design.SKILLS:
            folder = skills / name
            folder.mkdir(parents=True, exist_ok=True)
            card = design.skill_path(name).read_bytes()
            (folder / "SKILL.md").write_bytes(
                card + b"\n# amended\n" if amend_card else card
            )
            if name in design.APPENDIX_SKILLS:
                book = design.skill_path(name, "appendix").read_bytes()
                (folder / "APPENDIX.md").write_bytes(
                    book if amend_card else book + b"\n# amended\n"
                )

    for amend_card in (True, False):
        stage(amend_card)
        monkeypatch.setenv("FP_STUDIO_DESIGN_SKILLS", str(skills))
        with pytest.raises(DesignRulesError, match="current content"):
            design.check_acknowledged(TABLE_DOC, json.loads(stale))
        fresh = {name: design.digest(name) for name in design.required(TABLE_DOC)}
        assert design.check_acknowledged(TABLE_DOC, fresh) == [
            "fp-design-system",
            "fp-design-table",
        ]


def test_an_appendix_missing_from_the_bundle_is_a_missing_rule(tmp_path, monkeypatch):
    skills = tmp_path / "half"
    for name in design.SKILLS:
        (skills / name).mkdir(parents=True)
        (skills / name / "SKILL.md").write_bytes(design.skill_path(name).read_bytes())
    monkeypatch.setenv("FP_STUDIO_DESIGN_SKILLS", str(skills))
    assert design.missing() == [f"{name}/APPENDIX.md" for name in design.APPENDIX_SKILLS]
    with pytest.raises(DesignRulesError, match="bundle is incomplete"):
        design.load("fp-design-system")


def test_missing_rules_block_rendering_rather_than_degrade(tmp_path, monkeypatch):
    monkeypatch.setenv("FP_STUDIO_DESIGN_SKILLS", str(tmp_path / "absent"))
    with pytest.raises(DesignRulesError, match="bundle is incomplete"):
        design.load("fp-design-system")


# -- the decidable subset ----------------------------------------------------------


def test_type_scale_is_enforced():
    doc = {
        "title": "x",
        "blocks": [
            {"kind": "text", "text": "a", "size": 22},
            {"kind": "text", "text": "b", "size": 26},
            {"kind": "text", "text": "c", "size": 28},
        ],
    }
    problems = design.violations(doc)
    assert any("minimum text size is 24" in p for p in problems)
    assert any("rules of 4" in p for p in problems)
    assert not design.violations({"title": "x", "blocks": [{"kind": "text", "text": "c", "size": 32}]})


def test_raw_hex_needs_a_recorded_brand_source():
    doc = {"title": "x", "blocks": [{"kind": "text", "text": "a", "color": "#D2705E"}]}
    assert any("raw hex" in p for p in design.violations(doc))
    # A sampled brand colour is allowed, but only with the source the rules demand.
    sampled = {
        **doc,
        "direction": {
            "statement": "brand chart",
            "decisions": [{"target": "accent", "value": "#D2705E", "from": "logo asset 12:34"}],
        },
    }
    assert design.violations(sampled) == []


def test_empty_and_placeholder_frame_fields_are_refused():
    assert any("subtitle is empty" in p for p in design.violations({"title": "x", "subtitle": "  "}))
    assert any("placeholder" in p for p in design.violations({"title": "x", "note": "TBD"}))
    assert any("placeholder" in p for p in design.violations({"title": "H1"}))
    assert any("title (H1) is required" in p for p in design.violations({"blocks": []}))
    # The field simply being absent is the documented way to "delete" it.
    assert design.violations({"title": "Fee comparison"}) == []


def test_a_footer_note_has_to_say_where_it_came_from():
    """The defect: an unrequested line appears across the frame's bottom band.

    A note is legitimate from exactly three origins — the user asked, the source being
    redrawn has one, or illustrative mode requires the label. Anything else is a caption
    the model wrote, and the frame's bottom band is not a place to think out loud.
    """
    invented = {"title": "Fee comparison", "note": "Fees vary by network and volume"}
    assert any("was not asked for" in p and "noteRequest" in p
               for p in design.violations(invented))
    # The user's own request, recorded.
    assert design.violations(
        {**invented, "noteRequest": 'user: "add a note that fees vary"'}) == []
    # The label illustrative mode demands in the visual is not an invented caption.
    assert design.violations({"title": "A", "note": "가상 예시 데이터"}) == []
    assert design.violations({"title": "A", "note": "Illustrative figures"}) == []
    # Geometry still applies to a note that was asked for.
    long_note = {"title": "A", "noteRequest": "they asked", "note": "x" * 81}
    assert any("81 characters" in p for p in design.violations(long_note))


def test_a_redraw_may_only_carry_the_source_s_own_note():
    drawn = {"title": "Networks", "note": "As of Q3, excludes fees",
             "reference": {"source_id": "src", "note": "As of Q3, excludes fees",
                           "blocks": [{"kind": "table"}]}}
    assert [p for p in design.violations(drawn) if "note" in p] == []
    invented = {**drawn, "note": "Fees vary by network"}
    assert any("not in the transcription of the source" in p
               for p in design.violations(invented))
    silent = {"title": "Networks", "note": "Fees vary by network",
              "reference": {"source_id": "src", "blocks": [{"kind": "table"}]}}
    assert any("a redraw adds no footer note of its own" in p
               for p in design.violations(silent))


def test_render_reports_breaches_before_touching_the_renderer(tmp_path):
    render = _tools(tmp_path)["fp_render"]
    doc = {"title": "x", "note": "", "blocks": [{"kind": "text", "text": "a", "size": 22}]}
    with pytest.raises(DesignRulesError) as caught:
        render(json.dumps(doc), 0, 0, _acks("fp-design-system"))
    message = str(caught.value)
    assert "note is empty" in message and "minimum text size is 24" in message
    # Nothing was written: the gate runs before the compiler.
    assert not (tmp_path / "fp").exists()
