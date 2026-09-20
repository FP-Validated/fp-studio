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

## 2026-09-17 — 0.3.3: the grammar could not express a paired bar

A user redraw of a paired bar chart (two dates per measure, seven measures) came back as
seven identical full-width bars with `100` printed beside each. The trace also shows 24
steps for one frame.

| Defect | Root cause | Fix and its test |
|---|---|---|
| Seven identical bars, every value printed as `100` | The bar grammar took one value column (`fields.value`) and one text column (`fields.line`). A paired source had nowhere to put its second series, so the agent indexed the first series to 100 | `style: 'paired'`: two or three bars per row from `fields.columns`, legend, both values printed, `fields.unit` / `delta` / `group`, `scale` `'row'` (default, mixed units) or `'shared'`. String values (`839.8M`, `$0.58`) print verbatim and their magnitude drives the bar. Kit tests assert two bars per row, every printed value, per-row normalisation, the shared scale and the one-series refusal |
| The agent read the renderer to find out what `style` accepts | A grammar's styles were published nowhere: `style?: string` | `templates/registry.json` carries them with a `when` line each; `fp_guide('vocabulary')` and `('draw')` return them. Live test asserts the shipped bundle offers `paired` |
| `colorMode: 'series'` crashed as `Cannot read properties of undefined (reading 'assignment')` | An unknown mode fell out of the palette switch as `undefined` | `choosePalette` names the modes the pack serves. Kit test asserts the message |
| The same grammar contract, frame fields, design tokens and chart card were served twice in one turn | `fp_guide('vocabulary')`'s `next` string still routed to the old four-call path, and nothing recorded what a conversation already held | The catalog routes to `fp_guide('draw')`; a served contract returns a pointer, `again=True` forces the text. An appendix is never suppressed. Test asserts the pointer, the digest map surviving it, and the forced re-read |

| Check | Result |
|---|---|
| fp-kit | 47 passed |
| Assembled tree, every FP suite / Node runtime / GUI unit + build / shell smoke E2E | 2,170 passed, 1 skipped / 27 / passed / 2 passed |
| Fixed per-call cost | 15,740 chars against the 15,800 cap: the paired rules and the pointer mechanics were paid for by deleting duplicated prose in the chart card and merging two prompt items that both described the draw route |
| Chart document's mandatory reading | 2,649-char card, 7,485 with the index card (cap 7,500) |
| The reported chart, rendered through the staged bundle and read back as an image | legend, group headings, per-row unit, two bars per row, both values and the change column; `$0.58` against `$9.50` is a stub, not half a bar |

## 2026-09-17 — 0.3.4: nothing could read back what was drawn

The same 24-step trace read the rendered SVG twice and then grepped the codebase for two
hex colours. An outlined SVG has no text nodes and no rects, so both reads answered
nothing — and every tool result is re-sent on each later model call of the turn.

| Defect | Root cause | Fix and its test |
|---|---|---|
| A render could only be checked by reading its SVG, twice, and grepping hexes out of the source | The render result advertised `fp/<name>.svg` and nothing described the layout. The SVG is outlined glyphs: no `<text>`, every `<rect>` a path | `describeProgram(result, input)` → `layout` on the render result and in the committed receipt: resolved grammar/style per block, colour mode, legend swatch per series with its hex, strings the renderer derived rather than copied, clipped copy with what a reader sees, renderer warnings. Authored copy is not echoed. Kit test asserts the swatch hexes, a formatted value in `derived`, authored copy absent from it and a clipped cell named; live test asserts the same through the shipped compiler and that the receipt keeps it |
| The redraw route demanded a `reference` transcription whose shape was published nowhere | The FPInput contract declares research references, not the reproduce block; the fidelity gate's compared keys lived only in `reference.py` | `reference.CONTRACT` — one definition, served as `reproduce` by `fp_guide('draw', name, redraw=True)`, naming the five accepted fields, the per-kind block shapes and every key the gate compares. Test asserts the fields match `validate`'s allow-list and that the gate text names the compared keys and `referenceWaiver` |

| Check | Result |
|---|---|
| fp-kit | 48 passed |
| Assembled tree, every FP suite | 2,172 passed, 1 skipped |
| Fixed per-call cost | 15,748 chars against the 15,800 cap. The readback instruction was paid for by deleting three sentences that restated tool mechanics the docstrings and error messages already carry |
| Layout readback, rendered through the staged bundle | `{template: bar, style: paired}`, `colorMode: pair`, swatches `A #4F86C6` / `B #5BA86B` — the two hexes the trace grepped for — `839,800,000` in `derived`, `Validators` absent, no clipping |

