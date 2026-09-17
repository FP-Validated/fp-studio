# Validation report: FP Studio 0.3.0

Date: 2026-09-15. Execution environment: macOS (arm64), Python 3.14.5, system Node v26.7.0,
bundled runtime Node v22.16.0. Reference assembled checkout: `~/Developer/fp-studio-v0.3` — the
tree the installed `/Applications/FP Studio.app` was built from on 2026-09-15.

Reproduce with:

```bash
FP_ASSEMBLED=~/Developer/fp-studio-v0.3 \
FP_FONT_DIR="/Applications/FP Studio.app/Contents/Resources/fp-runtime/fonts" \
bash scripts/validate_local.sh
```

## Executed, passed

| Suite | Count | What it establishes |
|---|---:|---|
| `python -m pytest -q tests` | 8 | Assembly refuses existing destinations, overlay cannot overwrite upstream, caches are not packaged, the 255-hunk declared edit set applies once and is recorded in the manifest, a missing icon slot fails, icon digests match `assets/icons/MANIFEST.json`, overlay contract |
| `python -m pytest -q $FP_ASSEMBLED/tests/test_fp_*.py test_subscription_auth.py test_gemini_subscription.py` | 207 | Store/CAS/repair/restore/publication, receipts/bindings, migration, real child-process timeout/Stop/output limits, design-rule gate, pointer edits, routed SDK, token economy incl. the fixed per-call budget, the final inspection gate, reproduce mode incl. pasted-structure capture and graph fidelity, SVG preview, subscription auth and model discovery, **actual pinned compiler → supplied fonts → resvg → SVG/PNG**, **actual patched OpenWorker permission engine** |
| `node --test overlay/fp_runtime/tests/*.test.mjs` | 27 | Nested canonical hashing, request/frame limits, static SVG checks, synthetic SFNT identity/cmap checks |
| Compiled `LatestArtifactReader` with Node test runner | 3 | Out-of-order results discarded, session invalidation, retain last-good on read failure |
| `npx playwright test e2e/fp-smoke.spec.ts` (release gate) | 2 | The stock shell under FP Studio identity; a committed SVG opens as a picture in the stock artifact viewer |
| `scripts/check_overlay.py` | pass | No replacement app/JSX/CSS/page/component in overlay |
| `scripts/check_upstream_ui.py` (during assembly) | pass | 44 GUI files equal upstream + 221 declared edits; 5 declared additions; no undeclared change |
| `tsc`, Python compileall, Node syntax, shell syntax | pass | The checked local modules parse/type-check |

**Total executed test cases: 247** (8 + 207 + 27 + 3 + 2). No skipped cases in these suites.

Logs: `validation/python-tests.txt`, `assembled-tests.txt`, `node-tests.txt`, `preview-tests.txt`,
`overlay-contract.txt`, `syntax.txt`.

## 2026-09-17 — card split, the one-call draw route, redraw-first and the note gate

