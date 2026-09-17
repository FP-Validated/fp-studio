#!/usr/bin/env python3
"""Build receipt AFTER nested executable signing and BEFORE the outer app is sealed."""
import hashlib
import json
from pathlib import Path
import sys
root=Path(sys.argv[1]).resolve();files={}
for p in sorted(root.rglob('*')):
    if p.is_symlink():raise SystemExit('Symlink survived runtime staging')
    if p.is_file() and p.name!='BUILD-MANIFEST.json':
        files[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
(root/'BUILD-MANIFEST.json').write_text(json.dumps({'format':1,'files':files},indent=2)+'\n')