## 2026-09-17 — 0.3.5: the gate could not see the values it was guarding

The user put the source image next to what FP Studio delivered: seven bars of equal
length, each printed `100`, against a source that says 146, 22, 48, 839.8M, 7.0%, $9.50,
$3.82M. The frame committed, and one call earlier the model had read the document's own
JSON and called it identical to the image.

| Defect | Root cause | Fix and its test |
|---|---|---|
| A redraw that indexed a series to 100 was drawn and committed against a captured source | The numeric fidelity check collected numbers by KEY NAME (`value`, `values`, `percent`, …). A grammar names its own columns, so `fields: {value: 'Index'}` put every number in the frame outside the gate's sight | Every number inside a data row is data, whatever the column is called (`ROW_KEYS`, minus `id`/`accent`/`group`). Numbers inside strings are read too, with the magnitude their suffix declares, so `839.8M` and 839800000 are one measurement. Comparison is `math.isclose`, because the expansion is float arithmetic. Test renders the exact shipped shape through `fp_render` and asserts the refusal names `100` and that nothing was committed |
| Widening the check could refuse faithful redraws | A transcription that keeps the source's strings yields no numbers at all under the old rule; under the new one, every row number would be "invented" | Both sides parse strings the same way. Test asserts a verbatim redraw (`'839.8M'`) and a magnitude-expanded one (`839800000`) against the same transcription both pass, and that the verbatim one commits |
| `fields: {category: 'Measure'}` was reported as renaming the source | `category` is a LABEL_KEY, so the role map's column NAME was read as painted copy. The frame never paints it | `fields` is a role map, not copy: only `columns` (the legend) is checked. Test asserts `'measure'` is not reported |
| A committed revision could stay unfaithful and be declared correct | Nothing re-checked a stored document; only a human holding the source next to the frame could tell | `fp_inspect` returns `reference_drift` for any stored document that carries a `reference`. Test commits a drifted revision behind the gate and asserts inspect names it |

| Check | Result |
|---|---|
| Assembled tree, every FP suite | 2,174 passed, 1 skipped (2,172 before the four new assertions) |
| The shipped failure, replayed against the gate | refused: `these values are not in the transcription of the source: 58, 59, 100` plus the renamed legend `'index', 'now'` |
| A faithful redraw, verbatim and expanded | no violations either way |

## 2026-09-17 — 0.3.6: the research surface, and the gate that drove the model to it

A user attached two source images in one message, named the title, subtitle, note and
source for each, and asked for two infographics. The model searched the web four times,
read four pages, and composed frames from what it found. The delivered frame's numbers
came from a page, not from the image in the message.

| Defect | Root cause | Fix and its test |
|---|---|---|
| The redraw gate demanded that the document being rendered account for EVERY captured source | `unconsumed` returned every captured id except the one the document transcribed. Two images made the first document's refusal unsatisfiable, and the refusal text advised writing a `referenceWaiver` and composing freely | A document that redraws one supplied source passes; one that redraws none, while a source waits, is refused. A source another document already redrew is done (`Store.redrawn_sources`). Test renders two documents from two captured images with no waiver, then asserts a third source is still reported pending |
| One string silenced the reproduce gate for every source at once | `referenceWaiver: "<anything>"` short-circuited the whole check, so the product's first principle could be waived by a sentence the model wrote itself | The waiver names the source it excuses and quotes the user: `{"<source_id>": "<what they said>"}`. A bare string is refused. Test asserts both |
| Nothing stopped delivery with a supplied source untouched | Per-render enforcement was the only gate, and it had to be lenient to allow one-document-per-source | `fp_publish` refuses while any supplied source is un-redrawn and un-waived |
| The model researched instead of redrawing | The product registered `web_search` and `web_fetch`. An instruction competes with a tool that is right there, and the tool wins | The FP build registers neither. `capture_web_fetch` and its excerpt machinery are deleted; evidence kinds are the ones a user supplies (image, structure, local_file). The upstream test asserting registration is patched to assert absence. Tests: `build_engine`'s source mentions neither factory, `ask_user` stays, and no FP tool docstring advertises a URL |

| Check | Result |
|---|---|
| Assembled tree, every FP suite plus upstream | 2,175 passed, 1 skipped |
| Fixed per-call cost | 15,679 chars against the 15,800 cap — the two evidence items merged into one now that there is no fetch route to describe |

## 2026-09-18 — 0.3.7: light or dark, and a pack that is a difference

Patrick works (SECTION 28:3 in `FP Infographic Studio`) holds four templates and twenty-nine
delivered frames: seventeen dark `#141414`, eight `#0C0D0F` built by the Figma route, and
**six light `#E5E5E5` works**. The light appearance was never invented here; it was measured
from those six and from `Template WhiteH:1080px` 28:92 / 28:177.

