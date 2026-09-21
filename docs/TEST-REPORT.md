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

## 2026-09-20 — 0.3.9: four payloads the conversation paid for twice

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

## 2026-09-20 — 0.3.9: signed, notarized release build

Assembled fresh with `scripts/assemble.py` into `/Users/steve/Developer/fp-studio-release-0.3.9` from the pinned
commits, then `packaging/build_fp_studio_dmg.sh --release` with the Developer ID identity and an App Store Connect
notary key.

| Check | Result |
|---|---|
| Upstream GUI comparison | 44 GUI files equal upstream + 221 declared edits, 5 declared additions, no undeclared change |
| Design rules staged into the bundle | `fp-design-system@5d9787297db0`, `fp-design-table@5c8fb12a2bfa`, `fp-design-chart@a8a7dba5510c`, `fp-design-flowchart@dbc5e15f5c38`, `fp-design-reproduce@d61169d6cc1b` |
| Python gate in the assembled tree (real resvg, real permission integration, supplied fonts) | 185 passed |
| fp-kit `npm test` | 57 passed |
| Original GUI unit tests + production build | 189 tests / 27 files passed, build succeeded |
| Fork shell smoke E2E (`e2e/fp-smoke.spec.ts`) | 2 passed |
| Container signature | `Developer ID Application: Hyunmin kim (KH55W9G87F)`, team `KH55W9G87F`, timestamp 2026-09-20 10:21:30 |
| Notarization | submission `50109f68-e62c-473f-a7f8-f2a13e0713f8`, `status: Accepted`, stapled, `stapler validate` worked |
| DMG | `FP Studio_0.3.9_aarch64.dmg`, 178,107,724 bytes, sha256 `86b1d342aa1bdff5341ab16b57fdb7ef70e5f7da1b4735447e16c78c90eda1b9` |
| Quarantined copy | quarantine attribute set on the DMG, `spctl -a -t open` → `accepted — source=Notarized Developer ID`; mounted, copied to `/Applications`, `spctl -a` → `accepted` |
| Installed app launched | sidecar answered `/v1/health` with `{"status":"ok"}`; the stock shell rendered with its sidebar, session list, transcript, composer and right rail (screenshot reviewed) |
| Shipped bundle renders | the installed bundle's own runtime (`node v22.16.0`, staged fp-kit) rendered a 6-row table to a 580,967-byte PNG and 229,613-byte SVG through `fp-kit/9e7653d9027b` |
| Mounted bundle contents | 9 rule files (5 cards + 4 appendices), 9 Pretendard weights with `OFL.txt`, Node v22.16.0, 3,727 hashed entries in `BUILD-MANIFEST.json` |
| Published asset re-downloaded | `gh release download v0.3.9` returned 178,107,724 bytes, sha256 identical to the built DMG; quarantined copy `accepted — source=Notarized Developer ID`, ticket validates (GitHub serves it as `FP.Studio_0.3.9_aarch64.dmg`) |
| Full assembled suite, FP plus upstream | 2,188 passed, 1 skipped, with the shipped bundle as the runtime |

Still not run: installation on a separate clean Mac, and a full live-provider research → draft → revision →
publish conversation in this build.

## 2026-09-20 — 0.3.10: the first message of a session was thrown away

Two recorded conversations in the installed 0.3.9 build, read from
`~/.config/fp-studio/conversations/*.jsonl` and the workspace store. One asked for a white and a
dark version of an attached table; the other for an attached diagram redrawn in English. Both
attachments reached the model (`image_url` parts of 76,577 and 102,241 characters), and neither
became a captured source: `/Users/steve/fpstudio` had no `fp/attachments` directory and one
`local_file` row from an earlier week.

The sidecar log named the cause. Each session's FIRST socket carries no folder:

```
WebSocket /ws/session/b17a1ba3-b1f?workspace=&agent=cowork   [accepted]   ← the message + image
WebSocket /ws/session/b17a1ba3-b1f?workspace=%2FUsers%2Fsteve%2Ffpstudio  ← a later reconnect
```

`if capture_turn is not None and workspace:` read that empty parameter, so on exactly the turn that
carries the attachment and the user's own "화이트 다크 2가지 버전" both were dropped. Everything the
user saw follows from it.

