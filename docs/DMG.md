# macOS build and internal release

This document describes the build path. It produced `FP Studio_0.3.7_aarch64.dmg` on **2026-09-18**: Developer ID
signature (`Hyunmin kim (KH55W9G87F)`, timestamp 11:52:16), **notarized (`Accepted`) and stapled**, sha256
`4c40aae7a3a0d8c4375253119c0024180ba1d6d7291f7cf223e0a655c3019770`, published at
https://github.com/FP-Validated/fp-studio/releases/tag/v0.3.7 . The 0.3.0 through 0.3.5 builds were notarized the
same way and every DMG was withdrawn, because each shipped a frame that was wrong in what it showed - a broken
attached-image redraw, clipped table cells, a collapsed table head, a bar grammar that could not hold a second
series, a reproduce gate that could not see a value stored under a column the author named, and a reproduce gate a
two-image turn could only get past by waiving it and composing from the web. 0.3.6 drew correctly but could only
draw dark and never asked, so its DMG is withdrawn as superseded rather than defective. A copy downloaded
anonymously, carrying the browser's quarantine attribute, reports `accepted - source=Notarized Developer ID` and
validates its stapled ticket. Preserve the original OpenWorker GUI and run these gates on the actual target Mac;
installation on a clean, separate Mac is untested.

## 1. Prepare and assemble

Use a new destination, not an existing project directory:

```bash
python scripts/assemble.py --dest /absolute/new/path/fp-studio
cd /absolute/new/path/fp-studio
bash packaging/setup_dev_env.sh
.venv/bin/pip install -e '.[dev,messaging,browser,bedrock]' pyinstaller typer
(cd surfaces/gui && npm ci)
(cd surfaces/gui && npx playwright install)
```

The assembler checks out both exact commits, applies source anchors, builds/tests the kit and installs the pinned direct resvg dependency. It does not install macOS tooling or an Apple identity. Review generated npm lockfiles and the actual resolved Python dependencies. Record those locks with your release; do not describe version ranges as a fully reproducible dependency closure.

## 2. Supply production assets

`FP_FONT_DIR` must contain usable Pretendard TTF/OTF files and relevant notices. Static regular/semibold/bold weights used by the FP pack should be included and tested. Identity/glyph preflight rejects the wrong family and missing code points; it does not prove correct shaping or all font weight choices.

The FOUR PILLARS design rules are staged INTO the bundle (`design-skills/` beside the
runtime) and the build fails if any part is missing: each rule ships as a decision card
(`SKILL.md`, read on every authoring call) plus, for the four grammar rules, the verbatim
guideline appendix (`APPENDIX.md`, read only when a frame value is in doubt). `fp_render`
enforces them at runtime, so a DMG without them refuses every render on a clean Mac. The
staging step prints each rule's digest — one digest covers both parts, so record those with
the release, because editing either invalidates every acknowledgement made against the old
text.

The app icon set in `assets/icons` replaces the upstream icons during assembly, and each
file's sha256 is recorded in `.fp-patch-manifest.json`. Verify the built `.app` shows the
white four-dot mark before signing; a stale icon means the patch step did not run.

`FP_NODE_BINARY` must be a self-contained official Node binary matching the target architecture. Do not assume a Homebrew executable can run on another Mac. The script rejects non-system dylib dependencies. Use a tested, currently supported Node version for the internal release; record its exact binary hash. The supplied source was locally checked with Node 22.16.0, not endorsed as the latest or recommended security version.

```bash
export FP_FONT_DIR=/absolute/path/to/pretendard-fonts
export FP_NODE_BINARY=/absolute/path/to/self-contained-node/bin/node
```

## 3. Run the original app and conversation

```bash
mkdir -p surfaces/gui/src-tauri/binaries/fp-runtime
(cd surfaces/gui && npm run tauri dev)
```

Confirm the **original** interface, not a new FP desktop shell. Configure a provider with the existing Settings. Cloud model calls and search requests may send context outside the Mac; local file storage alone does not make the whole workflow offline.

The source fork uses `.config/fp-studio` on Mac rather than `.config/coworker`. It intentionally does not silently migrate another app's credentials/settings. In the pinned upstream, SecretStore is a 0600 JSON implementation. Review this before internal deployment; this package does not claim to have replaced it with Keychain.

## 4. Build

Unsigned/local iteration:

```bash
bash packaging/build_fp_studio_dmg.sh --development
```

