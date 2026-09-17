# FP Studio 0.3.1

An additive, pinned OpenWorker fork for conversational infographic research. **Keep the stock GUI.** Users research, discuss and revise in the original conversation while the original artifact viewer displays SVG/PNG. No replacement app, template picker, inspector, Figma or OMP runtime.

This archive contains source overlays, an exact-anchor assembler, regression tests and a macOS DMG build gate. It does **not** contain a full upstream checkout, fonts, model credentials or a signed DMG.

Local validation: 165 FP regression tests in an assembled tree (real resvg compiler and supplied fonts), 8 packaging/overlay-contract tests in this archive, 27 JavaScript runtime tests and 3 TypeScript preview-helper tests passed. Live model calls remain unexecuted here; the signature, notarization and hash of a published DMG are recorded in that release's notes, not claimed by this archive.

Start with [the Korean README](README.ko.md), [the review](docs/REVIEW.md), [test evidence](docs/TEST-REPORT.md), and [Mac release instructions](docs/DMG.md).

```bash
python scripts/assemble.py --dest /absolute/new/path/fp-studio
```

The assembler refuses an existing destination. Actual upstream code is cloned at the commits in `UPSTREAMS.lock.json`; it is never replaced with a substitute agent engine.
