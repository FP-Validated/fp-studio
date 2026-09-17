"""Reproduce mode: when the user hands over a source, the job is to REDRAW it.

The normal FP path composes from meaning: read the content, choose the grammar the
relationship needs, compose. That is right when the user brings facts and a message. It
is wrong when the user brings a picture - or pastes a diagram, a table, a mermaid graph -
and says "make this in our design": there the source already decided the grammar, the
nodes, the order, the wiring and the copy, and the only thing that may change is the
visual system (type scale, palette, spacing, vector style).

A structure pasted as text is exactly as much a source as an attached PNG. Treating only
the PNG as one is what let a pasted ASCII architecture diagram be "routed" into a new
composition with different levels and different edges, which is not a redraw.

Asking a model to be faithful is not enough; the failure mode is a beautiful chart of
different numbers. So a supplied source is captured with a receipt, the document carries
a `reference` block transcribing what that source actually shows, and the render gate
checks the parts that are decidable:

  * the grammar is the one the transcription read, not one the model preferred,
  * the block sequence matches the source's block sequence,
  * every data value in the output appears in the transcription,
  * every category/series label in the output appears in the transcription,
  * the graph the output draws has the transcription's nodes and its directed edges -
    nothing dropped, nothing invented, nothing reversed,
  * a captured source is either transcribed or explicitly waived in the user's words;
    it can no longer be quietly ignored.

What stays human: whether the transcription itself is a correct reading of the source.
The rules say transcribe, the receipt says which source, and the user reviews the result.
"""

from __future__ import annotations

import base64
import binascii
from pathlib import Path
import re
import struct
from typing import Any, Iterable

from .common import digest
from .store import Store

# Attachments are persisted here, inside the session workspace, so a reference has a file
# and a receipt rather than a base64 blob living in the transcript forever.
ATTACHMENT_DIR = "fp/attachments"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MIME_SUFFIX = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}
# Keys whose numbers are DATA (what the source measured) rather than presentation.
DATA_KEYS = frozenset({
    "value", "values", "y", "y2", "amount", "count", "percent", "share", "total",
    "delta", "min", "max", "target", "from", "to",
})
# Keys whose strings NAME something the source named.
LABEL_KEYS = frozenset({
    "label", "labels", "category", "categories", "name", "series", "legend", "axis",
})
_WS = re.compile(r"\s+")

# -- what counts as a structure the user pasted -------------------------------------
# Deliberately narrow. A false positive blocks a render until the author waives it, so
# the marks below are ones that effectively never occur in prose or in pasted code:
# box-drawing and arrow glyphs, an ASCII box rule (`+---`), a markdown table separator,
# or a fence that names a diagram language.
BOX_GLYPHS = "─│┌┐└┘├┤┬┴┼━┃┏┓┗┛╔╗╚╝║═╭╮╰╯▲▼◀▶◄►←→↑↓⇒⟶"
_FENCE = re.compile(r"```[ \t]*([A-Za-z-]*)[ \t]*\r?\n(.*?)```", re.S)
_DIAGRAM_LANGS = {"mermaid": "mermaid", "dot": "graphviz", "graphviz": "graphviz",
                  "flow": "ascii-diagram", "ascii": "ascii-diagram"}
_ASCII_RULE = re.compile(r"[+|][-=]{2,}")
_TABLE_RULE = re.compile(r"^\s*\|?[\s:|-]*-{3,}[\s:|-]*\|?\s*$")
MAX_STRUCTURES = 4
MAX_STRUCTURE_CHARS = 16_000
MIN_STRUCTURE_LINES = 3


class ReferenceError(ValueError):
    """The document claims to reproduce a source but does not."""


# -- capturing the image ------------------------------------------------------------


def _png_size(data: bytes) -> tuple[int, int] | None:
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)


def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB):
            height, width = struct.unpack(">HH", data[i + 5:i + 9])
            return int(width), int(height)
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        (length,) = struct.unpack(">H", data[i + 2:i + 4])
        i += 2 + length
    return None


