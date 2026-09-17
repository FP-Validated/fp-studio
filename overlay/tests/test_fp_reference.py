"""Reproduce mode: a source the user supplies is redrawn, not reinterpreted.

The failure this suite exists for is silent and pretty: the user attaches a chart — or
pastes an ASCII architecture diagram — asks for it "in our design", and gets a different
picture. A grammar the model preferred, a four-level topology flattened into two rows of
peers, an arrow pointing the other way, a summary card the source never had, a rounded
value, a punchier label. None of that is visible in a diff; it is only visible if you
hold the source next to the render.

So the checks here are the ones a machine can make: the document declares which captured
source it redraws, and its grammar, block sequence, graph, values and labels all come
from the transcription of that source — and a supplied source can no longer be ignored
without saying so in writing.
"""

import base64
import copy
import json
import struct
import zlib

import pytest

from coworker.fp import design, reference
from coworker.fp.common import dumps
from coworker.fp.rendering import RenderController
from coworker.fp.store import Store
from coworker.tools.fp import WRITE_TOOLS, fp_tools

from test_fp_core_v03 import acknowledge, rendered


def png_bytes(width: int = 640, height: int = 360, tint: int = 0) -> bytes:
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    raw = (b"\x00" + bytes([tint, 0, 0, 255]) * width) * height
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))


@pytest.fixture
def tools(tmp_path, monkeypatch):
    monkeypatch.setattr(RenderController, "run",
                        lambda self, value, workspace, **kw: rendered(value.get("title", "x")))
    funcs = {fn.__name__: fn for fn in fp_tools(tmp_path)}
    render = funcs["fp_render"]

    def render_with_rules(input_json, rev, research_rev, design_rules="", **kw):
        return render(input_json, rev, research_rev, design_rules or acknowledge(input_json), **kw)

    funcs["fp_render"] = render_with_rules
    funcs["_workspace"] = tmp_path
    return funcs


def captured(tmp_path) -> dict:
    return reference.capture_image(Store(tmp_path), png_bytes(), "attachment:quarterly.png")


# The user's own paste, trimmed: four levels, not two rows of peers.
ASCII_DIAGRAM = """\
                         [1] Protocol
                       Arbitrum One
                           ▲
                           │
                    indexer-agent
                           │
              ┌────────────┴────────────┐
              │     Our GRT Indexer     │
              │ Graph Node + PostgreSQL │
              └────────────┬────────────┘
                           │
                  blockchain data
                           ▼
                    [2] Data Chains
"""


def redraw(source_id: str, **overrides) -> dict:
    """A faithful redraw of a two-series bar chart the image shows."""
    document = {
        "title": "Quarterly revenue",
        "reference": {
            "source_id": source_id,
            "blocks": [{
                "kind": "chart", "template": "bar",
                "categories": ["Q1", "Q2", "Q3"],
                "series": [{"label": "Direct", "values": [41.2, 38.0, 44.5]},
                           {"label": "Partner", "values": [12.5, 19.0, 17.5]}],
            }],
            "title": "Quarterly revenue",
        },
        "blocks": [{
            "kind": "chart", "template": "bar",
            "categories": ["Q1", "Q2", "Q3"],
            "series": [{"label": "Direct", "values": [41.2, 38.0, 44.5]},
                       {"label": "Partner", "values": [12.5, 19.0, 17.5]}],
        }],
    }
    document.update(overrides)
    return document


# -- capturing the image ------------------------------------------------------------


def test_capture_writes_one_file_and_a_receipt_that_pins_its_bytes(tmp_path):
    receipt = captured(tmp_path)
    assert receipt["kind"] == "image" and receipt["mime"] == "image/png"
    assert receipt["width"] == 640 and receipt["height"] == 360
    stored = tmp_path / receipt["file"]
    assert stored.is_file() and stored.read_bytes() == png_bytes()
    assert receipt["image_sha256"] == __import__("hashlib").sha256(png_bytes()).hexdigest()


def test_capturing_the_same_image_twice_is_one_source(tmp_path):
    first = captured(tmp_path)
    second = captured(tmp_path)
    assert first["id"] == second["id"]
    assert len(reference.reference_sources(Store(tmp_path))) == 1


