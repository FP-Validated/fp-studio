#!/usr/bin/env python3
"""Prove the downstream GUI is the pinned upstream GUI plus exactly the declared patch set.

The old gate kept an allowlist of editable files and rejected any line that looked like
JSX. That answered "does this diff look like a redesign?" with a regex, and every new
declared edit needed a new hole in it. This answers the real question by reconstruction:

    upstream blob  +  the edits `patch_openworker.py` recorded  ==  downstream file

byte for byte, for every file under `surfaces/gui`. A replacement GUI, a new page, a
sneaked-in CSS tweak or a one-character label change that was not declared all fail the
same way, and no declared change needs the gate to be loosened.

Files that only EXIST downstream (the FP request-order helper, the ko catalog, the IME
test) are listed in ADDITIONS — additions can't be reconstructed from an upstream blob,
so they are enumerated instead, and the overlay contract (check_overlay.py) is what
keeps that list from growing into a second application.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

BASE = '5bc10d928e0b64aae74313349a3b17bd19643ae2'
MANIFEST = '.fp-patch-manifest.json'
GUI = 'surfaces/gui'
# Downstream-only files. Pure data (a locale catalog), one request-ordering helper, and
# tests — no component, page, route, style or canvas.
ADDITIONS = {
    'surfaces/gui/src/fp/latestArtifact.ts',
    'surfaces/gui/src/fp/latestArtifact.test.ts',
    'surfaces/gui/src/locales/ko.json',
    'surfaces/gui/src/components/Composer.ime.test.tsx',
    'surfaces/gui/e2e/fp-smoke.spec.ts',
}
# Components whose behaviour users read as "this is OpenWorker": byte-identical to
# upstream except for the edits declared for them in the manifest.
PROTECTED = (
    'surfaces/gui/src/components/Sidebar.tsx',
    'surfaces/gui/src/components/Composer.tsx',
    'surfaces/gui/src/components/Transcript.tsx',
)


def _git(repo, *args: str) -> str:
    return subprocess.check_output(['git', *args], cwd=repo, text=True)


def _upstream(repo, path: str) -> bytes:
    return subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=repo)


def _expected(repo, path: str, edits: list[dict]) -> bytes:
    """Upstream bytes with this file's declared edits applied, in order."""
    text = _upstream(repo, path).decode('utf-8')
    for edit in edits:
        if edit.get('all'):
            if edit['old'] not in text:
                raise SystemExit(f"{path}: declared edit no longer matches upstream: {edit['label']}")
            text = text.replace(edit['old'], edit['new'])
            continue
        if text.count(edit['old']) != 1:
            raise SystemExit(f"{path}: declared anchor is not unique upstream: {edit['label']}")
        text = text.replace(edit['old'], edit['new'], 1)
    return text.encode('utf-8')


def check(repo: str):
    manifest_path = Path(repo) / MANIFEST
    if not manifest_path.is_file():
        raise SystemExit(f'No {MANIFEST}: the checkout was not assembled by patch_openworker.py')
    declared: dict[str, list[dict]] = {}
    for edit in json.loads(manifest_path.read_text()):
        declared.setdefault(edit['path'], []).append(edit)

    changed = set(_git(repo, 'diff', '--name-only', BASE, '--', GUI).splitlines())
    untracked = set(_git(repo, 'ls-files', '--others', '--exclude-standard', '--', GUI).splitlines())
    undeclared = (changed | untracked) - set(declared) - ADDITIONS
    if undeclared:
        raise SystemExit('Undeclared GUI changes: ' + str(sorted(undeclared)))

    for path, edits in declared.items():
        if not path.startswith(GUI + '/'):
            continue  # the python/packaging side is covered by its own tests
        actual = (Path(repo) / path).read_bytes()
        binary = [e for e in edits if e.get('binary')]
        if binary:
            # A replaced asset (the app icon set) cannot be reconstructed from an anchor;
            # its declared digest is the contract.
            expected_digest = binary[-1]['sha256']
            if hashlib.sha256(actual).hexdigest() != expected_digest:
                raise SystemExit(
                    f'{path} is not the declared asset — an undeclared replacement is in '
                    'the working tree'
                )
            continue
        if actual != _expected(repo, path, edits):
            raise SystemExit(
                f'{path} does not equal upstream plus its declared edits — an undeclared '
                'change is in the working tree'
            )
    for path in PROTECTED:
        if path not in declared:
            if _upstream(repo, path) != (Path(repo) / path).read_bytes():
                raise SystemExit('Protected component changed without a declaration: ' + path)
    missing = ADDITIONS - untracked - changed
    if missing:
        raise SystemExit('Declared GUI addition is absent: ' + str(sorted(missing)))
    print(
        f'upstream-ui: {len([p for p in declared if p.startswith(GUI)])} GUI files equal '
        f'upstream + {sum(len(e) for p, e in declared.items() if p.startswith(GUI))} declared '
        f'edits; {len(ADDITIONS)} declared additions; no undeclared change'
    )


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('repo')
    check(p.parse_args().repo)