def image_shape(data: bytes) -> dict[str, Any]:
    """Format and pixel size, read from the file header - no image library."""
    for mime, reader in (("image/png", _png_size), ("image/jpeg", _jpeg_size)):
        size = reader(data)
        if size:
            return {"mime": mime, "width": size[0], "height": size[1]}
    if data[:6] in (b"GIF87a", b"GIF89a"):
        width, height = struct.unpack("<HH", data[6:10])
        return {"mime": "image/gif", "width": int(width), "height": int(height)}
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return {"mime": "image/webp"}
    raise ReferenceError("Reference must be a PNG, JPEG, GIF or WebP image")


def capture_image(store: Store, data: bytes, locator: str, origin: str = "attachment") -> dict:
    """Persist the image beside the workspace and record it as a captured source.

    The source row keeps a descriptor, not the pixels: the bytes live in one file, the
    receipt pins their sha256, and the transcript carries neither.
    """
    if not data:
        raise ReferenceError("Reference image is empty")
    if len(data) > MAX_IMAGE_BYTES:
        raise ReferenceError(
            f"Reference image exceeds {MAX_IMAGE_BYTES // (1024 * 1024)} MiB"
        )
    shape = image_shape(data)
    sha = digest(data)
    suffix = MIME_SUFFIX.get(shape["mime"], ".bin")
    path = store.root / ATTACHMENT_DIR / f"{sha[:16]}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_bytes(data)
    descriptor = (
        f"image {shape['mime']} sha256={sha} bytes={len(data)} "
        + " ".join(f"{k}={shape[k]}" for k in ("width", "height") if k in shape)
        + f" file={path.relative_to(store.root)}"
    )
    return store.capture(
        locator,
        descriptor,
        {
            "kind": "image",
            "origin": origin,
            "truncated": False,
            "image_sha256": sha,
            "file": str(path.relative_to(store.root)),
            **shape,
        },
    )


def detect_structures(text: Any) -> list[dict[str, str]]:
    """Diagrams/tables pasted into a message, as {form, text} in reading order.

    A user who pastes an ASCII architecture diagram has already drawn the thing. The
    detector stays conservative on purpose: a fenced diagram language, box-drawing or
    arrow glyphs, an ASCII box rule, or a markdown table separator. Prose and ordinary
    pasted code carry none of those.
    """
    if not isinstance(text, str) or not text.strip():
        return []
    found: list[dict[str, str]] = []
    rest: list[str] = []
    at = 0
    for match in _FENCE.finditer(text):
        rest.append(text[at:match.start()])
        at = match.end()
        lang = _DIAGRAM_LANGS.get(match.group(1).strip().lower())
        body = match.group(2)
        if lang:
            found.append({"form": lang, "text": body})
        else:
            # An unlabelled fence still holds a diagram often enough to look inside.
            rest.append(body)
    rest.append(text[at:])

    for chunk in re.split(r"\n[ \t]*\n", "\n".join(rest)):
        lines = [line for line in chunk.splitlines() if line.strip()]
        if len(lines) < MIN_STRUCTURE_LINES:
            continue
        glyphs = sum(chunk.count(g) for g in BOX_GLYPHS)
        glyph_lines = sum(1 for line in lines if any(g in line for g in BOX_GLYPHS))
        pipes = [line for line in lines if line.count("|") >= 2]
        if glyphs >= 4 and glyph_lines >= 2:
            form = "ascii-diagram"
        elif len(_ASCII_RULE.findall(chunk)) >= 2:
            form = "ascii-diagram"
        elif len(pipes) >= 3 and any(_TABLE_RULE.match(line) for line in lines):
            form = "table"
        else:
            continue
        found.append({"form": form, "text": chunk.strip("\n")})
    return found[:MAX_STRUCTURES]


