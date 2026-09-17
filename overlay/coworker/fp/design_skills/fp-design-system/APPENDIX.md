# fp-design-system — verbatim FOUR PILLARS guideline (appendix)

Served by `fp_design_rules('fp-design-system', appendix=True)`, not by default: the
decision card in SKILL.md carries what you author, this file carries the frame
arithmetic, Figma node ids, exact strokes and marker geometry behind it. Both files
are covered by the skill's digest.

---
# FP infographic design system — index

This skill is a **hard gate**, not advice. `fp_render` and `fp_edit` refuse a document whose
`design_rules` acknowledgement does not include this index plus every per-grammar skill the
document's grammars require. Load them with `fp_design_rules(kind)` and pass the returned
digests back to `fp_render` or `fp_edit`.

## Routing — which skill each grammar requires

| Grammar in the document | Required skill |
|---|---|
| every document, always | `fp-design-system` (this file) |
| `table` block, `table` template | `fp-design-table` |
| `bar`, `line`, `scatter`, `area`, `combo`, `waterfall`, `donut`, `radar`, `polar`, `treemap`, `funnel`, `pyramid`, `venn`, `quadrant`, `gantt`, `sankey` | `fp-design-chart` |
| `flowchart`, `architecture`, `data-flow`, `deployment`, `dependency`, `tree`, `sequence`, `swimlane`, `layers`, `state`, `er`, `uml-class`, `db-schema`, `nested`, `org-chart`, `process`, `loop`, `timeline`, `journey`, `story-map`, `kanban`, `fishbone`, `wardley`, `high-level`, `medallion`, `dp-integration`, `it-state`, `matrix` | `fp-design-flowchart` |

## What is machine-checked and what is on you

Both write tools mechanically reject: text sizes below 24 or off the 4-grid, raw hex where a
palette variable is required, empty/placeholder required fields (H1/H2/Source/Date as of/
Note), and a missing acknowledgement for a required skill. Everything else in these rules —
emphasis choice, legend marker shape, slanted axis labels, vector strokes, fidelity to the
sample — is enforced by you following the text below, and by the user's review. A passing
render is not proof the design rules were honoured.

---

# I N F O G R A P H I C   S Y S T E M   ·   F L O W   N O D E S
Prompt Guideline for Claude
FP color palette / slanted x axis data / label text size 28 pt

[Basic Design System Rules for Claude]

Refer to the FP Infographic Design Guide.

Frame & layout

