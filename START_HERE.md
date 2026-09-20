# Start here

Use this v0.3 overlay, not the discarded v0.1 application.

1. Read `README.ko.md` and `docs/REVIEW.md` for scope and unresolved release blockers.
2. Run `bash scripts/validate_local.sh` for the local regression suite.
3. Assemble a **new** checkout with `python scripts/assemble.py --dest /new/path/fp-studio`.
4. On macOS, follow `docs/DMG.md`; run actual compiler, OpenWorker, GUI and manual chat tests before a signed release.

**Build state (2026-09-20, this Mac):** `FP Studio_0.3.9_aarch64.dmg` was built from the assembled checkout
`~/Developer/fp-studio-release-0.3.9`, signed with Developer ID `Hyunmin kim (KH55W9G87F)` under hardened runtime,
**notarized and stapled** (`Accepted`, submission `50109f68-e62c-473f-a7f8-f2a13e0713f8`), copied out of the
mounted DMG with the download quarantine attribute set, installed to `/Applications/FP Studio.app` and launched:
`spctl -a` returns `accepted — source=Notarized Developer ID`, the sidecar answers `/v1/health`, and the stock
shell renders with its sidebar, transcript, composer and right rail. The bundle's own runtime rendered a table to
PNG/SVG. SHA-256 of the DMG:
`86b1d342aa1bdff5341ab16b57fdb7ef70e5f7da1b4735447e16c78c90eda1b9`.
No live provider call is claimed, and fonts are supplied at build time rather than shipped in this archive.

User interaction stays in the original OpenWorker conversation and artifact viewer. Do not add template selection or a second GUI.