Verified in a scratch assembled tree (`/tmp/fp-card`: this repository's overlay over the
reference checkout's upstream package, kit and runtime), driven by the reference venv with
`PYTHONPATH` pointing at the scratch tree and `FP_FONT_DIR` at the installed app's fonts.

| Check | Result | What it establishes |
|---|---:|---|
| `pytest -q tests/test_fp_*.py` (scratch tree) | 164 pass | Design-rule gate over card+appendix, digest covers both parts, a missing appendix is a missing rule, the final inspection gate, routed SDK, reproduce mode, token economy incl. the card byte cap, the per-document rule budget and the one-call draw route, and the three legitimate origins of a footer note |
| `pytest -q tests` (this repo) | 8 pass | Assembly mechanics and the overlay contract, now asserting both rule parts |
| `node --test overlay/fp_runtime/tests/*.test.mjs`, `LatestArtifactReader`, `tsc`, compileall, shell syntax | 27 + 3 + pass | Unchanged by this work, re-run as regression |
| Real render through `fp_guide('draw')` → `fp_render` | committed rev 1, audit ok, 72,225-byte SVG + 533,814-byte PNG | The one-call route's own digest map satisfies the gate with the pinned compiler and supplied fonts; a partial acknowledgement is still refused |
| Same document rendered by the pristine reference tree and by the changed tree | `sha256 eab86482eccea3ef48092e7885b18ce63390e3ea22158909fe964bfddd406715` on both | The frame background, chrome and every drawn byte are unchanged: the split moved rule text between context and appendix, not renderer behaviour |
| Note origin, real compiler | invented note refused before anything was written; `note` + `noteRequest` committed with audit ok | The bottom band no longer takes a caption nobody asked for, and a note that was asked for still renders: PNG 538,583 → 541,838 bytes with the note present, `noteRequest` itself never reaches the artifact |

Measured effect. Mandatory rule text a document must read: 11,167 → 6,420 chars for a
table, 12,502 → 7,342 for a chart, 11,576 → 7,699 for a diagram. Read path before a first
render: 5 calls / 23,258 chars → 2 calls / 18,245 chars, so three fewer round trips, each
of which replayed the whole transcript. Fixed per-call cost 15,158 → 15,785 chars (cap
15,800): the draw route, the appendix switch, redraw-as-first-principle and the note rule,
paid for by trimming docstring and prompt duplication.

NOT run in that scratch tree: GUI `npm test`/`npm run build`, the Playwright smoke, the DMG
build, signing and native-Mac integration. Those gates ran in the release build below.

## 2026-09-17 — signed, notarized release build

Assembled fresh with `scripts/assemble.py` into `/Users/steve/Developer/fp-studio-release-0.3.0` from the pinned
commits, then `packaging/build_fp_studio_dmg.sh --release` with a Developer ID identity and an App Store Connect
notary key.

| Check | Result |
|---|---|
| Design rules staged into the bundle | `fp-design-system@5d9787297db0`, `fp-design-table@5c8fb12a2bfa`, `fp-design-chart@3f9555a834ff`, `fp-design-flowchart@dbc5e15f5c38`, `fp-design-reproduce@d61169d6cc1b` |
| Python gate in the assembled tree (real resvg, real permission integration, supplied fonts) | 127 passed |
| fp-kit `npm test` | 189 tests / 27 files passed |
| Original GUI unit tests + production build | passed |
| Fork shell smoke E2E (`e2e/fp-smoke.spec.ts`) | 2 passed |
| Container signature | `Developer ID Application: Hyunmin kim (KH55W9G87F)`, team `KH55W9G87F`, timestamp 2026-09-17 09:54:58 |
| Notarization | `status: Accepted`, ticket stapled, `stapler validate` worked |
| Gatekeeper on the built app and DMG | `accepted — source=Notarized Developer ID` |
| Mounted DMG contents | 9 rule files (5 cards + 4 appendices), 9 Pretendard weights with `OFL.txt`, Node v22.16.0, 3,724 hashed entries in `BUILD-MANIFEST.json` |
| Published asset re-downloaded anonymously | 177,984,419 bytes, sha256 `610eaf219023f63f7431fda16aa273436f8a84c753c42b7307fc1b9b6d8ba0ee` — identical to the built DMG |
| Quarantined copy of that download | `accepted — source=Notarized Developer ID`, ticket validates |

Still not run: installation on a separate clean Mac, and a full live-provider research → draft → revision →
publish conversation.

## 2026-09-17 — 0.3.1: three defects the first real conversation found

A live 0.3.0 session spent 1,869,070 input tokens on one infographic. The trace, not a
guess, names the causes.

| Defect | Root cause | Fix and its test |
|---|---|---|
| An attached image never became a redraw source; the agent asked the user to re-attach it and to grant folder access to hunt for the screenshot | The composer sends `{kind:"image", data_url:…}` and `build_user_content` reads `data_url`; `capture_turn` read `url`/`dataUrl` — names nothing sends. The fixture test used `url`, so it passed | Capture reads the same field the model turn reads. `test_the_image_the_model_receives_is_the_image_the_gate_captures` feeds ONE attachment dict to both paths; it fails on the shipped 0.3.0 code (`[] == ['attachment:table.png']`) |
| Long table cells rendered as `…`; raising the row pitch only stretched the frame | `tableBlock` drew every cell with `maxLines: 1` against a fixed pitch | Cells wrap to four lines, row height follows the wrapped count, and a column never shrinks below its longest word. Kit test asserts no `…`, `lines.join(' ') == source`, and `['Custody &', 'recordkeeping']` |
| No horizontal rules; the header band was a rounded pill above the first row | Pack shipped `rowRules: false`; the band took the surface radius on all four corners | A rule under the header and between rows, spanning the full table width; `corners: 'top'` on the band, new per-corner radius honoured by the SVG (path) and Figma (per-corner radii) backends. Kit test pins rule count, `rule.w == table.w` and `band.corners === 'top'` |
| The release gate never ran `test_fp_reference.py` | The build script enumerated eight suites by name | The gate now runs `tests/test_fp_*.py` |

| Check | Result |
|---|---|
| Assembled tree, every FP suite | 165 passed |
| fp-kit | 43 passed |
| fp_runtime Node tests / GUI unit + production build / fork shell smoke E2E | 27 passed / passed / 2 passed |
| DMG `FP Studio_0.3.1_aarch64.dmg` | 177,987,734 bytes, sha256 `9cf9ca43858f227a870c1380d5f30a619f4ced21204b769ee0fde372decb0582` |
| Signature, notarization, Gatekeeper | `Developer ID Application: Hyunmin kim (KH55W9G87F)`, timestamp 2026-09-17 10:47:23, notary `Accepted`, ticket stapled and validated, `accepted — source=Notarized Developer ID` |
| Compiler pinned inside the bundle | `fp-kit/18518aef6147c481877196047b232af2ff14cb7d`, `rowRules: true` in the staged theme |
| The reported nine-row table, re-rendered through the staged bundle with `FP_FONT_DIR` unset | committed, audit `ok` with no findings, read back as an image: every cell whole, rules under the header and between rows, no vertical rules |
| Attachment → capture → `fp_inspect` references, through the staged bundle | `['text','image_url']` model turn and `attachment:ondo-table.png` captured from the same dict |

Round trips removed: a redraw needs no research and no review pass, `fp_review` is delivery
only, one `fp_guide('draw')` is the whole briefing, and the truncation warning that sent the
agent grepping the SVG is gone because the layout no longer truncates. Fixed per-call cost
stayed at 15,796 characters (cap 15,800) by deleting duplicated prose.

## 2026-09-17 — 0.3.2: the table head and the column widths

Two more defects, both visible in a user screenshot of a 0.3.1 frame beside a correctly
built reference.

| Defect | Root cause | Fix and its test |
|---|---|---|
| The column labels sat on the surface's top edge, on top of the first row | `headerH = pitch`, so a document that lowered `rowPitch` (what an agent does when it is trying to make room for clipped text) shrank the band below its own label height and the label's centring offset went negative | `headerH = max(pitch, lineHeight(headerRole) + pad)`. Kit test renders `rowPitch: 40` and asserts the label's box lies inside the band |
| A 120-character status sentence pulled width out of every other column, so "Custody & recordkeeping" wrapped onto two lines | Over-wide tables shrank every column in proportion to its content | Width is capped largest-first (binary search on the cap, floors respected): a column that fits keeps its natural width, the deficit comes out of the long prose column. Kit test asserts the key column stays on one line |

| Check | Result |
|---|---|
| fp-kit | 44 passed |
| Assembled tree, every FP suite / Node runtime / GUI unit + build / shell smoke E2E | 165 / 27 / passed / 2 passed |
| DMG `FP Studio_0.3.2_aarch64.dmg` | 177,991,569 bytes, sha256 `15f6cf23b9939a7e9f26e0aade2248bd77d4c81b8e66fb44facd65bc00ca8b73` |
| Signature, notarization, Gatekeeper | `Developer ID Application: Hyunmin kim (KH55W9G87F)`, timestamp 11:13:21, notary `Accepted`, stapled and validated, `accepted — source=Notarized Developer ID` |
| Compiler pinned inside the bundle | `fp-kit/ecf6d9c0b881a98ccfa8871a7dec86e8c5e799e6` |
| The reported table through the staged bundle, default pitch and `rowPitch: 40` | both committed with no audit findings; read back as images: labels inside the head in both, key column on one line, rules under the header and between rows |

## Reassembly equivalence

`python scripts/assemble.py --dest /tmp/fp-verify-8 --openworker-source ~/Developer/fp-studio-v0.3
--fp-kit-source ~/Developer/fp-studio-v0.3/vendor/fp-kit --skip-install` produced 736 source files that are
byte-identical to the reference checkout; zero content differences and zero files present only in the
assembled tree. The reference tree's remaining extra files are build outputs (`coworker.egg-info`,
`surfaces/gui/src-tauri/binaries`, installed `node_modules`, kit `dist`), not source.