def test_a_file_that_is_not_an_image_is_refused(tmp_path):
    with pytest.raises(reference.ReferenceError):
        reference.capture_image(Store(tmp_path), b"%PDF-1.7 not an image", "attachment:x.pdf")


def test_a_turn_captures_images_and_pasted_structures_and_skips_bad_ones(tmp_path):
    receipts = reference.capture_turn(tmp_path, "here is the stack:\n" + ASCII_DIAGRAM, [
        {"kind": "image", "name": "chart.png",
         "data_url": "data:image/png;base64," + base64.b64encode(png_bytes()).decode()},
        {"kind": "image", "name": "broken.png", "data_url": "data:image/png;base64,!!!not-base64"},
        {"kind": "text", "name": "notes.txt", "data_url": "data:text/plain;base64,aGk="},
        "not-a-dict",
    ])
    assert [r["locator"] for r in receipts] == ["attachment:chart.png", "pasted:ascii-diagram-1"]
    rows = reference.reference_sources(Store(tmp_path))
    assert sorted(r["kind"] for r in rows) == ["image", "structure"]
    # The paste is readable evidence, not an opaque descriptor.
    text = Store(tmp_path).source(receipts[1]["id"])["text"]
    assert "indexer-agent" in text and receipts[1]["form"] == "ascii-diagram"


def test_the_image_the_model_receives_is_the_image_the_gate_captures(tmp_path):
    """One attachment dict, both consumers.

    The composer sends `data_url`; `build_user_content` keys off that field when it builds
    the model turn. Capture used to read `url`/`dataUrl`, names nothing sends, so a real
    attached image reached the model while the redraw gate saw no source and the agent
    asked the user to attach the file again. This test fails if the two paths ever read
    different fields again.
    """
    from coworker.attachments import build_user_content

    attachment = {"kind": "image", "name": "table.png",
                  "data_url": "data:image/png;base64," + base64.b64encode(png_bytes()).decode()}
    parts = build_user_content("redraw this in our design", [attachment])
    assert [p["type"] for p in parts] == ["text", "image_url"]
    receipts = reference.capture_turn(tmp_path, "redraw this in our design", [attachment])
    assert [r["locator"] for r in receipts] == ["attachment:table.png"]
    rows = reference.reference_sources(Store(tmp_path))
    assert [r["kind"] for r in rows] == ["image"]


def test_prose_and_pasted_code_are_not_mistaken_for_a_diagram(tmp_path):
    prose = ("We should show how the indexer works.\n"
             "It stakes, it serves queries, and it settles.\n"
             "Make it look like our other decks.\n")
    code = ("def rank(nodes: list[str], edges: list[str]) -> dict[str, int]:\n"
            "    order = {n: 0 for n in nodes}\n"
            "    return order  # a | b -> c\n")
    assert reference.detect_structures(prose) == []
    assert reference.detect_structures(code) == []
    assert reference.capture_turn(tmp_path, prose + code, []) == []


def test_a_mermaid_fence_and_a_markdown_table_are_both_structures():
    mermaid = "see below\n\n```mermaid\ngraph TD\n  A --> B\n  B --> C\n```\n"
    table = "| chain | share |\n| --- | --- |\n| Ethereum | 41 |\n| Base | 22 |\n"
    assert [s["form"] for s in reference.detect_structures(mermaid)] == ["mermaid"]
    assert [s["form"] for s in reference.detect_structures(table)] == ["table"]


# -- the rules that apply ------------------------------------------------------------


def test_a_reference_makes_the_redraw_rules_mandatory(tmp_path):
    assert design.REPRODUCE_SKILL in design.required(redraw("src_x"))
    assert design.REPRODUCE_SKILL not in design.required({"title": "t", "blocks": []})


def test_a_redraw_without_the_redraw_rules_is_refused(tools, tmp_path):
    document = redraw(captured(tmp_path)["id"])
    partial = dumps({n: design.digest(n) for n in design.required(document)
                     if n != design.REPRODUCE_SKILL})
    with pytest.raises(design.DesignRulesError, match=design.REPRODUCE_SKILL):
        tools["fp_render"](dumps(document), 0, 0, partial)


# -- what a redraw may not do ---------------------------------------------------------