| Defect | Root cause | Fix and its test |
|---|---|---|
| The product could only draw dark | `'light'` appeared nowhere in the renderer; sixteen literal greys outside `color.*` meant no light pack could swap them | Every literal is bound to a token (seven new named ramp steps). Test: neither pack carries a colour the palette does not name |
| A second pack would drift | Packs did not compose, so light meant copying 560 fields | `loadTheme` resolves `extends` with an RFC 7386 merge. The light pack is 4 KB of measured difference. Tests: the light pack inherits typography, safe zone and title block from the dark one; the committed pack equals `scripts/derive-light.mjs` |
| Gradients ignored the palette | `surfaceOps` and the card path passed theme gradients to the backend unresolved, so a token in a stop would have reached the SVG as a literal string | Both call `resolveGradient`. Without this the card and raised variants could not change with the pack |
| Nothing asked which appearance | The model chose, or defaulted to dark | `fp_render` refuses until the user has declared; the refusal names `ask_user` and offers no waiver. Both channels record: a typed message via `capture_turn`, an `ask_user` answer via `question_asker`. Tests: refusal text, both channels, `"Batch Prover And Light Client Prover"` is not a declaration, and a document field cannot open the gate |
| Switching pack would overwrite a delivered frame | The renderer fingerprint changes with the pack, so the drift guard fired with a message about compilers | The refusal now names the appearance switch and says to render the other one under its own name |
| Bars dissolved on paper | `barFillFrom 0.4 -> barFillTo 0.05` reads as a glow above ink and as a bar fading into the page on paper | The light pack fills bars solid, as the six light works do; emphasis rides the stroke. Verified by rendering the same document in both packs through the shipped runtime |

Light-mode rules, so a future pack is derived rather than guessed: the neutral ramp is
mirrored **by rank** (every step keeps a measured brand grey, the ends trade places, and no
role reference changes); chromatic colour keeps hue and saturation and loses only enough
lightness to clear **3:1** against paper, capped at the measured chroma of the active
`report` set; measured overrides beat both and cite their Figma node. The dark pack's edge
gradient is deleted in light because the light template and all six works are a flat fill
plus corner blobs.

| Check | Result |
|---|---|
| fp-kit | 53 passed (48 before) |
| Assembled tree, every FP suite plus upstream | 2,182 passed, 1 skipped |
| Live runtime, light pack | refused with no declaration, refused with the dark pack, rendered light; receipt pins `fp-v1.json` + `fp-v1-light.json`, `inherits: ['fp-v1']` |
| Fixed per-call cost | 15,747 chars against the 15,800 cap (one policy line, no new tool) |
| Accent contrast on paper | blue 3.2:1, green 3.3:1, coral 3.2:1, amber 3.2:1 |

## 2026-09-18 — 0.3.8: the two things a delivered frame does that the pack could not

`Patrick works` reads a node category by FILLING its box - `Coinbase Dominance` 35:4142
stacks four pastel cards with dark labels on the dark canvas, and `3_03 Account And
Transaction Abstraction` 32:1364 does the same on paper, then names its three categories in
a centred row of chips. The pack could do neither.

| Gap | What existed | Fix and its test |
|---|---|---|
| A category washed a node instead of filling it | `nodeBox` drew the accent at 12% with a tinted label, which is one reading, not the only one | `style: 'tinted'`: the accent fills the box at `surface.node.tinted.tint` (0.78 toward white) and the label is ink chosen against THAT fill by `inkOn`, so one rule serves both appearances. Tests: three filled boxes carry solid fills, every label colour is a pack neutral, and the same document on paper keeps the same ink |
| A coloured group had no name | Diagrams emitted no legend at all, so a category-coloured frame showed colours the reader had to guess | `legend: true` draws centred chips under the graphic in first-appearance order. Off by default, because a legend that appears uninvited takes the eye off the graphic. Tests: chips appear only when asked, and one category is not a legend |
| A composed diagram lost its categories | `collectAccentKeys` had no `chart` case, so node `group`/`kind` never reached the palette and every box came out slate. The top-level path had always collected them | The block path collects them too. Test asserts `ir.visual.accents` is `['Actor', 'Execution', 'Validation']` |
| The catalog could not say either existed | Diagram grammars declared no `styles` | The twelve grammars whose renderer draws a node box declare `tinted`. Test asserts the list AND that each one really honours it - a tinted render differs from a washed one |

