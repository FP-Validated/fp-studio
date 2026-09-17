---
name: fp-design-chart
description: MANDATORY rules for every FP chart grammar (bar, line, scatter, area, combo, waterfall, donut, radar, polar, treemap, funnel, pyramid, venn, quadrant, gantt, sankey) — bars, axes, gridlines, labels, the always-required legend, color situation, vectors and fidelity.
allowed-tools: fp_design_rules, fp_inspect, fp_source, fp_render, fp_edit
---

Required by `fp_render` and `fp_edit` for any document containing a chart grammar. Load
`fp-design-system` first — the frame, typography and color rules there apply on top of
these. The legend is not optional.

Bar fills, axis and gridline strokes, tick and label sizes, the slant angle and the legend
marker geometry are the renderer's: it draws them from the Bar Chart frame and the Chart
Label System, and they are verbatim in
`fp_design_rules('fp-design-chart', appendix=True)` for when a rendered chart has to be
inspected against a number. This card is the part you author.

---

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
Don't give every bar the accent color — only the ones the sample highlights.

Legend — always include
Do
Always reproduce the legend.
Match the marker to how the series is drawn: a bar / stacked / area series takes a square, a line takes a line, a reference / forecast / threshold takes a dashed line, a scatter / point takes a dot, a named company / token / entity takes a logo chip.
Do not
Don't drop the legend when importing a chart graphic.
Don't use a dot for a bar / area series — use a square (marker mirrors render type).
Don't mismatch marker count, shape, or color to the series.

Fidelity
Do
Reproduce every data point, label, and axis value exactly as in the sample.
After building, double-check every value, label, axis, color, and legend marker (shape, color, count) against the sample.
Do not
Don't add, change, or drop any value or label.
Don't invent a series, legend entry, or highlight the sample doesn't have.
Don't relabel, reorder, or round values differently from the sample.
Don't drop the axis titles.
Don't leave x-axis labels horizontal — always slant them.
