#!/usr/bin/env python3
"""Apply this fork's checked patch set to a pinned upstream checkout.

Three kinds of change, all declared:

  1. **Text edits** — `scripts/fp_edits.py`, one entry per hunk, each anchored on a string
     that occurs exactly ONCE in the upstream blob. A drifted anchor fails the assembly
     instead of silently patching the wrong place.
  2. **Replaced assets** — the app icon set in `assets/icons`. Binary files cannot be
     anchored, so each is copied and its sha256 recorded.
  3. **Bundle identity** — `tauri.conf.json` is re-serialised JSON, declared as one
     whole-file edit.

Everything applied is written to `MANIFEST` in the assembled checkout. That record is the
contract `check_upstream_ui.py` enforces: upstream blob + these edits must equal the
downstream file, byte for byte. No replacement GUI, no undeclared JSX/CSS change, and no
"it was already like that" can hide in the diff.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fp_edits import EDITS  # noqa: E402  (sibling module, loaded by path)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ".fp-patch-manifest.json"
ICONS = ROOT / "assets/icons"
# Where the replaced icon set lands in the upstream tree.
ICON_DIR = "surfaces/gui/src-tauri/icons"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text("utf-8")
    if text.count(old) != 1:
        raise RuntimeError(
            f"{label}: expected one exact upstream anchor in {path}, found {text.count(old)}"
        )
    path.write_text(text.replace(old, new, 1), "utf-8")


def patch(repo: Path) -> None:
    applied: list[dict] = []

    for relative, old, new, label in EDITS:
        replace_once(repo / relative, old, new, label)
        applied.append({"path": relative, "old": old, "new": new, "label": label})

    # -- the app icon set (binary: replaced, not patched) --------------------------
    for source in sorted(ICONS.iterdir()):
        if source.name == "MANIFEST.json" or not source.is_file():
            continue
        target = repo / ICON_DIR / source.name
        if not target.exists():
            raise RuntimeError(f"Icon slot is absent upstream: {target}")
        data = source.read_bytes()
        applied.append(
            {
                "path": f"{ICON_DIR}/{source.name}",
                "binary": True,
                "sha256_before": hashlib.sha256(target.read_bytes()).hexdigest(),
                "sha256": hashlib.sha256(data).hexdigest(),
                "label": f"App icon: {source.name}",
            }
        )
        target.write_bytes(data)

    # -- bundle identity ----------------------------------------------------------
    # Configuration is not a new interface. Fork identity must not collide with upstream.
    conf = repo / "surfaces/gui/src-tauri/tauri.conf.json"
    before = conf.read_text()
    value = json.loads(before)
    if value.get("identifier") != "com.openworker.desktop":
        raise RuntimeError("Unexpected upstream app identity")
    value["identifier"] = "com.fourpillars.fpstudio"
    value["productName"] = "FP Studio"
    value["version"] = "0.3.2"
    value["bundle"]["resources"]["binaries/fp-runtime"] = "fp-runtime"
    # No update source: FP Studio ships no updater, and the GUI has no update surface.
    value["plugins"]["updater"]["endpoints"] = []
    conf.write_text(json.dumps(value, indent=2) + "\n")
    applied.append(
        {
            "path": "surfaces/gui/src-tauri/tauri.conf.json",
            "old": before,
            "new": conf.read_text(),
            "label": "Fork bundle identity",
        }
    )

    (repo / MANIFEST).write_text(json.dumps(applied, indent=1) + "\n", "utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo")
    patch(Path(parser.parse_args().repo).resolve())


if __name__ == "__main__":
    main()