| Defect | Evidence in the recording | Fix and its test |
|---|---|---|
| The attached source was never captured, so the redraw had nothing to point at | `fp_capture_image {}` → "Pass a path…", then 12 `fp_inspect`, 12 `fp_source`, a `grep` and a `list_files` hunting for it | capture and the ask-channel declaration both resolve the workspace through `manager.engine_workspace(...)` — `test_fp_first_turn.py` drives the real socket with `?workspace=` empty and asserts the image row, the file on disk and `mode='both'` |
| The appearance question never ended | `fp_render(light)` refused twice → `ask_user('Light or dark?')` → **"Dark"** → the model asks whether both are wanted → **"Both"** → nothing recorded → three more refusals ("the user asked for dark") → `ask_user` again → **"Both"** → refusal → a fourth ask, answered `interrupted by user`. The light document was never rendered | `"Both"`, `"둘 다"`, `"둘다 만들어줘"`, `"두 버전 모두"` record `both` when the question they answer names light and dark; the same words against "어느 문법으로 그릴까요?" record nothing (`test_the_answer_the_refusal_prescribes_records_it`) |
| One `read_file` cost more than everything else in the turn | `read_file('fp/grt-overall-structure.png')` returned 918,976 characters of U+FFFD with a note offering lines 2001-6157; re-sent on all 18 later calls = 16.5M of that turn's 19.0M | `read_file` refuses a file whose first bytes are not UTF-8 text, naming path and size (190 characters); instruction 9 no longer says "look at the PNG" |
| The same contract was bought twice | `fp_guide('draw', 'architecture', redraw=True)` then `fp_guide('draw', 'architecture')`: 14,525 characters of grammar, frame fields and cards already in the transcript. `fp_design_rules(appendix=True)` twice for one kind | `draw` tracks each piece and serves only what is missing; the appendix has its own ledger key. 14,525 → 604 and 3,965 → 477, measured by replaying the recorded calls |
| Four `ask_user` rounds about a declaration the tools could already see | the model has no way to read the store, and policy says "ask if they have not said" | `fp_guide('draw')` — the call immediately before a render — carries `appearance` |
| Name and pointer guessing | 8 `fp_inspect` calls on names that do not exist; `fp_source(pointer='/')` and `pointer='""'` → "No such path" three times | a miss lists the workspace's documents; `'/'`, `'""'` and `''` all read the root, and the refusal names the form |

Cumulative tool-result replay for the recorded 44-call turn, same call sequence with the new
payload sizes measured by replaying each `fp_guide`/`fp_design_rules`/`read_file` call against the
built tree: **18,999,604 → 2,230,162 characters (89% less)**. The 25-call turn's traffic barely
moves (801,053 → 798,238) because its waste was rounds, not payload: five questions, six refused
renders and a version that never got drawn.

| Check | Result |
|---|---|
| `python -m pytest -q tests` (repo) | 8 passed |
| FP suites in the assembled tree (real resvg, real permission integration, shipped fonts) | 194 passed (185 before) |
| `FP_ASSEMBLED` gate | 242 passed |
| Full assembled suite, FP plus upstream | 2,197 passed, 1 skipped (2,188 before) |
| Fixed per-call cost | 15,776 of the 15,800 budget (15,772 before): instruction 9 now forbids reading an artifact file, inside the same budget |

The pre-fix failure is pinned, not assumed: reverting the capture hook to the query parameter makes
`test_the_first_message_is_captured_when_the_socket_names_no_workspace` fail with `[] != ['attachment:table.png']`.

Not run: a live-provider conversation in a rebuilt bundle, and installation on a separate clean Mac.

## 2026-09-20 — 0.3.10: signed, notarized release build

Assembled into `/Users/steve/Developer/fp-studio-release-0.3.10` from the pinned commits, then
`packaging/build_fp_studio_dmg.sh --release`.