def test_a_faithful_redraw_commits_and_the_receipt_pins_the_image(tools, tmp_path):
    receipt = captured(tmp_path)
    out = tools["fp_render"](dumps(redraw(receipt["id"])), 0, 0)
    assert out["ok"] and out["committed"]
    pinned = out["receipt"]["reference"]
    assert pinned["source_id"] == receipt["id"]
    assert pinned["image_sha256"] == receipt["image_sha256"]
    assert pinned["blocks"] == ["chart:bar"]
    assert "reproduce mode" in " ".join(out["checked"])


def test_a_value_the_image_does_not_show_is_refused(tools, tmp_path):
    document = redraw(captured(tmp_path)["id"])
    document["blocks"][0]["series"][0]["values"][1] = 39.0   # "about 38" rounded up
    with pytest.raises(design.DesignRulesError, match="not in the transcription"):
        tools["fp_render"](dumps(document), 0, 0)


def test_re_routing_to_a_grammar_the_model_prefers_is_refused(tools, tmp_path):
    document = redraw(captured(tmp_path)["id"])
    document["blocks"][0]["template"] = "line"
    with pytest.raises(design.DesignRulesError, match="keep the source's blocks"):
        tools["fp_render"](dumps(document), 0, 0)


def test_an_added_block_the_image_does_not_have_is_refused(tools, tmp_path):
    document = redraw(captured(tmp_path)["id"])
    document["blocks"].append({"kind": "kpi", "label": "Growth", "value": 44.5})
    with pytest.raises(design.DesignRulesError, match="keep the source's blocks"):
        tools["fp_render"](dumps(document), 0, 0)


def test_renaming_a_label_is_refused(tools, tmp_path):
    document = redraw(captured(tmp_path)["id"])
    document["blocks"][0]["series"][1]["label"] = "Channel partners"
    with pytest.raises(design.DesignRulesError, match="not in the transcription"):
        tools["fp_render"](dumps(document), 0, 0)


def test_the_visual_system_is_still_the_fork_s_own(tools, tmp_path):
    """Reproduce mode keeps the source's content — never its raw colours or type sizes."""
    document = redraw(captured(tmp_path)["id"])
    document["blocks"][0]["color"] = "#FF3366"
    with pytest.raises(design.DesignRulesError, match="raw hex"):
        tools["fp_render"](dumps(document), 0, 0)
    document["blocks"][0].pop("color")
    document["blocks"][0]["size"] = 18
    with pytest.raises(design.DesignRulesError, match="minimum text size"):
        tools["fp_render"](dumps(document), 0, 0)


# -- the reference itself must be real ------------------------------------------------


def test_a_reference_without_a_transcription_is_refused(tools, tmp_path):
    document = redraw(captured(tmp_path)["id"])
    document["reference"].pop("blocks")
    with pytest.raises(design.DesignRulesError, match="reference.blocks"):
        tools["fp_render"](dumps(document), 0, 0)


def test_an_unknown_source_id_is_refused(tools, tmp_path):
    with pytest.raises(ValueError, match="Unknown captured source"):
        tools["fp_render"](dumps(redraw("src_nothing")), 0, 0)


def test_a_web_source_cannot_pose_as_the_redrawn_reference(tools, tmp_path):
    text = Store(tmp_path).capture("https://example.test/a", "Direct 41.2",
                                   {"kind": "web_fetch", "origin": "transport", "truncated": False})
    with pytest.raises(reference.ReferenceError, match="not a captured reference"):
        tools["fp_render"](dumps(redraw(text["id"])), 0, 0)


# -- reaching the source from the conversation ----------------------------------------


def test_inspect_offers_the_supplied_source_before_anything_is_rendered(tools, tmp_path):
    receipt = captured(tmp_path)
    out = tools["fp_inspect"]()
    assert out["exists"] is False
    assert [i["source_id"] for i in out["references"]] == [receipt["id"]]
    assert [i["kind"] for i in out["references"]] == ["image"]
    assert "Redraw the supplied source" in out["notice"]
    assert json.dumps(out["references"]).count("base64") == 0


# -- the wiring is the content --------------------------------------------------------