Orthogonal routing, arrowheads and feedback edges were already there: `layeredGraph` sends an
edge that spans more than one rank, or runs backwards, into a side channel and draws it with
`cornerRadius` from the pack. Verified by rendering the same flow in both packs - the
`Settlement -> User action` edge takes the channel and arrives with an arrowhead. Nothing was
added for it.

| Check | Result |
|---|---|
| fp-kit | 57 passed (53 before) |
| Assembled tree, every FP suite plus upstream | 2,182 passed, 1 skipped |
| Live runtime, both primitives | catalog advertises `tinted` for `flowchart`; the shipped compiler drew three filled categories and named them |
| Both appearances | rendered the same tinted flow with `fp-v1` and `fp-v1-light`; pastel fills and ink labels in both |

## 2026-09-18 — 0.3.9: four payloads the conversation paid for twice

Every tool result is replayed on every later model call of the turn, so a payload emitted
at call *k* of *N* is charged *N−k* more times. Four of them were being re-sent with no
mechanism to stop it. Measured in an assembled tree (this overlay over the pinned upstream
and kit, real compiler, installed app fonts), base = `HEAD`, new = this change.

| Payload | Where it came from | Base | Now |
|---|---|---:|---:|
| `fp_review`'s final checklist, second call | `fp.py` had no dedupe on the largest payload the capability produces (107 rules for a redraw) | 21,414 | 937 |
| `review` on a redraw's write result | the review demanded an editorial brief and captured claims from a document the instructions tell not to research, and counted the transcription under `/reference/**` as unbound values | 412, `ok: false` | 156, `ok: true` |
| `review` on a factual write, 20 unbound values | one line per pointer, plus the invariant warnings, on every render, edit, restore and inspect | 1,282 (24 lines) | 408 (5 lines) |
| `checked` / `not_checked` on every write | the gate's constant description of what it checks | 532 per write | 532 once |

Replayed over one 24-call turn (8 writes, 2 reviews): a redraw cost 277,040 chars and now
costs 138,267; a factual document cost 303,096 and now costs 124,848 — ~35k and ~45k
tokens returned to the window.

Two correctness defects fell out of the same work. The dedupe ledger lived in the
workspace database, which outlives the conversation: a SECOND chat about the same project
was told "this conversation already carries it in full — scroll back" about a contract it
had never been sent, and was handed the acknowledgement digests that let it render
anyway. The ledger is now the tool closure, whose lifetime is the session's (the engine,
and with it the tool set, is built once per session and cached). And a redraw could not be
published at all without inventing a brief, an audience and a source for numbers the user
had supplied; it now publishes against the source it transcribes, with the redrawn image
named in the export receipt.

`layout` — the readback that replaces reading outlined glyphs — was the one summary with
no cap, copied whole into the result and the receipt. It is served whole while it fits
(8,000 chars; a 14-row paired bar is 327), and an oversized part is replaced by its size
and `fp_source(pointer, doc='layout')`, which now reads the committed readback.

| Check | Result |
|---|---|
| Assembled tree, every FP suite plus subscription auth | 233 passed (228 before; 5 new regression tests) |
| `pytest -q tests` (this repo) | 8 passed |
| Live runtime, real compiler and fonts | 27 passed; a redraw published end to end, 107 rules inspected, `## Redrawn source` in the receipt |
| Fixed per-call cost | 15,772 of 15,800 chars (schemas 10,733 + instructions 5,039); `doc='layout'` and `fp_review(again=)` were paid for by deleting three docstring sentences the prompt already carries |

No DMG was built for this change: source and the assembled-tree suites only. GUI, native
Mac integration, a signed build and a live model call remain unexecuted here.

An independent review of the change set found no bypass: the pointer response carries no
checklist ids, so `fp_publish` still refuses (`107 design rules were not inspected`) until
a body was served in this conversation, and a rebuilt tool set starts with an empty
ledger. It did name one drift: a readback pointer outlives the render that produced it,
because the next write replaces `receipt.layout`. `fp_source(doc='layout')` now stamps the
revision that answered, so a pointer carried over from an earlier result is read as the
current readback rather than mistaken for the one it was summarized from.

Regenerating the manifest showed the committed 0.3.8 `SOURCE-MANIFEST.json` was stale for
24 of its 117 entries — it was written before the last edits of that commit. It is
regenerated here, and `.serena/` (a local index directory, like `.zvec-grep` and
`.codegraph`) is excluded.
The manifest is only true if `validate_local.sh` is the last thing run before a commit.

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
~12,500 chars for a table document and ~21,400 for a redraw. It never rides a render or edit
result — `test_fp_final_gate.py` pins that — and since 0.3.9 it is served once per
conversation: a second `fp_review` returns the skill digests, the item count and a pointer,
and `again=True` forces the text back after a compaction.

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
