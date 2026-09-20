# Start here

Use this v0.3 overlay, not the discarded v0.1 application.

1. Read `README.ko.md` and `docs/REVIEW.md` for scope and unresolved release blockers.
2. Run `bash scripts/validate_local.sh` for the local regression suite.
3. Assemble a **new** checkout with `python scripts/assemble.py --dest /new/path/fp-studio`.
4. On macOS, follow `docs/DMG.md`; run actual compiler, OpenWorker, GUI and manual chat tests before a signed release.

**Build state (2026-09-20, this Mac):** `FP Studio_0.3.10_aarch64.dmg` was built from the assembled checkout
`~/Developer/fp-studio-release-0.3.10`, signed with Developer ID `Hyunmin kim (KH55W9G87F)` under hardened runtime,
**notarized and stapled** (`Accepted`, submission `8e096b39-9a87-44d6-b53b-753abb865965`), copied out of the
mounted DMG with the download quarantine attribute set, installed to `/Applications/FP Studio.app` and launched:
`spctl -a` returns `accepted — source=Notarized Developer ID` and the sidecar answers `/v1/health`. The installed
binary was then driven over the socket shape the GUI actually opens (`?workspace=` empty) and captured the attached
image plus the user's light/dark declaration — the 0.3.9 defect this build exists for. SHA-256 of the DMG:
`b541063786f78efc76ea2dcbba229f7ae27f54131cea36976666c2378d37ed63`.
No live provider call is claimed, and fonts are supplied at build time rather than shipped in this archive.

User interaction stays in the original OpenWorker conversation and artifact viewer. Do not add template selection or a second GUI.
