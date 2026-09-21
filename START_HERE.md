# Start here

Use this v0.3 overlay, not the discarded v0.1 application.

1. Read `README.ko.md` and `docs/REVIEW.md` for scope and unresolved release blockers.
2. Run `bash scripts/validate_local.sh` for the local regression suite.
3. Assemble a **new** checkout with `python scripts/assemble.py --dest /new/path/fp-studio`.
4. On macOS, follow `docs/DMG.md`; run actual compiler, OpenWorker, GUI and manual chat tests before a signed release.

**Build state (2026-09-21, this Mac):** `FP Studio_0.3.12_aarch64.dmg` was built from the assembled checkout
`~/Developer/fp-studio-release-0.3.12`, signed with Developer ID `Hyunmin kim (KH55W9G87F)` under hardened runtime,
**notarized and stapled** (`Accepted`, submission `cfcc4261-cbb4-4984-938c-aac3fbde8599`), copied out of the
mounted DMG with the download quarantine attribute set, installed to `/Applications/FP Studio.app` and launched:
`spctl -a` returns `accepted — source=Notarized Developer ID` and the sidecar answers `/v1/health`. The defect this
build exists for was then checked INSIDE the shipped sidecar: `coworker.compaction` extracted from the bundled
PyInstaller archive carries `IMAGE_TOKENS`, `CARRY_IMAGES`, `cap_explicit`, `_part_chars` and `carried_images`, and
`coworker.engine` carries `_COMPACTION_RETRY_DELAY` and `_compaction_reason`. SHA-256 of the DMG:
`6abf6521b6926bda32ee81246e07ccbf281e435785b6a4cf34bec4d7691806b5`.
No live provider call is claimed, and fonts are supplied at build time rather than shipped in this archive.

User interaction stays in the original OpenWorker conversation and artifact viewer. Do not add template selection or a second GUI.
