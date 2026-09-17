# Start here

Use this v0.3 overlay, not the discarded v0.1 application.

1. Read `README.ko.md` and `docs/REVIEW.md` for scope and unresolved release blockers.
2. Run `bash scripts/validate_local.sh` for the local regression suite.
3. Assemble a **new** checkout with `python scripts/assemble.py --dest /new/path/fp-studio`.
4. On macOS, follow `docs/DMG.md`; run actual compiler, OpenWorker, GUI and manual chat tests before a signed release.

**Build state (2026-09-15, this Mac):** `FP Studio_0.3.0_aarch64.dmg` was built from the assembled checkout
`~/Developer/fp-studio-v0.3`, signed with Developer ID `Hyunmin kim (KH55W9G87F)` under hardened runtime,
**notarized and stapled** (`Accepted`, submission `f319e84d-3ef4-4c23-aa0f-4c70ce5c2193`), installed to
`/Applications/FP Studio.app` and launched: `spctl -a` returns `accepted — source=Notarized Developer ID`,
the sidecar answers `/v1/health`, and the stock shell renders. SHA-256 of the DMG:
`929609932fb96a7f47d057529bbdd0426a64f1d349301ed26c00adbb5b3c387e`.
No live provider call is claimed, and fonts are supplied at build time rather than shipped in this archive.

User interaction stays in the original OpenWorker conversation and artifact viewer. Do not add template selection or a second GUI.