| Check | Result |
|---|---|
| Upstream GUI comparison | 44 GUI files equal upstream + 221 declared edits, 5 declared additions, no undeclared change |
| Design rules staged | `fp-design-system@5d9787297db0`, `fp-design-table@5c8fb12a2bfa`, `fp-design-chart@a8a7dba5510c`, `fp-design-flowchart@dbc5e15f5c38`, `fp-design-reproduce@d61169d6cc1b` |
| Python gate in the build tree (real resvg, real permission integration, supplied fonts) | 194 passed |
| fp-kit `npm test` | 57 passed |
| Original GUI unit tests + production build | 189 tests / 27 files passed, build succeeded |
| Fork shell smoke E2E | 2 passed |
| Container signature | `Developer ID Application: Hyunmin kim (KH55W9G87F)`, team `KH55W9G87F`, timestamp 2026-09-20 16:34:56 |
| Notarization | submission `8e096b39-9a87-44d6-b53b-753abb865965`, `status: Accepted`, stapled, `stapler validate` worked |
| DMG | `FP Studio_0.3.10_aarch64.dmg`, 175,092,614 bytes, sha256 `b541063786f78efc76ea2dcbba229f7ae27f54131cea36976666c2378d37ed63` |
| Quarantined copy | `spctl -a -t open` → `accepted — source=Notarized Developer ID`; mounted, copied to `/Applications`, `spctl -a` → `accepted`, `CFBundleShortVersionString` 0.3.10 |
| Installed app launched | sidecar answered `/v1/health` with `{"status":"ok"}` from `/Applications` (not a translocated copy) |
| **The shipped binary captures the first message** | the installed `openworker-server`, driven over `/ws/session/…?workspace=&agent=cowork` — the GUI's first-connect shape — captured `attachment:table.png` (the same 57,380-byte PNG from the recorded conversation), wrote `fp/attachments/3cfdf8df967d4641.png` and recorded `mode='both'`, `channel='message'` |
| The shipped read guard | `read_file('fp/grt-overall-structure.png')` on the 768,395-byte artifact returns `not text: … holds binary data (768395 bytes)` — 165 characters instead of 918,976 |
| The light pack the user never got | with `both` declared, the build tree on the installed bundle's runtime rendered `theme='fp-v1-light'`, `appearance='light'`, 98,640-byte PNG / 99,210-byte SVG |
| Mounted bundle contents | 9 rule files, 9 Pretendard weights, Node v22.16.0, 3,727 hashed entries in `BUILD-MANIFEST.json` |
| Published asset re-downloaded | `gh release download v0.3.10` returned 175,092,614 bytes, sha256 identical to the built DMG; quarantined copy `accepted — source=Notarized Developer ID`, ticket validates |

Still not run: a live-provider conversation in this build, and installation on a separate clean Mac.

## 2026-09-20 — 0.3.11: the footer band was painted over the brand mark

Two screenshots of the same 200px-tall strip: a correctly built FOUR PILLARS frame, and one
this product shipped. In ours `X(@VitalikButerin)` sat on top of the FOUR PILLARS wordmark.

`fp plan` on the exact document reproduces it with no rendering at all — the geometry says it:

```
Footer value Note    x=206  w=1086  right=1292
Footer value Source  x=1488 w=271   right=1759   ← brand mark occupies 1593..1850
Footer value Date    x=1988 w=172   right=2160   ← the frame is 1920 wide
```

`footerOps` walked the three entries left to right from a running `x`, each with `maxLines: 1`,
and never compared that `x` to anything. There was no right edge in the function. The note's
79 characters were legal (the gate capped it at 80, one line), so nothing upstream refused it;
the two entries after it paid. The date was not clipped or shrunk — it was drawn 68px past the
edge of the picture, silently absent from every PNG.

| Defect | Root cause | Fix and its test |
|---|---|---|
| `Source` drawn on top of the FOUR PILLARS mark | entries placed from a running `x` with no boundary | the brand mark's left edge minus `brandGap` is the band's right edge; an entry that no longer fits starts a new row. Kit test asserts every footer op's right edge ≤ 1592.57 |
| `Date as of` drawn at x=1988 on a 1920px frame | same | it moves down beside `Source`; the kit test asserts all three values are still drawn and that the two short ones share a row |
| A long note could only be one line, so the gate capped it at 80 characters | `maxLines: 1` on the footer value | the value wraps to two lines at `valueLineHeight` 1.3; the cap is now 180, the measured two-line capacity. The designer's own reference note (171 characters) renders in two lines, unbroken |
| A taller band would have been drawn over the content | `plan.ts` reserved the constant `footer.height` | the footer is laid out before the content budget and the frame reserves what it measured. Kit test asserts the band grows upward and content still clears it |
| Text the band genuinely cannot hold would be truncated to `…` | nothing inspected the renderer's own report | `fp_render` refuses when `layout.clipped` names the `footer` role, quoting what was cut. A 170-character Korean note (one em per glyph) is refused rather than halved |

Verified with the real compiler and the shipped fonts, not a mock: rendering the user's own
failing document now produces `Note` on its line, `Source` and `Date as of` on the next, and
nothing right of x=1544.57. The same three kit tests fail on the previous commit
(`Footer value Source reaches 1759, the brand mark starts at 1592.57`, `note drew 1 line(s)`,
`the taller band did not grow upward`) and pass on this one.

fp-kit moves to `17c89e711220d1d44977a2a21ec0bfea41339b6a`. Suites: 2,198 passed / 1 skipped
in the assembled tree, fp-kit 60, repo 8.

## 2026-09-20 — 0.3.11: signed, notarized release build

