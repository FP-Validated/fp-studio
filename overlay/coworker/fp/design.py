"""The FOUR PILLARS design rules as a runtime gate, not a suggestion.

Five skills ship inside the application bundle: an index (`fp-design-system`), one per
grammar family (`fp-design-table`, `fp-design-chart`, `fp-design-flowchart`) and the redraw
rules (`fp-design-reproduce`). They are the customer's own design guidelines, stored
verbatim, served in two parts: `SKILL.md` is the decision card - what the model authors -
and `APPENDIX.md` keeps the frame arithmetic, Figma node ids, exact fills, stroke weights
and marker geometry the renderer draws from the Frame Guide. The card is replayed on every
authoring call; the appendix is served only when it is asked for. One digest covers both,
so neither part can be edited behind an acknowledgement.

Two mechanisms, deliberately separate:

  - **Gate.** `required(input)` derives which skills a document's grammars require.
    `fp_render` refuses unless the caller passes back the exact content digest of each one
    (`fp_design_rules` returns them). An agent cannot render an infographic without having
    the matching rules in its context, and a rules file edited in the bundle invalidates
    every stale acknowledgement instead of silently passing.
  - **Checks.** `violations(input)` enforces the subset that is decidable from the semantic
    input: the type scale (minimum 24, multiples of 4), palette binding instead of raw hex,
    and empty/placeholder required fields. Everything else — emphasis choice, legend marker
    shape, slanted axis labels, vector strokes, fidelity to a sample — is enforced by the
    rules being in context and by the user's review. A passing render is NOT evidence the
    design rules were honoured, and this module never claims otherwise.

Resolution order for the skill directory: `FP_STUDIO_DESIGN_SKILLS`, then the bundled
`<FP_STUDIO_RUNTIME_DIR>/design-skills`, then this package's copy (development checkout).
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Iterable, Optional

INDEX_SKILL = "fp-design-system"
TABLE_SKILL = "fp-design-table"
CHART_SKILL = "fp-design-chart"
DIAGRAM_SKILL = "fp-design-flowchart"
# Redrawing an attached image is a different job from composing one: the source already
# chose the grammar and the data, and only the visual system may change.
REPRODUCE_SKILL = "fp-design-reproduce"
SKILLS = (INDEX_SKILL, TABLE_SKILL, CHART_SKILL, DIAGRAM_SKILL, REPRODUCE_SKILL)

# Grammar → the skill whose rules govern it. Every fp-kit template id is classified; an
# unknown id is treated as a diagram, because an unclassified grammar must not become an
# escape hatch from the gate.
CHART_TEMPLATES = frozenset(
    {
        "bar", "line", "scatter", "area", "combo", "waterfall", "donut", "radar",
        "polar", "treemap", "funnel", "pyramid", "venn", "quadrant", "gantt", "sankey",
    }
)
DIAGRAM_TEMPLATES = frozenset(
    {
        "flowchart", "architecture", "data-flow", "deployment", "dependency", "tree",
        "sequence", "swimlane", "layers", "state", "er", "uml-class", "db-schema",
        "nested", "org-chart", "process", "loop", "timeline", "journey", "story-map",
        "kanban", "fishbone", "wardley", "high-level", "medallion", "dp-integration",
        "it-state", "matrix",
    }
)

# Type scale from the index skill: minimum 24, "keep the rules of 4".
MIN_TEXT_SIZE = 24
SIZE_GRID = 4
# Fields the frame ships as required: an empty one is deleted, never left as a placeholder.
OPTIONAL_FIELDS = ("subtitle", "source", "dateAsOf", "note")
# The footer note is drawn on one line; see `_footer_note` for the arithmetic and for the
# origins a note may have at all.
MAX_NOTE = 80
# Words that make a note the label illustrative mode REQUIRES in the visual (same
# vocabulary `research.py` checks for), so the gate below never blocks a required label.
ILLUSTRATIVE_MARKS = (
    "illustrative", "hypothetical", "sample data", "예시", "가상", "데모",
)
# fp-kit's ColorMode. `auto` is a real answer (the pack derives it from the data shape);
# saying nothing at all is not.
COLOR_MODES = frozenset({
    "auto", "none", "mono", "pair", "categorical", "sequential", "diverging", "ordered",
})
_PLACEHOLDERS = re.compile(
    r"^(h1|h2|title|subtitle|source|date as of|date|note|lorem ipsum|tbd|todo|xxx|placeholder)\W*$",
    re.IGNORECASE,
)
_HEX = re.compile(r"#[0-9A-Fa-f]{3,8}$")
# Light or dark is the user's call: the pack that draws follows their declaration, and a
# document may not carry an appearance the conversation never chose.
APPEARANCE_PACKS = {"dark": "fp-v1", "light": "fp-v1-light"}
_APPEARANCE_WORDS = {
    "dark": ("dark", "다크", "어두운", "어둡게", "검은", "블랙"),
    "light": ("light", "white", "라이트", "화이트", "밝은", "밝게", "흰", "하얀"),
}
# A colour word alone is not a declaration: "Light Client Prover" is a subject, not a mode.
_APPEARANCE_CONTEXT = (
    "mode", "theme", "version", "background", "palette", "style",
    "모드", "테마", "버전", "배경", "판", "스타일", "바탕",
)
_APPEARANCE_PARTICLE = re.compile(r"^\s*(?:로|으로|는|은|이|가|랑|과|와)")
# The shape of an answer to a question: "Dark", "라이트", "둘 다".
_APPEARANCE_ANSWER = 24


class DesignRulesError(ValueError):
    """A design-rules refusal carrying the exact remedy in its message."""


def appearance_declaration(text: Any) -> Optional[dict[str, str]]:
    """Light or dark as the user stated it, or None. Only their words ever land here.

    The gate this feeds must be satisfiable in one round trip, so a declaration is read
    from a normal sentence as well as from a bare answer - but never from a colour word
    standing alone in ordinary prose, or "Batch Prover And Light Client Prover" would
    silently choose paper. A word counts when a mode word sits beside it, when a Korean
    colour word takes a particle ("다크로"), or when the whole message is short enough to be
    an answer to the question.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    body = text.strip()
    low = body.lower()
    answerish = len(body) <= _APPEARANCE_ANSWER
    found: dict[str, str] = {}
    for mode, words in _APPEARANCE_WORDS.items():
        for word in words:
            start = 0
            while (at := low.find(word, start)) != -1:
                start = at + len(word)
                after = low[start:start + 16]
                before = low[max(0, at - 16):at]
                if (answerish
                        or _APPEARANCE_PARTICLE.match(body[start:start + 4])
                        or any(c in after or c in before for c in _APPEARANCE_CONTEXT)
                        or word in ("어둡게", "밝게")):
                    found[mode] = body[max(0, at - 40):start + 40].strip()
                    break
            if mode in found:
                break
    if not found:
        return None
    if len(found) == 2:
        return {"mode": "both", "quote": max(found.values(), key=len)}
    mode, quote = next(iter(found.items()))
    return {"mode": mode, "quote": quote}


