#!/usr/bin/env python3
"""Regenerate `scripts/fp_edits.py` (and the icon assets) from a reference checkout.

The reference is an assembled tree whose working state is the fork you want to ship:
upstream at the pinned commit, plus the overlay files, plus every edit. This derives the
declarative patch set from its `git diff` so the shipped table can never drift from what
was actually built and tested.

    python scripts/regen_edits.py ~/Developer/fp-studio-v0.3

Anchors grow context until they are unique in the upstream blob; a hunk that cannot be
made unique is an error, not a guess.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / "UPSTREAMS.lock.json").read_text())["openworker"]["commit"]
BINARY_SUFFIXES = (".png", ".icns", ".ico", ".rgba", ".woff2", ".wasm")
# Re-serialised JSON, declared as a whole-file edit by patch_openworker.py itself.
SPECIAL = {"surfaces/gui/src-tauri/tauri.conf.json"}
MIN_CONTEXT, MAX_CONTEXT = 3, 60


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True)


def _upstream(repo: Path, path: str) -> str:
    return _git(repo, "show", f"{BASE}:{path}")


def hunks(repo: Path, path: str) -> list[tuple[str, str]]:
    old_text = _upstream(repo, path)
    new_text = (repo / path).read_text("utf-8")
    old_lines, new_lines = old_text.splitlines(True), new_text.splitlines(True)
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    blocks = [op for op in matcher.get_opcodes() if op[0] != "equal"]
    merged: list[list] = []
    for op in blocks:
        # Hunks closer than a context window would overlap; merge them into one anchor.
        if merged and op[1] - merged[-1][2] <= 2 * MIN_CONTEXT:
            merged[-1][2], merged[-1][4] = op[2], op[4]
        else:
            merged.append(list(op))
    out: list[tuple[str, str]] = []
    for _tag, i1, i2, j1, j2 in merged:
        context = MIN_CONTEXT
        while True:
            old = "".join(old_lines[max(0, i1 - context) : min(len(old_lines), i2 + context)])
            new = "".join(new_lines[max(0, j1 - context) : min(len(new_lines), j2 + context)])
            if old_text.count(old) == 1:
                break
            if context >= MAX_CONTEXT:
                raise SystemExit(
                    f"{path}: no unique anchor for the hunk at upstream line {i1 + 1}"
                )
            context += 3
        out.append((old, new))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", help="assembled checkout whose state should ship")
    repo = Path(parser.parse_args().reference).expanduser().resolve()
    changed = _git(repo, "diff", "--name-only", BASE).split()

    rows: list[str] = []
    count = 0
    for path in changed:
        if path in SPECIAL or path.endswith(BINARY_SUFFIXES):
            continue
        for index, (old, new) in enumerate(hunks(repo, path), 1):
            count += 1
            rows.extend(
                [
                    "    (",
                    f"        {path!r},",
                    f"        {old!r},",
                    f"        {new!r},",
                    f"        {f'{path}#{index}'!r},",
                    "    ),",
                ]
            )

    header = '''#!/usr/bin/env python3
"""Generated: every text edit this fork applies to the pinned upstream checkout.

One entry per hunk: (path, upstream anchor, replacement, label). The anchor is unique in
the upstream blob, so `patch_openworker.py` can apply the set exactly once and
`check_upstream_ui.py` can replay it to prove the downstream tree is upstream + these
edits and nothing else. Regenerate with `scripts/regen_edits.py`; never hand-edit a hunk.
"""

EDITS: tuple[tuple[str, str, str, str], ...] = (
'''
    (ROOT / "scripts/fp_edits.py").write_text(header + "\n".join(rows) + "\n)\n")

    icons = ROOT / "assets/icons"
    icons.mkdir(parents=True, exist_ok=True)
    digests = {}
    for path in changed:
        if not path.startswith("surfaces/gui/src-tauri/icons/"):
            continue
        source = repo / path
        shutil.copy2(source, icons / source.name)
        digests[path] = hashlib.sha256(source.read_bytes()).hexdigest()
    (icons / "MANIFEST.json").write_text(json.dumps(digests, indent=1) + "\n")
    print(f"fp_edits.py: {count} hunks across {len(set(changed))} changed paths")
    print(f"assets/icons: {len(digests)} replaced assets")


if __name__ == "__main__":
    main()