def graph_redraw(source_id: str) -> dict:
    """A faithful redraw of the pasted stack: three levels, two directed edges."""
    nodes = [{"id": "agent", "label": "indexer-agent", "group": "ours"},
             {"id": "chain", "label": "Arbitrum One", "group": "protocol"},
             {"id": "data", "label": "Data Chains", "group": "chains"}]
    edges = [{"from": "agent", "to": "chain"}, {"from": "agent", "to": "data"}]
    # The document's own copy, so a test that rewires the render does not also rewrite
    # the transcription it is checked against.
    return {
        "title": "Our GRT Indexer",
        "template": "flowchart",
        "reference": {
            "source_id": source_id,
            "blocks": [{"kind": "diagram", "template": "flowchart",
                        "nodes": nodes, "edges": edges}],
        },
        "diagram": copy.deepcopy({"nodes": nodes, "edges": edges}),
    }


def pasted(tmp_path) -> dict:
    return reference.capture_structure(
        Store(tmp_path), ASCII_DIAGRAM, "pasted:ascii-diagram-1", "ascii-diagram")


def test_a_faithful_redraw_of_a_pasted_diagram_renders(tools, tmp_path):
    out = tools["fp_render"](dumps(graph_redraw(pasted(tmp_path)["id"])), 0, 0)
    assert out["committed"] is True
    committed = out["receipt"]["reference"]
    assert committed["kind"] == "structure" and committed["form"] == "ascii-diagram"
    assert committed["graph"] == {"nodes": 3, "edges": 2}
    assert committed["structure_sha256"] == pasted(tmp_path)["structure_sha256"]


def test_a_reversed_arrow_is_refused(tools, tmp_path):
    document = graph_redraw(pasted(tmp_path)["id"])
    document["diagram"]["edges"][0] = {"from": "chain", "to": "agent"}
    with pytest.raises(design.DesignRulesError, match="point the wrong way"):
        tools["fp_render"](dumps(document), 0, 0)


def test_dropping_a_node_or_rewiring_the_flow_is_refused(tools, tmp_path):
    source_id = pasted(tmp_path)["id"]
    document = graph_redraw(source_id)
    document["diagram"]["nodes"] = document["diagram"]["nodes"][:2]
    document["diagram"]["edges"] = [{"from": "agent", "to": "chain"}]
    with pytest.raises(design.DesignRulesError, match="drops"):
        tools["fp_render"](dumps(document), 0, 0)

    invented = graph_redraw(source_id)
    invented["diagram"]["edges"].append({"from": "chain", "to": "data"})
    with pytest.raises(design.DesignRulesError, match="invents connections"):
        tools["fp_render"](dumps(invented), 0, 0)


def test_a_supplied_source_cannot_be_quietly_ignored(tools, tmp_path):
    """The defect this exists for: a pasted diagram routed into a new composition."""
    pasted(tmp_path)
    invented = {"title": "Our GRT Indexer", "template": "flowchart",
                "diagram": {"nodes": [{"id": "a", "label": "indexer-agent", "group": "ours"},
                                      {"id": "b", "label": "Data Chains", "group": "chains"},
                                      {"id": "c", "label": "The Graph Gateway", "group": "query"}],
                            "edges": [{"from": "a", "to": "b"}]}}
    with pytest.raises(ValueError, match="supplied a source to redraw"):
        tools["fp_render"](dumps(invented), 0, 0)

    # Composing something else is allowed — in the user's words, on the record.
    invented["referenceWaiver"] = "user: forget the sketch, show me the revenue split"
    out = tools["fp_render"](dumps(invented), 0, 0)
    assert out["committed"] is True


def test_capture_image_tool_reads_a_granted_file_and_re_reads_a_capture(tools, tmp_path):
    path = tmp_path / "board.png"
    path.write_bytes(png_bytes(320, 200, tint=7))
    captured_file = tools["fp_capture_image"](path="board.png")
    assert captured_file["kind"] == "image" and captured_file["width"] == 320
    again = tools["fp_capture_image"](source_id=captured_file["id"])
    assert again["id"] == captured_file["id"] and "text" not in again
    with pytest.raises(ValueError, match="outside the session's granted roots"):
        tools["fp_capture_image"](path="/etc/hosts")


def test_the_new_write_tool_is_risk_classified_and_root_scoped():
    from coworker import permissions, risk
    assert "fp_capture_image" in WRITE_TOOLS
    assert risk.classify("fp_capture_image") is risk.RiskClass.WRITE_LOCAL
    paths, located = permissions.write_paths("fp_capture_image", {"name": "infographic"})
    assert located and paths
