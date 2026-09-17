"""Routed access to the FP SDK contracts, so authoring one infographic costs one
grammar's worth of context instead of the whole kit.

The problem this exists for: the kit ships 45 grammars and a 21 KB TypeScript contract
file. Serving that file (even paged) meant every document — a four-row table included —
paid for the schema of every chart, diagram and theme knob the SDK has. ~34 KB of
contracts, ~8.6k tokens, before a single word of the user's content.

The shape here is a two-step route, and the second step is the only way in:

    1. `index()`     — the thin catalog: every grammar as id + intent + triggers +
                       budget + family, plus the block kinds. ~2 KB. This is what a
                       model reads to CHOOSE.
    2. `grammar(id)`  — that ONE grammar's contract: its block variant, the interfaces
                       it actually references, its budget and the design skill that
                       governs it. ~1-2 KB.

There is deliberately no "give me everything" topic. `fp_guide` cannot serve the raw
contract file any more, so a model cannot skip the choice and grep the SDK instead: the
capability is gone, not discouraged. `input()` adds the frame-level fields (title,
source, blocks…) which every document needs regardless of grammar.

Slices are extracted from the kit's own `src/types.ts` at call time — never a copy that
can drift from the pinned compiler.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from .rendering import kit_root

# Which design skill governs each grammar family (same routing `design.py` enforces).
TABLE_SKILL = "fp-design-table"
CHART_SKILL = "fp-design-chart"
DIAGRAM_SKILL = "fp-design-flowchart"
# Families whose members are drawn as charts; everything else that is not a table is a
# diagram, so a grammar added upstream inherits diagram rules instead of no rules.
CHART_FAMILIES = frozenset({"cartesian", "radial", "sequential", "quantity-flow", "grid"})
# Interfaces worth carrying with a block variant. Anything else referenced by name is
# resolved from types.ts automatically.
_DECL = re.compile(
    r"^export (?:interface|type) (?P<name>[A-Z][A-Za-z0-9]*)\b", re.MULTILINE
)
_IDENTIFIER = re.compile(r"\b([A-Z][A-Za-z0-9]*)\b")
# Types that are noise in a slice: enormous unions of ids the index already lists, or
# theme internals the agent never writes.
_SKIP = frozenset({"TemplateId", "Theme", "TextRole", "VectorAsset", "Evidence", "GradientPaint"})


class SdkError(ValueError):
    """The kit is missing, or a grammar id does not exist."""


def _read(relative: str) -> str:
    path = kit_root() / relative
    if not path.is_file():
        raise SdkError(
            f"FP SDK contract is absent in this installation: {relative}. "
            "The bundle is incomplete."
        )
    return path.read_text("utf-8")


@lru_cache(maxsize=1)
def _registry() -> dict[str, Any]:
    return json.loads(_read("templates/registry.json"))


@lru_cache(maxsize=1)
def _types() -> str:
    return _read("src/types.ts")


@lru_cache(maxsize=1)
def _declarations() -> dict[str, str]:
    """`name → full declaration text` for every exported interface/type in types.ts."""
    text = _types()
    spans: list[tuple[str, int]] = [
        (match.group("name"), match.start()) for match in _DECL.finditer(text)
    ]
    out: dict[str, str] = {}
    for index, (name, start) in enumerate(spans):
        end = spans[index + 1][1] if index + 1 < len(spans) else len(text)
        out[name] = text[start:end].rstrip() + "\n"
    return out


@lru_cache(maxsize=1)
def _block_variants() -> dict[str, str]:
    """`kind → the Block union member` (one entry per block kind, multi-line kept)."""
    text = _types()
    start = text.find("export type Block =")
    if start == -1:
        raise SdkError("The kit's Block union is not where the contract says it is")
    end = text.find("\n\n", start)
    union = text[start : end if end != -1 else len(text)]
    out: dict[str, str] = {}
    for chunk in union.split("\n  | ")[1:]:
        match = re.search(r"kind: '([a-z]+)'", chunk)
        if match:
            out[match.group(1)] = "  | " + chunk.rstrip().rstrip(";")
    return out


def _family_of(template: str) -> str:
    for family, members in (_registry().get("families") or {}).items():
        if template in members:
            return family
    return ""


def design_skill_for(template: str) -> str:
    if template == "table":
        return TABLE_SKILL
    return CHART_SKILL if _family_of(template) in CHART_FAMILIES else DIAGRAM_SKILL


def _block_kind_for(template: str) -> str:
    """Which block a grammar is authored through: a table is its own block; every other
    grammar rides the `chart` block and names itself in `template`."""
    return "table" if template == "table" else "chart"


def template_ids() -> list[str]:
    return [row["id"] for row in _registry().get("templates") or [] if row.get("id")]


def index() -> dict[str, Any]:
    """The thin catalog a model reads to CHOOSE a grammar. No schema, no prose."""
    registry = _registry()
    rows = []
    for row in registry.get("templates") or []:
        template = row.get("id")
        if not template:
            continue
        rows.append(
            {
                "id": template,
                "intent": row.get("intent"),
                "trigger": row.get("trigger") or [],
                "budget": row.get("budget") or {},
                "family": _family_of(template),
                # Only a grammar with more than one reading declares styles.
                **({"styles": row["styles"]} if row.get("styles") else {}),
            }
        )
    blocks = registry.get("blocks") or {}
    return {
        "grammars": rows,
        "block_kinds": blocks.get("kinds") or [],
        "note": registry.get("note"),
        "next": "fp_guide('draw', name='<id>[,<id>]') returns those grammars' "
        "contracts, the frame fields and every design rule in ONE call. There is no "
        "whole-SDK topic: choose, then draw.",
    }


def _slice_for(names: list[str]) -> str:
    """Declarations for `names`, plus what they reference, one resolution pass deep."""
    declarations = _declarations()
    wanted: list[str] = []
    seen: set[str] = set()
    frontier = [n for n in names if n in declarations]
    for _pass in range(2):
        nxt: list[str] = []
        for name in frontier:
            if name in seen or name in _SKIP:
                continue
            seen.add(name)
            body = declarations[name]
            wanted.append(body)
            for referenced in _IDENTIFIER.findall(body):
                if (
                    referenced not in seen
                    and referenced not in _SKIP
                    and referenced in declarations
                ):
                    nxt.append(referenced)
        frontier = nxt
    return "\n".join(wanted)


def grammar(template: str) -> dict[str, Any]:
    """ONE grammar's authoring contract: its block variant, the interfaces it uses, its
    editorial budget, and the design rules that govern it."""
    rows = {row.get("id"): row for row in _registry().get("templates") or []}
    row = rows.get(template)
    if row is None:
        raise SdkError(
            f"Unknown grammar: {template!r}. Call fp_guide('vocabulary') for the "
            f"{len(rows)} available ids."
        )
    kind = _block_kind_for(template)
    variant = _block_variants().get(kind, "")
    referenced = [n for n in _IDENTIFIER.findall(variant) if n not in ("BlockBase",)]
    return {
        "id": template,
        "intent": row.get("intent"),
        "trigger": row.get("trigger") or [],
        "budget": row.get("budget") or {},
        "family": _family_of(template),
        # The readings this grammar serves under `style`. Absent means it has one.
        **({"styles": row["styles"]} if row.get("styles") else {}),
        "block_kind": kind,
        "design_skill": design_skill_for(template),
        "contract": (variant + "\n" + _slice_for(referenced)).strip(),
        "note": "Budgets are editorial limits: exceed one by splitting overview and "
        "detail, never by shrinking type.",
    }


def input_contract() -> dict[str, Any]:
    """The frame-level fields every document has, without the 45 grammar variants."""
    declarations = _declarations()
    fp_input = declarations.get("FPInput")
    if not fp_input:
        raise SdkError("The kit's FPInput contract is not where the contract says it is")
    return {
        "contract": fp_input + "\n" + _slice_for(["Direction"]),
        "block_kinds": (_registry().get("blocks") or {}).get("kinds") or [],
        "note": "Blocks are authored one grammar at a time: fp_guide('draw', name).",
    }


def validate_templates(value: Any) -> list[str]:
    """Every grammar named in a document must be one the kit actually serves.

    Returns the offending ids; an unknown grammar is a typo or an invention, and failing
    here beats a compiler error after the model has already claimed a render.
    """
    named: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            item = node.get("template")
            if isinstance(item, str) and item and item != "auto":
                named.append(item)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    if not named:
        return []
    try:
        known = set(template_ids())
    except SdkError:
        # No installed kit to check against (a test double, a partial bundle). The
        # renderer is the backstop; refusing here would block documents that name a
        # perfectly good grammar.
        return []
    return sorted({n for n in named if n not in known})


def required_design_skills(value: Any) -> list[str]:
    """The design skills a document's grammars require, derived from the kit's own
    families rather than a second hardcoded table."""
    out: list[str] = []
    known = set(template_ids())

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            named = node.get("template")
            if isinstance(named, str) and named in known:
                out.append(design_skill_for(named))
            if node.get("kind") == "table":
                out.append(TABLE_SKILL)
            for item in node.values():
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(value)
    return sorted(set(out))


def cache_clear() -> None:
    """Drop the parsed-kit caches (used by tests that swap the runtime root)."""
    for cached in (_registry, _types, _declarations, _block_variants):
        cached.cache_clear()