def capture_structure(store: Store, text: str, locator: str, form: str,
                      origin: str = "message") -> dict:
    """Persist a pasted structure as a captured source, text and all.

    Unlike an image the bytes ARE readable, so the source row keeps them: the author can
    quote the paste with fp_source_text and the receipt pins exactly what was pasted.
    """
    body = text.strip("\n")
    if not body.strip():
        raise ReferenceError("Reference structure is empty")
    if len(body) > MAX_STRUCTURE_CHARS:
        raise ReferenceError(f"Reference structure exceeds {MAX_STRUCTURE_CHARS} characters")
    sha = digest(body.encode("utf-8"))
    path = store.root / ATTACHMENT_DIR / f"{sha[:16]}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_text(body, encoding="utf-8")
    return store.capture(
        locator,
        body,
        {
            "kind": "structure",
            "form": form,
            "origin": origin,
            "truncated": False,
            "structure_sha256": sha,
            "lines": len(body.splitlines()),
            "file": str(path.relative_to(store.root)),
        },
    )


def capture_turn(workspace: str | Path, text: Any, attachments: Iterable[Any]) -> list[dict]:
    """Capture every source of one user turn - images AND pasted structures.

    Called from the server as a message is accepted. Never raises into the chat: a
    capture failure must not stop the user's message from being delivered.
    """
    out: list[dict] = []
    try:
        store = Store(workspace)
    except Exception:
        return out
    for index, attachment in enumerate(attachments or []):
        if not isinstance(attachment, dict):
            continue
        # `data_url` is what the composer and `build_user_content` use — capture MUST key
        # off the same field the model call does, or an attached image reaches the model
        # while the redraw gate sees no source at all and asks the user to re-attach it.
        url = (attachment.get("data_url") or attachment.get("url")
               or attachment.get("dataUrl") or "")
        if not isinstance(url, str) or not url.startswith("data:image/"):
            continue
        head, _, payload = url.partition(";base64,")
        if not payload:
            continue
        try:
            data = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError):
            continue
        name = attachment.get("name") or attachment.get("filename") or f"attachment-{index + 1}"
        try:
            out.append(capture_image(store, data, f"attachment:{name}"))
        except (ReferenceError, ValueError, OSError):
            continue
    try:
        structures = detect_structures(text)
    except Exception:
        structures = []
    for index, item in enumerate(structures):
        try:
            out.append(capture_structure(
                store, item["text"], f"pasted:{item['form']}-{index + 1}", item["form"],
            ))
        except (ReferenceError, ValueError, OSError):
            continue
    return out


def reference_sources(store: Store) -> list[dict]:
    """Every source the user supplied to be redrawn, newest first."""
    return [row for row in store.sources() if row.get("kind") in ("image", "structure")]


def unconsumed(store: Store, value: Any) -> list[str]:
    """Captured references this document neither transcribes nor waives.

    The gate used to be opt-in: a document that simply omitted `reference` escaped
    reproduce mode entirely, which is precisely how a pasted diagram became a new
    invented composition. Now the choice has to be made in writing.
    """
    rows = reference_sources(store)
    if not rows:
        return []
    value = value if isinstance(value, dict) else {}
    if str(value.get("referenceWaiver") or "").strip():
        return []
    used = value.get("reference")
    used_id = str(used.get("source_id")) if isinstance(used, dict) else ""
    return [str(row.get("id")) for row in rows if str(row.get("id")) != used_id]


# -- the transcription --------------------------------------------------------------


def _norm(text: Any) -> str:
    return _WS.sub(" ", str(text)).strip().casefold()


def _numbers(value: Any, keys: frozenset[str], out: list[float], inside: bool = False) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _numbers(item, keys, out, key in keys)
    elif isinstance(value, list):
        for item in value:
            _numbers(item, keys, out, inside)
    elif inside and isinstance(value, (int, float)) and not isinstance(value, bool):
        out.append(float(value))


def _labels(value: Any, keys: frozenset[str], out: list[str], inside: bool = False) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _labels(item, keys, out, key in keys)
    elif isinstance(value, list):
        for item in value:
            _labels(item, keys, out, inside)
    elif inside and isinstance(value, str) and value.strip():
        out.append(_norm(value))


