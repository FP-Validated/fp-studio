"""The rendered artifact is the picture, not its markup.

FP commits an SVG and a PNG for every revision, and the SVG is the authoritative one —
the PNG is derived from it. Upstream classified `.svg` by suffix as text, so the stock
artifact viewer showed the user several thousand lines of `<path d="M0 0L1 1"/>` instead
of their infographic, while the PNG of the same revision rendered fine.

`<img>` is the safe way to show it: an SVG loaded as an image runs no script and fetches
nothing remote, so the viewer gains a picture without gaining a new execution surface.
"""

import base64

from test_server import _client


SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="32">'
    '<title>Quarterly revenue</title><rect width="64" height="32"/></svg>'
)


def test_a_committed_svg_is_served_as_a_rendered_image(tmp_path):
    (tmp_path / "fp").mkdir()
    (tmp_path / "fp/infographic.svg").write_text(SVG, encoding="utf-8")

    client = _client(tmp_path, [])
    listed = {a["path"]: a for a in client.get("/v1/sessions/unknown/artifacts").json()["artifacts"]}
    assert listed["fp/infographic.svg"]["kind"] == "image"

    read = client.get(
        "/v1/sessions/unknown/artifacts/read", params={"path": "fp/infographic.svg"}
    ).json()
    assert read["ok"] is True and read["kind"] == "image"
    head, _, payload = read["data_url"].partition(";base64,")
    assert head == "data:image/svg+xml"
    # The viewer draws exactly the committed bytes — no rewriting, no sanitiser pass.
    assert base64.b64decode(payload).decode("utf-8") == SVG
    assert "content" not in read   # never the markup as text


def test_the_png_of_the_same_revision_is_unchanged(tmp_path):
    (tmp_path / "fp").mkdir()
    (tmp_path / "fp/infographic.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)

    read = _client(tmp_path, []).get(
        "/v1/sessions/unknown/artifacts/read", params={"path": "fp/infographic.png"}
    ).json()
    assert read["kind"] == "image" and read["data_url"].startswith("data:image/png;base64,")


def test_other_markup_is_still_text(tmp_path):
    """Only SVG moved. A source file the user wants to READ must stay readable."""
    (tmp_path / "notes.json").write_text('{"a": 1}', encoding="utf-8")
    (tmp_path / "page.html").write_text("<h1>Preview</h1>", encoding="utf-8")

    client = _client(tmp_path, [])
    notes = client.get("/v1/sessions/unknown/artifacts/read", params={"path": "notes.json"}).json()
    page = client.get("/v1/sessions/unknown/artifacts/read", params={"path": "page.html"}).json()
    assert notes["kind"] == "code" and notes["content"] == '{"a": 1}'
    assert page["kind"] == "html" and "<h1>Preview</h1>" in page["content"]