def appearance_gate(recorded: Optional[dict], value: Any) -> None:
    """Refuse a render until the user has chosen light or dark, and follow their choice.

    The remedy is one call, and it is the only one: nothing the model can write records a
    declaration. A gate whose way out is a string the model composes is not a gate - that
    is how the reproduce gate came to be waived by a sentence the model wrote for itself.
    """
    if not recorded or recorded.get("mode") not in ("dark", "light", "both"):
        raise DesignRulesError(
            "Light or dark is the user's call and this conversation has not heard it. Ask "
            "once - ask_user(question='Light or dark?', options=['Dark','Light','Both']) - "
            "then render. Their answer records it; nothing you write can."
        )
    mode = recorded["mode"]
    pack = (value.get("theme") if isinstance(value, dict) else None) or APPEARANCE_PACKS["dark"]
    allowed = set(APPEARANCE_PACKS.values()) if mode == "both" else {APPEARANCE_PACKS[mode]}
    if pack not in allowed:
        raise DesignRulesError(
            f"The user asked for {mode}, so render with theme='{sorted(allowed)[0]}'"
            + (" or 'fp-v1' (one document per appearance)" if mode == "both" else "")
            + f", not theme='{pack}'."
        )


def skills_dir() -> Path:
    explicit = (os.environ.get("FP_STUDIO_DESIGN_SKILLS") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    # Same discovery the renderer uses, so the packaged app finds the rules beside its
    # sidecar (no env var is set in the signed bundle) and a dev checkout finds the
    # repository copy.
    from .rendering import runtime_root

    try:
        bundled = runtime_root() / "design-skills"
    except RuntimeError:
        bundled = None
    if bundled is not None and bundled.is_dir():
        return bundled
    return Path(__file__).resolve().parent / "design_skills"


CARD_FILE = "SKILL.md"
APPENDIX_FILE = "APPENDIX.md"
# Skills whose verbatim guideline text is split: the decision card is served on every
# authoring call, the appendix (frame arithmetic, Figma node ids, exact fills and stroke
# weights the renderer draws) only when it is asked for. `fp-design-reproduce` has none -
# every line of it is a decision the model makes.
APPENDIX_SKILLS = (INDEX_SKILL, TABLE_SKILL, CHART_SKILL, DIAGRAM_SKILL)
# A card is replayed on every model call that authors or edits a document, so its size is
# a contract, not a style preference. Raising it is a product decision.
MAX_CARD_BYTES = 5_200


def skill_path(name: str, part: str = "card") -> Path:
    if name not in SKILLS:
        raise DesignRulesError(
            f"Unknown design skill: {name!r}. Available: {', '.join(SKILLS)}"
        )
    if part not in ("card", "appendix"):
        raise DesignRulesError(f"Unknown rule part: {part!r}. Use card or appendix.")
    return skills_dir() / name / (CARD_FILE if part == "card" else APPENDIX_FILE)


def _read_part(name: str, part: str) -> bytes:
    path = skill_path(name, part)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise DesignRulesError(
            f"Design rules are missing from this installation: {name} "
            f"(expected {path}). The application bundle is incomplete; FP rendering is "
            "blocked until it is repaired."
        ) from exc


def load(name: str) -> dict[str, Any]:
    """One skill's decision card plus the digest `fp_render` requires back.

    The digest covers the card AND the appendix: the rules are one document served in two
    parts, so editing either invalidates yesterday's acknowledgement.
    """
    card = _read_part(name, "card")
    extra = _read_part(name, "appendix") if name in APPENDIX_SKILLS else b""
    return {
        "name": name,
        "digest": hashlib.sha256(card + b"\n" + extra).hexdigest(),
        "path": str(skill_path(name)),
        "rules": card.decode("utf-8"),
        "appendix": (
            f"fp_design_rules({name!r}, appendix=True) serves the verbatim guideline "
            "geometry behind this card"
        )
        if extra
        else "",
    }


def appendix(name: str) -> dict[str, Any]:
    """The verbatim guideline text behind a card: read it to inspect a rendered artifact
    against a number, or when a card's decision needs the frame value under it."""
    if name not in APPENDIX_SKILLS:
        raise DesignRulesError(
            f"{name} has no appendix: its card is the whole rule set. Skills with one: "
            + ", ".join(APPENDIX_SKILLS)
        )
    return {
        "name": name,
        "part": "appendix",
        "digest": digest(name),
        "path": str(skill_path(name, "appendix")),
        "rules": _read_part(name, "appendix").decode("utf-8"),
    }


def digest(name: str) -> str:
    return load(name)["digest"]


# -- the final inspection gate -------------------------------------------------------

_ITEM_SKIP = ("#", "|", "---", "```")


def _items(name: str) -> list[dict[str, str]]:
    """Every Do / Do not line of one skill, with the section it belongs to.

    The rule text is the guideline's own line, verbatim — the point of the final gate is
    to put the rules back in front of the model at the moment it would otherwise declare
    the work done from memory.
    """
    rules = load(name)["rules"]
    body = rules.split("---", 2)[-1]
    out: list[dict[str, str]] = []
    mode = ""
    section = ""
    previous = ""
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "Do":
            mode, section = "must", previous
            continue
        if line in ("Do not", "Don't", "Do Not"):
            mode = "never"
            continue
        if mode and not line.startswith(_ITEM_SKIP):
            out.append({
                "id": hashlib.sha256(f"{name}\n{section}\n{line}".encode()).hexdigest()[:8],
                "skill": name,
                "section": section or name,
                "verb": mode,
                "rule": line,
            })
            continue
        mode, previous = "", line
    return out


def checklist(value: Any) -> dict[str, Any]:
    """The rules this document must be inspected against before it is published.

    Scoped by grammar, exactly like the render gate: a table document is not asked about
    legend markers. Each item carries the digest of the skill it came from, so a check
    signed against older rules cannot be replayed against new ones.
    """
    needed = required(value)
    items: list[dict[str, str]] = []
    for name in needed:
        items.extend(_items(name))
    return {
        "skills": {name: digest(name) for name in needed},
        "items": items,
        "verdicts": {
            "pass": "checked against the rendered artifact and it complies",
            "n/a": "this rule does not apply to this document — say why in note",
        },
        "binding": "fp_publish refuses until every id has a verdict. A rule you cannot "
        "satisfy is a conversation with the user, never an omitted id.",
    }


def check_final(value: Any, submitted: Any) -> dict[str, Any]:
    """Refuse publication unless every checklist item was answered."""
    expected = checklist(value)
    ids = {item["id"] for item in expected["items"]}
    if not isinstance(submitted, dict):
        raise DesignRulesError(
            "Final inspection is mandatory: call fp_review for the checklist, verify each "
            f"rule against the rendered artifact, then publish with {len(ids)} verdicts."
        )
    given = submitted.get("checks") if isinstance(submitted.get("checks"), dict) else submitted
    missing = sorted(ids - set(given or {}))
    if missing:
        raise DesignRulesError(
            f"{len(missing)} design rules were not inspected: "
            + ", ".join(missing[:20])
            + (" …" if len(missing) > 20 else "")
            + ". Read them with fp_review and answer every id."
        )
    bad: list[str] = []
    for item_id in sorted(ids):
        answer = given[item_id]
        verdict = answer.get("verdict") if isinstance(answer, dict) else answer
        note = answer.get("note", "") if isinstance(answer, dict) else ""
        if verdict == "pass":
            continue
        if verdict == "n/a" and isinstance(note, str) and note.strip():
            continue
        bad.append(item_id)
    if bad:
        raise DesignRulesError(
            "These rules are neither passing nor explained: "
            + ", ".join(bad[:20])
            + ". Fix the artifact and re-inspect, or answer 'n/a' with the reason. "
            "Publication is the claim that the rules hold."
        )
    stale = [
        name for name, sealed in expected["skills"].items()
        if isinstance(submitted, dict)
        and isinstance(submitted.get("skills"), dict)
        and submitted["skills"].get(name) not in (None, sealed)
    ]
    if stale:
        raise DesignRulesError(
            "The inspection was made against older rules: " + ", ".join(stale)
        )
    return {"inspected": len(ids), "skills": expected["skills"]}


# -- which rules a document is subject to -------------------------------------------


def _grammars(value: Any, found: set[str]) -> None:
    """Every template/grammar id reachable from an FP input, including nested blocks."""
    if isinstance(value, dict):
        for key in ("template", "kind"):
            item = value.get(key)
            if isinstance(item, str):
                found.add(item)
        if isinstance(value.get("diagram"), dict):
            found.add("diagram")
        for item in value.values():
            _grammars(item, found)
    elif isinstance(value, list):
        for item in value:
            _grammars(item, found)


def required(value: Any) -> list[str]:
    """The skills whose rules govern this document, index first."""
    grammars: set[str] = set()
    _grammars(value, grammars)
    needed = [INDEX_SKILL]
    if "table" in grammars:
        needed.append(TABLE_SKILL)
    if grammars & CHART_TEMPLATES:
        needed.append(CHART_SKILL)
    # `chart` blocks name their template; a diagram payload or any unclassified grammar
    # falls to the diagram rules rather than escaping the gate.
    unclassified = {
        g
        for g in grammars
        if g not in CHART_TEMPLATES
        and g != "table"
        and g
        not in {
            "text", "columns", "cards", "panel", "kpi", "steps", "chart", "stages",
            "section", "divider", "spacer", "rows", "blocks", "graph",
        }
    }
    if grammars & DIAGRAM_TEMPLATES or unclassified:
        needed.append(DIAGRAM_SKILL)
    # A document that names a reference image is a redraw, and the redraw rules are what
    # keep it one.
    if isinstance(value, dict) and value.get("reference") is not None:
        needed.append(REPRODUCE_SKILL)
    return needed


def check_acknowledged(value: Any, acknowledged: Any) -> list[str]:
    """Refuse unless every required skill's CURRENT digest was acknowledged.

    `acknowledged` is the `{skill: digest}` mapping the agent collected from
    `fp_design_rules`. Returns the required skill names on success.
    """
    needed = required(value)
    if not isinstance(acknowledged, dict) or not acknowledged:
        raise DesignRulesError(
            "Design rules are mandatory: call fp_design_rules for "
            + ", ".join(needed)
            + " and pass {skill: digest} as design_rules."
        )
    stale: list[str] = []
    for name in needed:
        given = acknowledged.get(name)
        if not isinstance(given, str) or given != digest(name):
            stale.append(name)
    if stale:
        raise DesignRulesError(
            "These design rules were not acknowledged with their current content: "
            + ", ".join(stale)
            + ". Call fp_design_rules for each, read the rules, then render with the "
            "returned digests."
        )
    return needed


# -- the decidable subset -----------------------------------------------------------


def _text_sizes(value: Any, out: list[tuple[str, Any]], where: str = "") -> None:
    if isinstance(value, dict):
        for key in ("size", "headingSize", "subtitleSize"):
            if key in value:
                out.append((f"{where}.{key}".lstrip("."), value[key]))
        for key, item in value.items():
            _text_sizes(item, out, f"{where}.{key}".lstrip("."))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _text_sizes(item, out, f"{where}[{index}]")


def _raw_hex(value: Any, out: list[str], where: str = "") -> None:
    """Colour fields carrying a literal hex instead of a bound palette token."""
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{where}.{key}".lstrip(".")
            if key in ("color", "accent") and isinstance(item, str) and _HEX.match(item.strip()):
                out.append(path)
            elif key in ("accents", "roles") and isinstance(item, dict):
                for sub, subitem in item.items():
                    if isinstance(subitem, str) and _HEX.match(subitem.strip()):
                        out.append(f"{path}.{sub}")
                    else:
                        _raw_hex(subitem, out, f"{path}.{sub}")
            else:
                _raw_hex(item, out, path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _raw_hex(item, out, f"{where}[{index}]")


def _brand_exception(value: Any) -> bool:
    """A sampled brand colour is allowed — but only with the recorded source that the
    rules demand ("sampled from the logo asset in the file")."""
    direction = value.get("direction") if isinstance(value, dict) else None
    if not isinstance(direction, dict):
        return False
    decisions = direction.get("decisions")
    if not isinstance(decisions, list):
        return False
    return any(
        isinstance(d, dict) and isinstance(d.get("from"), str) and d["from"].strip()
        for d in decisions
    )


def violations(value: Any) -> list[str]:
    """The design-rule breaches that are decidable from the semantic input."""
    problems: list[str] = []
    if not isinstance(value, dict):
        return ["FP input must be an object"]

    title = value.get("title")
    if not isinstance(title, str) or not title.strip():
        problems.append("title (H1) is required and must not be empty")
    elif _PLACEHOLDERS.match(title.strip()):
        problems.append(f"title is placeholder text: {title!r}")
    for field in OPTIONAL_FIELDS:
        if field not in value:
            continue
        item = value.get(field)
        if not isinstance(item, str) or not item.strip():
            problems.append(
                f"{field} is empty — delete the field instead of shipping an empty "
                "required frame field"
            )
        elif _PLACEHOLDERS.match(item.strip()):
            problems.append(f"{field} is placeholder text: {item!r}")

    sizes: list[tuple[str, Any]] = []
    _text_sizes(value, sizes)
    for where, size in sizes:
        if not isinstance(size, (int, float)) or isinstance(size, bool):
            problems.append(f"{where}: text size must be a number")
            continue
        if size < MIN_TEXT_SIZE:
            problems.append(
                f"{where}={size:g}: minimum text size is {MIN_TEXT_SIZE} (never 22)"
            )
        elif float(size) % SIZE_GRID:
            problems.append(f"{where}={size:g}: text sizes keep the rules of 4")

    hexes: list[str] = []
    _raw_hex(value, hexes)
    if hexes and not _brand_exception(value):
        problems.append(
            "raw hex instead of a bound palette variable at "
            + ", ".join(sorted(hexes))
            + " — map the colour to the nearest FP palette token, or record the sampled "
            "brand asset in direction.decisions[].from"
        )

    problems.extend(_footer_note(value))
    problems.extend(_colour_situation(value))

    # Reproduce mode: the supplied source already made the structural decisions.
    if value.get("reference") is not None:
        from . import reference as reference_mode

        problems.extend(reference_mode.fidelity_violations(value))
    return problems


def _footer_note(value: dict) -> list[str]:
    """The footer note is a label the user asked for, not a caption the model wrote.

    Geometry, not taste: the note is drawn on ONE line at footer size 28 starting at
    x=206, and the brand mark begins at x≈1593. That is ~97 characters before the note
    runs under "FOUR PILLARS", and a shipped frame did exactly that. 80 keeps a margin
    and keeps the sentence where a sentence belongs — the body, or the chat.

    Origin, and this is the defect it exists for: a note nobody asked for kept appearing
    in the frame's bottom band — an "insight", a caveat, a hedge the source never had. The
    guideline already refuses to invent one ("don't invent a source, note, or subtitle the
    sample doesn't have"), so the field now has to name where it came from: the user's own
    request, the transcription of a redrawn source, or the label illustrative mode requires.
    """
    raw = value.get("note")
    if not isinstance(raw, str) or not raw.strip():
        return []
    note = raw.strip()
    if len(note) > MAX_NOTE:
        return [
            f"note is {len(note)} characters: the footer note is a short label "
            f"(max {MAX_NOTE}) drawn on one line, and a longer one runs under the FOUR "
            "PILLARS mark. Shorten it, move the explanation into the body, or drop the "
            "note — the user did not ask for a caption"
        ]
    folded = note.casefold()
    if any(mark in folded for mark in ILLUSTRATIVE_MARKS):
        return []
    asked = value.get("noteRequest")
    if isinstance(asked, str) and asked.strip():
        return []
    reference = value.get("reference")
    if isinstance(reference, dict):
        source_note = reference.get("note")
        if isinstance(source_note, str) and _squash(note) in _squash(source_note):
            return []
        return [
            f"note {note!r} is not in the transcription of the source being redrawn: a "
            "redraw adds no footer note of its own. Transcribe the source's note into "
            "reference.note, record the user's words in noteRequest, or drop the note"
        ]
    return [
        f"note {note!r} was not asked for: the footer note is not a caption to add. "
        "Record the user's own request in noteRequest, or drop the note — an unrequested "
        "line across the frame's bottom band is not neutral"
    ]


def _squash(text: str) -> str:
    return " ".join(text.split()).casefold()


def _colour_situation(value: dict) -> list[str]:
    """"Identify the situation first" — decided, not defaulted.

    A diagram's palette keys are the distinctions the author declares (node groups or
    kinds). Declare none and the pack has nothing to colour, so every box comes out the
    same slate — not because slate was chosen but because nothing was said. For anything
    bigger than a three-box sketch that answer has to be written down.
    """
    diagram = value.get("diagram")
    nodes = diagram.get("nodes") if isinstance(diagram, dict) else None
    if not isinstance(nodes, list) or len(nodes) < 3:
        return []
    if isinstance(value.get("colorMode"), str) and value["colorMode"].strip():
        if value["colorMode"] not in COLOR_MODES:
            return [
                f"colorMode {value['colorMode']!r} is not one of "
                + ", ".join(sorted(COLOR_MODES))
            ]
        return []
    if value.get("accents") or value.get("highlightIds"):
        return []
    if any(isinstance(n, dict) and (n.get("group") or n.get("kind")) for n in nodes):
        return []
    return [
        "decide the colour situation first (fp-design-system, 'Color — decide the "
        "situation first'): give the nodes their groups, name accents/highlightIds, or "
        "set colorMode explicitly — 'none' is a valid answer, an omission is not. "
        "Without one of these every box renders the same slate by default"
    ]


def enforce(value: Any, acknowledged: Any) -> dict[str, Any]:
    """Gate + checks, in that order. Raises DesignRulesError on any refusal."""
    needed = check_acknowledged(value, acknowledged)
    problems = violations(value)
    if problems:
        raise DesignRulesError(
            "The document breaks the FOUR PILLARS design rules:\n- "
            + "\n- ".join(problems)
        )
    checked = [
        "type scale (min 24, multiples of 4)",
        "palette binding (no raw hex)",
        "no empty or placeholder required fields",
        f"footer note fits one line (max {MAX_NOTE} characters)",
        "the colour situation is stated, not defaulted",
    ]
    if isinstance(value, dict) and value.get("reference") is not None:
        checked.append(
            "reproduce mode: same grammar, same block sequence, same nodes and directed "
            "edges, no value or label the transcription did not read from the source"
        )
    return {
        "design_rules": needed,
        "checked": checked,
        "not_checked": "emphasis choice, legend markers, axis label slant, vector "
        "strokes and fidelity to the source are your responsibility and the user's review",
    }


def catalog() -> list[dict[str, str]]:
    """Index of the shipped rules, for `fp_design_rules()` with no argument."""
    rows: list[dict[str, str]] = []
    for name in SKILLS:
        path = skill_path(name)
        rows.append(
            {
                "name": name,
                "present": str(path.is_file()).lower(),
                "path": str(path),
                "appendix": str(name in APPENDIX_SKILLS).lower(),
            }
        )
    return rows


def resource_files() -> Iterable[Path]:
    """Every file the bundle must carry — used by the packaging manifest."""
    base = skills_dir()
    for name in SKILLS:
        yield base / name / CARD_FILE
        if name in APPENDIX_SKILLS:
            yield base / name / APPENDIX_FILE


def missing() -> list[str]:
    """A card or an appendix absent from the installation, by the name it is served as.

    A dropped appendix is as fatal as a dropped card: the digest covers both, so a bundle
    missing one refuses every render instead of quietly serving half the rules.
    """
    out = [name for name in SKILLS if not skill_path(name).is_file()]
    out += [
        f"{name}/{APPENDIX_FILE}"
        for name in APPENDIX_SKILLS
        if not skill_path(name, "appendix").is_file()
    ]
    return out
