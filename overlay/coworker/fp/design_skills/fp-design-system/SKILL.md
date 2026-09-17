---
name: fp-design-system
description: MANDATORY index for every FP infographic. The FOUR PILLARS frame, typography and color rules, plus which per-grammar design skill (table, chart, flowchart) fp_render requires for the grammars you are about to use.
allowed-tools: fp_design_rules, fp_inspect, fp_source, fp_render, fp_edit
---

# FP infographic design system — decision card

This skill is a **hard gate**, not advice. `fp_render` and `fp_edit` refuse a document whose
`design_rules` acknowledgement does not include this index plus every per-grammar skill the
document's grammars require. `fp_guide('draw', name='<grammar>[,<grammar>]')` returns those
contracts, these cards and the digest map in one call.

This card is the part you author. The frame arithmetic, Figma node ids, exact fills, stroke
weights, marker geometry and the full grammar → skill routing table are verbatim in
`fp_design_rules('fp-design-system', appendix=True)` — read it when a check fails, when a
value is in doubt, or when a rendered artifact has to be inspected against a number. The
renderer draws the frame's chrome and background from the Frame Guide; you never author it.

## What is machine-checked and what is on you

Both write tools mechanically reject: text sizes below 24 or off the 4-grid, raw hex where a
palette variable is required, empty/placeholder required fields (H1/H2/Source/Date as of/
Note), and a missing acknowledgement for a required skill. Everything else in these rules —
emphasis choice, legend marker shape, slanted axis labels, vector strokes, fidelity to the
sample — is enforced by you following the text below, and by the user's review. A passing
render is not proof the design rules were honoured.

---

Frame & background
Do
Clone the Frame Guide (209:3364) and use its existing chrome and background.
Fit the infographic to safe zone, starting at x112, center-aligned.
Tables fill the full 1696px width (don't shrink columns to text width). Charts may fill the width when it suits the data, but it isn't required — illustrative diagrams (payoff diagrams, flowcharts) use their natural proportions, centered in the safe zone, not a forced stretch.
Delete any empty required field (H1 / H2 / Source / Date as of / Note).
Do not
Don't rebuild the chrome.
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
Single highlight / comparison: slate base + one point color on the highlight only.
Categorical (multiple distinct series): use the FP categorical palette (the 8 muted hues).
No highlight: slate palette only.
Company / brand chart: use the company's real key color, sampled from the logo asset in the file.
Only point-color what the sample highlights.
Never drop a color the sample has, and never invent one. If an element is colored in the sample (e.g. red step labels), it stays colored in the output — keep the information.
Colors always come from the FP palette variables — read the palette, don't eyeball a hex off the sample. Map the sample's color to the nearest FP palette color and bind to that variable (red → Coral/500 #D2705E = Semantic/Negative; the system has no pure red).
In charts, color only the series the sample colors — keep reference/guide lines (baseline, strike, axes) the same neutral, not their own hue.
Do not
Don't make a categorical chart monochrome.
Don't substitute or approximate a company's brand color.
Don't highlight any part that isn't highlighted in the sample.