That is what makes this repository the source of the installed build again: it reproduces that tree,
not merely something similar.

`--skip-install` leaves the assembled tree without the kit's build output and renderer dependencies,
so `test_fp_live_runtime.py` cannot run there; it was run in the reference checkout, which has them.

## Fixed per-call cost, and what a session actually costs

Tool results are paid for once and then replayed; the FP instructions and the tool schemas are
paid for on **every** model call of the conversation (up to 12 iterations in a stock turn).
Measured with the stock `ToolRegistry.schemas()` in the reference checkout:

| | before | after dedup | shipped |
|---|---:|---:|---:|
| `INSTRUCTIONS` | 5,418 | 3,518 | 4,652 |
| tool schemas | 10,061 (15) | 9,244 (15) | 10,506 (16) |
| total per model call | 15,479 | 12,762 | 15,158 |

`test_fp_token_economy.py::test_the_fixed_per_call_cost_stays_within_its_budget` pins the ceiling
(15,300 chars combined, 1,300 per tool), so restating policy in a docstring — or call mechanics in
the prompt — fails the suite. The ceiling was raised three times, each for a capability, with the
reason recorded in that test's docstring: reproduce mode, the final inspection gate, and routing a
source the user supplies.

A whole session was then measured end to end with the real tools (120-row table document of
10,383 chars; index + table rules, grammar catalog + one grammar, first render, five revisions):

