# FP Studio 0.3.10

An additive, pinned OpenWorker fork for conversational infographic research. **Keep the stock GUI.** Users research, discuss and revise in the original conversation while the original artifact viewer displays SVG/PNG. No replacement app, template picker, inspector, Figma or OMP runtime.

This archive contains source overlays, an exact-anchor assembler, regression tests and a macOS DMG build gate. It does **not** contain a full upstream checkout, fonts, model credentials or a signed DMG.

Local validation: 2,188 regression tests pass in an assembled tree (every FP suite plus the upstream suite, real resvg compiler and the shipped bundle's fonts) with 1 skipped, and 57 fp-kit tests pass. Live model calls remain unexecuted here; the signature, notarization and hash of a published DMG are recorded in that release's notes, not claimed by this archive.

Light or dark is the user's declaration, not an inference: a render is refused until they have said which, and the light pack is the dark pack's measured difference rather than a second copy of it.

Start with [the Korean README](README.ko.md), [the review](docs/REVIEW.md), [test evidence](docs/TEST-REPORT.md), and [Mac release instructions](docs/DMG.md).

```bash
python scripts/assemble.py --dest /absolute/new/path/fp-studio
```

The assembler refuses an existing destination. Actual upstream code is cloned at the commits in `UPSTREAMS.lock.json`; it is never replaced with a substitute agent engine.
