# fp-design-chart — verbatim FOUR PILLARS guideline (appendix)

Served by `fp_design_rules('fp-design-chart', appendix=True)`, not by default: the
decision card in SKILL.md carries what you author, this file carries the frame
arithmetic, Figma node ids, exact strokes and marker geometry behind it. Both files
are covered by the skill's digest.

---
Required by `fp_render` and `fp_edit` for any document containing a chart grammar. Load
`fp-design-system` first — the frame, typography and color rules there apply on top of
these. The legend is not optional.

---

I N F O G R A P H I C   S Y S T E M   ·   F L O W   N O D E S
Guideline for table design

Match the "Bar Chart" frame (209:3523); use the Chart Label System (209:4188) for the legend. Follow the full Prompt Guideline (310:2) first — especially Charts and Vectors.
Bind to variables: Text/White (250:2) · Text/Grey 2 (250:4) · Text/Grey 3 (250:3). Structural colors: axis line #777B80, gridline #232B32, base-bar stroke #5E7388. Label grey: #AEB3B8.

Frame & Width
Do
Clone the Frame Guide (209:3364) and keep its background / chrome.
Build the chart at full 1696px width, content in the safe zone (x112).
Resize the frame height to fit, then set footer + watermark Y last.
Do not
Don't rebuild the chrome.
Don't shrink the chart to less than full width unless asked.

Bars
Do
Draw bars as rectangles with a translucent slate gradient fill.
Base bars: gradient fill + #5E7388 stroke, 1px.
Emphasized bars: same fill + the single point/accent color stroke, ~1.5px (heavier), plus the value label.
Keep bar width and spacing uniform across the series.
Do not
Don't give every bar the accent color — only the ones the sample highlights.
Don't vary bar width to fit labels.

Axes & Gridlines
Do
X and Y axis lines: pen vector stroke, #777B80, weight 2.
Value gridlines: pen vector stroke, #232B32, weight ~1.5.
Keep gridlines behind the bars.
Do not
Don't build any axis, gridline, or connector as a rotated rectangle — they are real vector strokes.
Don't drop the axis titles.

Labels
Do
Chart title: Pretendard Bold 32, Text/White.
Axis titles: Pretendard Medium 28, Text/Grey 2 (rotate the Y-axis title 90°).
Y-axis tick labels: Pretendard Medium 24, Text/Grey 2.
X-axis category labels: Pretendard Medium 26, Text/Grey 2, slanted (~48°).
Value labels on emphasized bars: Pretendard Bold 20, in the accent color.
Do not
Don't leave x-axis labels horizontal — always slant them.
Don't relabel, reorder, or round values differently from the sample.

Legend — always include
Do
Always reproduce the legend.
Match the marker to how the series is drawn (Chart Label System 209:4188):
bar / stacked / area → square (14×14, corner 3)
line → solid line
reference / forecast / threshold → dashed line (dash 4, gap 6)
scatter / point → dot
named company / token / entity → logo chip
Marker + soft glow, 16px gap to the label.
Label text: Pretendard Regular 23, grey #AEB3B8.
Do not
Don't drop the legend when importing a chart graphic.
Don't use a dot for a bar / area series — use a square (marker mirrors render type).
Don't mismatch marker count, shape, or color to the series.

Color — pick the situation
Do
One series emphasized: slate base + ONE point color, on that series only (fill at low opacity, 100% stroke, glow).
Multiple distinct series: the FP categorical palette (8 muted hues).
Company / brand chart: the brand's real key color, sampled from the logo asset in the file.
Color only what the sample highlights.
Do not
Don't make a multi-series chart monochrome.
Don't substitute or approximate a brand color.
Don't add a highlight the sample doesn't have.

Vectors
Do
Every chart line, axis, gridline, leader, and connector is a pen / vector stroke path.
Arrows are pen vectors with a V-arrowhead (Flowchart Arrows 209:3167).
Do not
Don't use a rotated rectangle as any line.
Don't fake an arrowhead.

Fidelity
Do
Reproduce every data point, label, and axis value exactly as in the sample.
After building, double-check every value, label, axis, color, and legend marker (shape, color, count) against the sample.
Do not
Don't add, change, or drop any value or label.
Don't invent a series, legend entry, or highlight the sample doesn't have.
