"""Pointer edits, so changing one number does not cost the whole document.

Why this exists, measured on a real session: `fp_render` and `fp_research` took the FULL
document/research JSON as arguments. Every save re-sent everything, and every one of
those copies stayed in the transcript, which is replayed on every later model call. Those
two argument streams alone were 42% of ~3.9M input tokens for ONE infographic.

The authoritative source already lives in SQLite, so the model never needed to carry it:
it can name the change instead. An edit is a list of RFC 6901 pointer ops —

    [{"op": "set",    "pointer": "/blocks/2/rows/0/value", "value": 41.2},
     {"op": "append", "pointer": "/blocks/2/rows",         "value": {...}},
     {"op": "remove", "pointer": "/note"}]

— applied to the stored revision under the same revision CAS as a full render.

Strict by design: a pointer that does not resolve is an error, never a silently created
branch. A typo that invents `/blocks/9` must not produce a half-built document, and a
`remove` of something already gone must not read as success.
"""

from __future__ import annotations

import json
from typing import Any

MAX_OPS = 200
# An ops payload is meant to be small; a caller sending a whole document as one `set` is
# using the wrong tool, and the point of this path is the token cost.
MAX_OPS_CHARS = 64_000
OPS = ("set", "remove", "append", "insert")


class PatchError(ValueError):
    """An edit that cannot be applied exactly as written."""


def _unescape(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _parse(pointer: Any) -> list[str]:
    if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
        raise PatchError(f"Pointer must be '' or start with '/': {pointer!r}")
    if pointer == "":
        return []
    return [_unescape(token) for token in pointer.split("/")[1:]]


def _descend(doc: Any, tokens: list[str], pointer: str) -> Any:
    node = doc
    for token in tokens:
        if isinstance(node, dict):
            if token not in node:
                raise PatchError(f"No such path: {pointer}")
            node = node[token]
        elif isinstance(node, list):
            if not token.lstrip("-").isdigit():
                raise PatchError(f"List index expected in {pointer}, got {token!r}")
            index = int(token)
            if not -len(node) <= index < len(node):
                raise PatchError(f"Index out of range in {pointer}")
            node = node[index]
        else:
            raise PatchError(f"Cannot descend into a scalar at {pointer}")
    return node


def _child_index(node: list, token: str, pointer: str, *, bound: int) -> int:
    if not token.lstrip("-").isdigit():
        raise PatchError(f"List index expected in {pointer}, got {token!r}")
    index = int(token)
    if index < 0:
        index += len(node)
    if not 0 <= index < bound:
        raise PatchError(f"Index out of range in {pointer}")
    return index


def apply_ops(document: Any, ops: Any) -> Any:
    """`document` with `ops` applied, as a fresh value. Never mutates the input."""
    if not isinstance(ops, list) or not ops:
        raise PatchError("Edits require a non-empty list of ops")
    if len(ops) > MAX_OPS:
        raise PatchError(f"At most {MAX_OPS} ops per edit")
    if len(json.dumps(ops, ensure_ascii=False)) > MAX_OPS_CHARS:
        raise PatchError(
            "Ops payload is too large — an edit names a change; use fp_render to "
            "replace a whole document"
        )
    out = json.loads(json.dumps(document))  # deep copy, and rejects non-JSON values
    for position, op in enumerate(ops):
        if not isinstance(op, dict) or set(op) - {"op", "pointer", "value"}:
            raise PatchError(f"Op {position}: fields are op, pointer and value only")
        kind = op.get("op")
        if kind not in OPS:
            raise PatchError(f"Op {position}: op must be one of {', '.join(OPS)}")
        pointer = op.get("pointer", "")
        tokens = _parse(pointer)
        has_value = "value" in op
        if kind in ("set", "append", "insert") and not has_value:
            raise PatchError(f"Op {position}: {kind} requires a value")
        if kind == "remove" and has_value:
            raise PatchError(f"Op {position}: remove takes no value")

        if kind == "append":
            target = _descend(out, tokens, pointer)
            if not isinstance(target, list):
                raise PatchError(f"append needs a list at {pointer}")
            target.append(op["value"])
            continue

        if not tokens:
            if kind == "set" and isinstance(op["value"], dict):
                out = json.loads(json.dumps(op["value"]))
                continue
            raise PatchError("The document root can only be replaced by an object")

        parent = _descend(out, tokens[:-1], pointer)
        leaf = tokens[-1]
        if isinstance(parent, dict):
            if kind == "insert":
                raise PatchError(f"insert needs a list at {pointer}")
            if kind == "remove":
                if leaf not in parent:
                    raise PatchError(f"No such path: {pointer}")
                del parent[leaf]
            else:
                parent[leaf] = op["value"]
        elif isinstance(parent, list):
            if kind == "insert":
                index = _child_index(parent, leaf, pointer, bound=len(parent) + 1)
                parent.insert(index, op["value"])
            elif kind == "remove":
                del parent[_child_index(parent, leaf, pointer, bound=len(parent))]
            else:
                parent[_child_index(parent, leaf, pointer, bound=len(parent))] = op["value"]
        else:
            raise PatchError(f"Cannot edit a child of a scalar at {pointer}")
    return out


def outline(document: Any, *, limit: int = 40) -> list[dict[str, Any]]:
    """A structural map of a document: enough to aim an edit, without the content.

    This is what `fp_inspect` returns instead of the document itself — the old payload
    echoed the whole source on every inspect, and inspect runs before every edit.
    """
    rows: list[dict[str, Any]] = []
    if not isinstance(document, dict):
        return rows
    blocks = document.get("blocks")
    if not isinstance(blocks, list):
        return rows
    for index, block in enumerate(blocks[:limit]):
        if not isinstance(block, dict):
            rows.append({"pointer": f"/blocks/{index}", "kind": type(block).__name__})
            continue
        row: dict[str, Any] = {"pointer": f"/blocks/{index}", "kind": block.get("kind")}
        for key in ("template", "title", "heading", "name", "variant"):
            value = block.get(key)
            if isinstance(value, str) and value:
                row[key] = value[:80]
        for key in ("rows", "items", "columns", "blocks"):
            value = block.get(key)
            if isinstance(value, list):
                row[f"{key}_count"] = len(value)
        if isinstance(block.get("diagram"), dict):
            diagram = block["diagram"]
            row["diagram"] = {
                "nodes": len(diagram.get("nodes") or []),
                "edges": len(diagram.get("edges") or []),
            }
        rows.append(row)
    if len(blocks) > limit:
        rows.append({"note": f"{len(blocks) - limit} more blocks; read with fp_source"})
    return rows