Assembled into `/Users/steve/Developer/fp-studio-release-0.3.11` from the pinned commits
(openworker `5bc10d92`, fp-kit `17c89e71`), then `packaging/build_fp_studio_dmg.sh --release`.

| Check | Result |
|---|---|
| Upstream GUI comparison | 44 GUI files equal upstream + 221 declared edits, 5 declared additions, no undeclared change |
| Design rules staged | `fp-design-system@5d9787297db0`, `fp-design-table@5c8fb12a2bfa`, `fp-design-chart@a8a7dba5510c`, `fp-design-flowchart@dbc5e15f5c38`, `fp-design-reproduce@e661096cd057` |
| Python gate in the build tree (real resvg, real permission integration, supplied fonts) | 195 passed |
| Full assembled suite, FP plus upstream | 2,198 passed, 1 skipped |
| fp-kit `npm test` | 60 passed |
| Original GUI unit tests + production build | 189 tests / 27 files passed, build succeeded |
| Fork shell smoke E2E | 2 passed |
| Notarization | submission `9950c3ba-9f8b-4e96-84bb-83681f3f7c47`, `status: Accepted`, stapled, `stapler validate` worked |
| DMG | `FP Studio_0.3.11_aarch64.dmg`, 175,099,942 bytes, sha256 `eac7fdebcc4833512f9404955d92ca6bc54534ce896559afb60bd7b419a32144` |
| Quarantined copy | `spctl -a -t open` → `accepted — source=Notarized Developer ID`; mounted, copied to `/Applications`, `spctl -a` → `accepted`, `CFBundleShortVersionString` 0.3.11 |
| Installed app launched | sidecar answered `/v1/health` with `{"status":"ok"}` from `/Applications` |
| **The band the user photographed, through the installed bundle** | the failing document (`note` 79 chars, `source` `X(@VitalikButerin)`, `dateAsOf`) rendered on `fp-kit/17c89e711220d1d44977a2a21ec0bfea41339b6a`: `Note` on its own line, `Source` and `Date as of` on the next, `layout.clipped` empty, nothing right of x=1544.57 — the mark starts at 1593 |
| The reference frame's own note | the 171-character note renders in two lines, breaking after "ETHB operator" exactly as the reference does, with `Source` below it |
| Both packs | `fp-v1` and `fp-v1-light` both correct in the shipped bundle; the light pack inherits the fixed chrome by `extends` |
| Published asset re-downloaded | `gh release download v0.3.11` returned 175,099,942 bytes, sha256 identical to the built DMG; quarantined copy `accepted — source=Notarized Developer ID`, ticket validates |

Still not run: a live-provider conversation in this build, and installation on a separate clean Mac.

## 2026-09-21 — 0.3.12: a screenshot read as 367,000 tokens, so the first turn compacted itself

Reported: `Context trimmed — oldest turns dropped (summary unavailable)` kept appearing, and the
`Context compaction failed — the summarizer couldn't condense this session's history` prompt came up
in a conversation that had **just started**. In the same conversation the agent then asked the user
to confirm a figure it had supposedly copied off the attached image ("Asia: 1697 validators") and
asked which of three screenshots taken that morning it should use — while the image was attached to
the message it was answering.

One cause. `compaction.estimate_tokens` serialized each message and divided by four, and an
attachment travels as a `data:` URL inside an `image_url` content part (`attachments.py:35-61`).
Measured on the reported size, a 1.1 MB PNG:

| | |
|---|---:|
| base64 characters in the data URL | 1,466,672 |
| `estimate_tokens` of `[system, user+image]` | **367,816** |
| trigger — no MATRIX entry for the model, so `min(0.8 × 128,000, cap)` | **102,400** |
| what that turn actually costs the model (image ≈ 1,600 + text) | ≈ 1,800 |
| outbound estimate AFTER the compaction it forced | **1,242** |

So compaction fired 3.6× "over" a threshold the session was using about 1% of. `pick_boundary`
returned 2 — the earliest legal boundary once one assistant message exists — so the span was
`[system, user]`: the user's only message. `_text_of` renders an image as the literal string
`[image]` (`compaction.py:269-280`), which is then the model's entire memory of the picture it was
asked to redraw. Verified by running the real functions on that message list: `image still visible
to the model: False`. Every later turn that carried an image did the same thing, which is what made
the notice repeat; when the summarizer call itself also failed, the bare `except Exception`
(`engine.py:664`) discarded the reason, logged nothing, and put an unexplained Retry/Trim dialog on
screen.

Four changes, all in the pinned upstream files, declared in `docs/DIFF-POLICY.md`:

1. `estimate_tokens` prices content parts: text by chars/4, an `image_url` data URL at
   `IMAGE_TOKENS` (1,600 — Anthropic's ceiling for a full-size image), a `file` data URL at
   `FILE_TOKENS`. Four megabytes of the same picture now costs the same as one.
2. `apply_to_outbound` carries the newest `CARRY_IMAGES` (2) reference images across the boundary
   with the compacted block, pulled from the canonical list at outbound time, so nothing is stored
   twice and the block stays byte-stable for prompt caching.
3. `trigger_tokens(..., cap_explicit=True)`: with no verified context window the 128,000 default is
   a guess and `min` can only lower a guess, so the Settings token cap was inert — typing 1,000,000
   still compacted at 102,400. A cap the user typed now sets the trigger; a verified window still
   wins.
4. The summarizer failure reason is kept: `logging.warning` in the sidecar log, appended to the
   trim notice, and shown in the Retry/Trim prompt — plus a 1.5 s pause before the single retry,
   because the common cause is a 429 and an instant retry lands in the same window.

| Check | Result |
|---|---|
| New regression file `tests/test_compaction_attachments.py` | 10 tests; **9 fail on the previous commit** — the headline one reports `a brand-new session estimated 366,733 tokens against a 102,400 trigger` |
| Engine end-to-end | after a forced compaction, `engine._outbound_messages()` still carries the attached image and the `<compacted-history>` block |
| Upstream compaction suites, unchanged | `tests/test_compaction.py` + `tests/test_compaction_engine.py` 31 passed |
| Patch table | `scripts/regen_edits.py` → 274 hunks across 71 paths; a fresh assembly is byte-identical to the hand-edited tree for all four touched files |
| Full assembled suite | 2,208 passed, 1 skipped |
| The reported document, rendered through the installed 0.3.11 bundle | "Where Monad's Validators Run" (KPI row + region bar chart, dark) rendered clean at revision 1, the Asia sub-label edit committed revision 2, `layout.clipped` empty both times, footer correct — the render/publish path was not the defect; the wrong figure came from a model that could no longer see its source |
| Publish path, re-read | `fp_publish` re-renders nothing: it exports the bytes committed for the requested revision (`store.publish` → `materialize(name, expected)`), and every `fp_render`/`fp_edit` runs the worker again, so a final PNG cannot be a stale copy of an earlier one |

Known gap, unchanged by this build: `fp_render` refuses a clipped layout only for `role == 'footer'`
(`tools/fp.py:543-553`). Clipping reported for any other role still commits.

### Signed, notarized release build

Assembled into `/Users/steve/Developer/fp-studio-release-0.3.12` from the pinned commits
(openworker `5bc10d92`, fp-kit `17c89e71`), then `packaging/build_fp_studio_dmg.sh --release`.

| Check | Result |
|---|---|
| Upstream GUI comparison | GUI files equal upstream + the declared edits; no undeclared change |
| Python gate in the build tree (real resvg, real permission integration, supplied fonts) | 195 passed |
| Full assembled suite, FP plus upstream | 2,208 passed, 1 skipped |
| fp-kit `npm test` | 60 passed |
| Original GUI unit tests + production build | passed, build succeeded |
| Fork shell smoke E2E | 2 passed |
| Notarization | submission `cfcc4261-cbb4-4984-938c-aac3fbde8599`, `status: Accepted`, stapled, `stapler validate` worked |
| DMG | `FP Studio_0.3.12_aarch64.dmg`, 132,907,134 bytes, sha256 `6abf6521b6926bda32ee81246e07ccbf281e435785b6a4cf34bec4d7691806b5` |
| Quarantined copy | `spctl -a -t open` → `accepted — source=Notarized Developer ID` |
| Installed and launched | copied to `/Applications`, `spctl -a` → `accepted`, `CFBundleShortVersionString` 0.3.12, sidecar answered `/v1/health` with `{"status":"ok"}` |
| **The fix is in the shipped binary** | `coworker.compaction` extracted from the bundled PyInstaller archive at `/Applications/FP Studio.app/Contents/Resources/sidecar`: `IMAGE_TOKENS`, `CARRY_IMAGES`, `cap_explicit`, `_part_chars`, `carried_images` and the carry-forward notice are present, and `coworker.engine` carries `_COMPACTION_RETRY_DELAY`, `_compaction_reason` and the failure log line |
| Published asset re-downloaded | `gh release download v0.3.12` returned 132,907,134 bytes, sha256 identical to the built DMG; quarantined copy `accepted — source=Notarized Developer ID`, ticket validates |

Still not run: a live-provider conversation in this build, and installation on a separate clean Mac.

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