def _shape_of(blocks: Any) -> list[str]:
    rows: list[str] = []
    for block in blocks if isinstance(blocks, list) else []:
        if not isinstance(block, dict):
            rows.append("?")
            continue
        kind = str(block.get("kind") or "?")
        template = block.get("template")
        rows.append(f"{kind}:{template}" if isinstance(template, str) and template else kind)
    return rows


def _graph_of(value: Any, nodes: dict[str, str] | None = None,
              edges: list[tuple[str, str]] | None = None) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Every node id → label and every directed edge reachable in a document or a
    transcription, wherever the graph is declared (`diagram`, a block, a nested one)."""
    nodes = {} if nodes is None else nodes
    edges = [] if edges is None else edges
    if isinstance(value, dict):
        for item in value.get("nodes") if isinstance(value.get("nodes"), list) else []:
            if isinstance(item, dict) and item.get("id") is not None:
                nodes[str(item["id"])] = _norm(item.get("label") or item["id"])
        for item in value.get("edges") if isinstance(value.get("edges"), list) else []:
            if isinstance(item, dict) and item.get("from") is not None and item.get("to") is not None:
                edges.append((str(item["from"]), str(item["to"])))
        for key, item in value.items():
            if key not in ("nodes", "edges"):
                _graph_of(item, nodes, edges)
    elif isinstance(value, list):
        for item in value:
            _graph_of(item, nodes, edges)
    return nodes, edges


def _named(edges: list[tuple[str, str]], nodes: dict[str, str]) -> set[tuple[str, str]]:
    """Edges keyed by node LABEL, so a redraw that renumbers ids still compares."""
    return {(nodes.get(a, _norm(a)), nodes.get(b, _norm(b))) for a, b in edges}


def validate(reference: Any) -> dict:
    """Structural validation of the `reference` block itself."""
    if not isinstance(reference, dict):
        raise ReferenceError("reference must be an object")
    unknown = set(reference) - {"source_id", "blocks", "title", "note", "reading"}
    if unknown:
        raise ReferenceError(
            "reference accepts source_id, blocks, title, note and reading; got "
            + ", ".join(sorted(unknown))
        )
    sid = reference.get("source_id")
    if not isinstance(sid, str) or not sid.strip():
        raise ReferenceError(
            "reference.source_id is required: capture the attached image first, then "
            "name its source id"
        )
    blocks = reference.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise ReferenceError(
            "reference.blocks must transcribe the source's blocks in reading order, "
            "e.g. [{'kind': 'chart', 'template': 'bar', 'categories': [...], "
            "'series': [{'label': ..., 'values': [...]}]}]"
        )
    for block in blocks:
        if not isinstance(block, dict) or not isinstance(block.get("kind"), str):
            raise ReferenceError("every reference block needs a kind read from the image")
    return reference


def _document_shape(value: dict) -> list[str]:
    """The grammar sequence of the DOCUMENT, whether it composes blocks or declares one
    top-level diagram — `{template, diagram}` is the same shape as a `diagram` block."""
    blocks = value.get("blocks")
    if isinstance(blocks, list) and blocks:
        return _shape_of(blocks)
    if isinstance(value.get("diagram"), dict):
        template = value.get("template")
        return [f"diagram:{template}" if isinstance(template, str) and template else "diagram"]
    return []


def fidelity_violations(value: Any) -> list[str]:
    """What a redraw must satisfy, checked against the transcription.

    Only decidable claims: same grammar, same block sequence, the same graph (nodes and
    directed edges), no data value and no category/series label that the transcription
    did not read from the source.
    """
    problems: list[str] = []
    if not isinstance(value, dict):
        return ["FP input must be an object"]
    reference = value.get("reference")
    try:
        validate(reference)
    except ReferenceError as error:
        return [str(error)]
    # Everything the document draws, which is everything except the transcription itself.
    drawn = {k: v for k, v in value.items() if k != "reference"}

    want = _shape_of(reference.get("blocks"))
    got = _document_shape(value)
    if want != got:
        problems.append(
            "the redraw must keep the source's blocks, in order: the source shows "
            + " → ".join(want)
            + " and this document is "
            + (" → ".join(got) or "empty")
            + ". Reproduce mode never re-chooses a grammar or adds a block the source "
            "does not have; ask the user before changing the structure"
        )

    # The wiring IS the content of a diagram: a redraw that re-levels the boxes or
    # re-points an arrow has changed the claim, however good it looks.
    source_nodes, source_edges = _graph_of(reference)
    drawn_nodes, drawn_edges = _graph_of(drawn)
    if source_nodes or drawn_nodes:
        missing = sorted(set(source_nodes.values()) - set(drawn_nodes.values()))
        added = sorted(set(drawn_nodes.values()) - set(source_nodes.values()))
        if missing:
            problems.append(
                "the source has nodes this redraw drops: "
                + ", ".join(repr(n) for n in missing[:12])
                + ". Every box in the source is a box in the redraw"
            )
        if added:
            problems.append(
                "these nodes are not in the transcription of the source: "
                + ", ".join(repr(n) for n in added[:12])
                + ". A redraw adds no box of its own"
            )
        source_wiring = _named(source_edges, source_nodes)
        drawn_wiring = _named(drawn_edges, drawn_nodes)
        lost = sorted(source_wiring - drawn_wiring)
        gained = sorted(drawn_wiring - source_wiring)
        reversed_ = sorted((a, b) for a, b in gained if (b, a) in source_wiring)
        if reversed_:
            problems.append(
                "these arrows point the wrong way: "
                + ", ".join(f"{b} → {a}" for a, b in reversed_[:8])
                + ". Keep the source's direction"
            )
        for label, items in (("drops", lost), ("invents", [e for e in gained if e not in reversed_])):
            if items:
                problems.append(
                    f"the redraw {label} connections: "
                    + ", ".join(f"{a} → {b}" for a, b in items[:8])
                    + ". Don't rewire the flow"
                )

    source_numbers: list[float] = []
    _numbers(reference, DATA_KEYS, source_numbers)
    document_numbers: list[float] = []
    _numbers(drawn, DATA_KEYS, document_numbers)
    invented = sorted({n for n in document_numbers if n not in set(source_numbers)})
    if invented:
        problems.append(
            "these values are not in the transcription of the source: "
            + ", ".join(f"{n:g}" for n in invented[:12])
            + ". Transcribe what the source shows; never fill a gap with a plausible "
            "number"
        )

    source_labels: set[str] = set()
    collected: list[str] = []
    _labels(reference, LABEL_KEYS, collected)
    source_labels.update(collected)
    for key in ("title", "note", "reading"):
        item = reference.get(key)
        if isinstance(item, str):
            source_labels.add(_norm(item))
    document_labels: list[str] = []
    _labels(drawn, LABEL_KEYS, document_labels)
    unread = sorted({
        label for label in document_labels
        if label and not any(label in known for known in source_labels)
    })
    if unread:
        problems.append(
            "these labels are not in the transcription of the source: "
            + ", ".join(repr(label) for label in unread[:12])
            + ". A redraw renames nothing"
        )
    return problems


def receipt(value: Any, store: Store) -> dict | None:
    """The reference receipt to commit with a revision, or None outside reproduce mode."""
    reference = value.get("reference") if isinstance(value, dict) else None
    if reference is None:
        return None
    validate(reference)
    row = store.source(str(reference["source_id"]))
    kind = row.get("kind")
    if kind not in ("image", "structure"):
        raise ReferenceError(
            f"{reference['source_id']} is not a captured reference; reproduce mode needs "
            "the id of the image or the pasted structure being redrawn"
        )
    nodes, edges = _graph_of(reference)
    return {
        "source_id": row.get("id"),
        "kind": kind,
        "form": row.get("form"),
        "image_sha256": row.get("image_sha256"),
        "structure_sha256": row.get("structure_sha256"),
        "file": row.get("file"),
        "locator": row.get("locator"),
        "blocks": _shape_of(reference.get("blocks")),
        "graph": {"nodes": len(nodes), "edges": len(edges)} if nodes else None,
    }
