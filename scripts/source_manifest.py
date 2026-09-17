#!/usr/bin/env python3
"""Write SOURCE-MANIFEST.json: sha256 of every file this archive ships.

The manifest identifies what was reviewed and shipped. Hand-maintaining it is how it went
stale, so `validate_local.sh` regenerates it at the end of every local run.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {'.git', '.zvec-grep', '.codegraph', '__pycache__', '.pytest_cache',
             'node_modules', '.venv', 'build', 'dist'}
SKIP_NAMES = {'.DS_Store', 'SOURCE-MANIFEST.json'}


def files() -> list[Path]:
    out = []
    for path in ROOT.rglob('*'):
        if not path.is_file() or path.name in SKIP_NAMES:
            continue
        if SKIP_DIRS & set(path.relative_to(ROOT).parts):
            continue
        out.append(path)
    return sorted(out)


def main() -> None:
    version = json.loads((ROOT / 'SOURCE-MANIFEST.json').read_text())['version']
    digests = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in files()}
    (ROOT / 'SOURCE-MANIFEST.json').write_text(
        json.dumps({'version': version, 'files': digests}, indent=1) + '\n', 'utf-8')
    print(f'SOURCE-MANIFEST.json: {len(digests)} files')


if __name__ == '__main__':
    main()