Release requires a Developer ID identity and successful notarization. The original `packaging/build_dmg.sh` uses these notarytool variable names (different from Tauri's generic CLI examples):

```bash
export APPLE_SIGNING_IDENTITY='Developer ID Application: YOUR COMPANY (TEAMID)'
export NOTARYTOOL_API_KEY_PATH=/secure/path/AuthKey_XXXX.p8
export NOTARYTOOL_API_KEY_ID=YOUR_KEY_ID
export NOTARYTOOL_API_ISSUER_ID=YOUR_ISSUER_ID
bash packaging/build_fp_studio_dmg.sh --release
```

Do not store these secrets in the source archive. Use the original script's supported secure CI/local credential mechanism. The updater endpoints are deliberately disabled until FP has its own verified release channel and key; do not reuse OpenWorker's updater signing authority. The original build may warn about missing updater artifacts; this does not authorize returning to upstream update endpoints.

The wrapper stages Node, runtime dependencies, compiler dependencies, schemas/contracts, theme and user-supplied fonts. It runs local core/process/migration tests, actual compiler and permission integrations, the kit's tests and original GUI tests/build. Release also runs the original GUI E2E suite. Missing dependencies are failures, not skipped tests.

The additive hook in the original DMG script signs Node **after** the original keychain bootstrap, writes a staged-byte manifest and then lets Tauri seal the outer bundle. After original packaging, the wrapper checks code signatures, Gatekeeper assessment, stapled DMG ticket and SHA-256.

Expected destination after a successful native build:

```text
surfaces/gui/src-tauri/target/release/bundle/macos/FP Studio.app
surfaces/gui/src-tauri/target/release/bundle/dmg/FP Studio_<version>_<arch>.dmg
```

This is not a claim that these files already exist in this archive.

## 5. Required acceptance on a clean Mac

| Scenario | Acceptance |
|---|---|
| Installation without Node/Python/Figma/OMP installed | Bundled renderer and original sidecar start; original chat appears |
| User supplies documents and asks for an infographic | Agent asks only material questions and starts in the original conversation |
| Research | Original web search/fetch runs under original permissions; actual-read receipts appear |
| Conflicting dates/units/values | Agent reports the conflict, preserves uncertainty and blocks unsupported final publication |
| First successful draft | Existing Artifact Viewer opens SVG without a new page or template screen |
| Revision while SVG or PNG is open | Current chosen format reloads; navigation/other session does not receive stale content |
| Failed render or Stop | Last good result survives; no uncommitted output is reported as complete |
| Reopen without renderer/network | Previously stored SVG/PNG remains available; restore uses archived exact bytes |
| Runtime/font/theme update | New render requires explicit upgrade; previous revision does not silently change |
| Final SVG/PNG | Downloaded/viewed bytes match stored final artifacts; source report pins document/research revisions |
| Quarantined copied app | Signature/Gatekeeper/notary checks pass on the clean target, not only the build machine |
| Real visual quality | Check the full grammar corpus, Korean text, chart scale/units, connectors, clipping and meaningful hierarchy |

Automatic tests are necessary but not sufficient for the last row. Test at least one full user research -> draft -> correction -> final conversation with a real provider. Do not report this interaction as passed until it actually runs.

Primary distribution references: https://v2.tauri.app/distribute/ , https://tauri.app/distribute/sign/macos/ , https://developer.apple.com/developer-id/ .

## Two build traps hit on a real Mac

`FP_NODE_BINARY` must be an official self-contained Node. A Homebrew `node` fails the
`otool -L` portability check, by design: it links dylibs that are absent on a colleague's
Mac. Fetch the tarball for the pinned version, verify it against `SHASUMS256.txt`, and
point `FP_NODE_BINARY` at `.../bin/node`.

Cargo's release profile defaults to `strip = "debuginfo"` and applies it to HOST units as
well. With the current stable toolchain that strip removes the Rust metadata section from
proc-macro dylibs on macOS, and every proc-macro dependent then fails to compile with
`can't find crate for 'thiserror_impl'` (or `ctor_proc_macro`, `phf_macros`, …). The
build script exports `CARGO_PROFILE_RELEASE_BUILD_OVERRIDE_STRIP=none` so host and
proc-macro units keep their metadata; the shipped binary is still stripped. A partially
built `target/` from an older toolchain shows the same error — delete it, do not retry.