| protocol | model calls | total session input |
|---|---:|---:|
| full snapshot (v0.2 shape, estimated) | 15 | ~333,000 tokens |
| delta writes, re-inspecting after each own edit | 15 | 212,234 tokens |
| delta writes, reusing the revision the write returned (shipped instructions) | 10 | **115,866 tokens** |

The remaining large items are the fixed cost itself and the design rules' verbatim text (8,830
chars for the index plus 3,564 for a grammar). The rules must be the guideline, not a summary, so
one reading stays in the transcript; only the grammar the document uses is read.

**Shipped.** The 2026-09-15 release build carries this surface. Two capabilities were added
deliberately above the deduplicated floor of 12,762: reproduce mode and the final inspection
gate, for 15,009 chars per call against a 15,100 ceiling.

The final inspection checklist (the per-grammar design rules served back with an id each) is
~17,000 chars for a table document. It is injected once, at `fp_review` before publication, and
never rides a render or edit result — `test_fp_final_gate.py` pins that.

## Test doubles, explicitly

The store/tool unit tests replace `RenderController.run` with a test-only renderer and a synthetic,
CRC-valid PNG. These prove persistence and workflow invariants, **not FP design output**. The font
unit tests construct synthetic name/cmap table bytes. The patch fixture in `tests/test_assembly.py`
is generated from the declared anchors and exercises application/ordering/failure — it is **not the
complete original source tree**; `check_upstream_ui.py` against a real checkout is what covers that.

The process tests launch and kill real local child processes, but those children are tiny Python
programs, not the production Node/resvg compiler.

## Not implemented or not qualified by these tests

- No clean-Mac quarantined-install test. The DMG is notarized and stapled and installs/launches here
  (`spctl -a` → `accepted — source=Notarized Developer ID`), but only on the build machine.
- No real provider API call or multi-turn user test performed.
- No full 45-grammar visual golden corpus run; no automated vision review of generated PNGs.
- The **upstream** GUI E2E suite is not a gate and does not pass: 181 of its 221 specs pin upstream's
  product name and wording that this fork changes. The release gate is the fork's own
  `e2e/fp-smoke.spec.ts`, which asserts the stock shell renders under FP Studio identity. GUI unit
  tests (189) do run in the release build.
- No native-memory/latency benchmark.
- No claim of cross-WebKit/resvg pixel equality. PNG is created from the final SVG; separate
  renderers may anti-alias differently.

These remaining checks are release blockers or explicit deployment decisions, not implicit passes.