Do
Clone the Frame Guide (209:3364) and use its existing chrome and background.
Fit the infographic to safe zone, starting at x112, center-aligned.
Rename the cloned frame (its layer name) to the infographic's title, so it's identifiable in the file.
The red zone is the FP infographic layout grid — the frame's red layout-grid bands — a frame property, not a layer. Read frame.layoutGrids. Margins: bottom red band 164px, sides 112px. Keep the whole table inside the clear area, and never mistake a red band for empty space to fill.
Set the frame height so the table bottom clears the bottom red band by ~10px. Footer + logo sit in the bottom band (42px bottom margin); the watermark is centered vertically. When unsure, match a known-good infographic (e.g. 500:71).
Gap between the title and the infographic is 98px — measured from the H2 bottom if an H2 exists, otherwise the H1 bottom (infographic top = title bottom + 98).
Tables fill the full 1696px width (don't shrink columns to text width). Charts may fill the width when it suits the data, but it isn't required — illustrative diagrams (payoff diagrams, flowcharts) use their natural proportions, centered in the safe zone, not a forced stretch.
Resize the frame height to fit the content.
After resizing, set the footer and watermark Y last so bottom info (Source, Date, Note, logo, watermark) stays bottom-aligned and bottom-pinned.
Delete any empty required field (H1 / H2 / Source / Date as of / Note).
If the brief has no H2 (subtitle), delete the H2 node entirely — never leave its placeholder text. Find it by its SemiBold title weight / placeholder, not a fixed font size (the guide's H2 may be 28 or 32).
Do not
Don't rebuild the chrome.
Don't shrink table columns to text width — keep 1696px unless asked.
Don't treat 1408px as a fixed height.
Don't leave the footer or watermark floating after a resize.
Don't exit / exceed the safe zone layout
Don't leave empty dead space inside the safe zone
Don't ship placeholder text in an empty frame field.
Don't delete the FOUR PILLARS watermark or any chrome the Frame Guide ships with — only the empty required fields (H1 / H2 / Source / Date / Note) get removed.
Don't add elements the frame doesn't already have (no divider under the title, no extra lines or decorations). Reference/sample frames show the look, not parts to copy in.
Frame Guide + this guideline are the source of truth; a task brief only fills blanks (title, source, highlight) and never overrides a frame value or a rule here — if a number conflicts, the frame wins.

Typography
Do
Use Pretendard, via the file's font styles.
Default to Regular 28 — body text is ALWAYS 28 unless there's a special reason. Hierarchy: H1 Bold · H2 SemiBold 32 · body Regular 28 · 설명 / details Regular 24. MINIMUM size is 24 (never 22), and 24 is rarely used — reach for 28 first. Maximum may vary but keep the rules of 4.
Bind text to the color styles / variables (Regular Slate 100 · Unimportant Details  Slate 200).
Do not
Don't use raw hex for text — bind to the color variables.
Don't use any font other than Pretendard / the file styles.
Don't add size or weight emphasis beyond the defined hierarchy.

Color — decide the situation first
Do
Identify the situation first: single highlight, categorical, no highlight, or brand.
Single highlight / comparison: slate base + one point color on the highlight only. Highlight = 1A1B1D 50% fill behind the text, with the 1.2px accent stroke + 18% accent glow (radius 10) on a separate layer on top so the table border/dividers don't cover the outline — like the flowchart node.
Categorical (multiple distinct series): use the FP categorical palette (the 8 muted hues).
No highlight: slate palette only.
Company / brand chart: use the company's real key color, sampled from the logo asset in the file.
Only point-color what the sample highlights.
Never drop a color the sample has, and never invent one. If an element is colored in the sample (e.g. red step labels), it stays colored in the output — keep the information.
Colors always come from the FP palette variables — read the palette, don't eyeball a hex off the sample. Map the sample's color to the nearest FP palette color and bind to that variable (red → Coral/500 #D2705E = Semantic/Negative; the system has no pure red).
In charts, color only the series the sample colors — keep reference/guide lines (baseline, strike, axes) the same neutral, not their own hue.
All lines use the same stroke weight — 2.5pt by default — unless the sample infographic shows different weights.
Do not
Don't make a categorical chart monochrome.
Don't substitute or approximate a company's brand color.
Don't highlight any part that isn't highlighted in the sample.
Only the top row (column headers) gets the #3C3E44 25% fill + Bold text. The first column is bold row-labels — Bold text, but NOT shaded. Data cells: no fill, Regular Slate/200.
Never shade the first column — the #3C3E44 shade belongs to the top row only. Shade the first column solely if the sample itself clearly shows that column with its own darker background (rare); default is bold text, no shade. Otherwise keep data cells uniform and add no emphasis the sample doesn't show (e.g. a totals row).
Any filled cell (header / row header) must fill the row height, not hug its text — set vertical sizing to FILL. A hugging filled cell leaves an unfilled strip when a sibling cell in the row wraps taller.
Table container: Slate/900 fill @ 30% opacity (bound), Slate/600 1px inside border, radius 16, clip; header row #3C3E44 @ 25%.
Table highlight (highlight only the row/column the sample marks — 행 = row, 열 = column): 1A1B1D 50% fill behind the text, plus a 1.2px accent stroke and 18% accent glow (radius 10) on a separate layer on top so the table border/dividers don't cover the outline; corner radius 12. Point-color only the highlighted row/column, nothing else.
