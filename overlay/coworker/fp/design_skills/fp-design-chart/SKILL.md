---
name: fp-design-chart
description: MANDATORY rules for every FP chart grammar (bar, line, scatter, area, combo, waterfall, donut, radar, polar, treemap, funnel, pyramid, venn, quadrant, gantt, sankey) — bars, axes, gridlines, labels, the always-required legend, color situation, vectors and fidelity.
allowed-tools: fp_design_rules, fp_inspect, fp_source, fp_render, fp_edit
---

Required with `fp-design-system` for any document containing a chart grammar. Bar fills,
axis and gridline strokes, tick sizes, the slant angle and legend marker geometry are the
renderer's, verbatim in the appendix for when a rendered chart must be inspected against
a number. This card is the part you author. The legend is not optional.

---

Color — pick the situation
Do
One series emphasized: slate base + ONE point color, on that series only (fill at low opacity, 100% stroke, glow).
Multiple distinct series: the FP categorical palette (8 muted hues).
Company / brand chart: the brand's real key color, sampled from the logo asset in the file.
Do not
Don't make a multi-series chart monochrome.
Don't substitute or approximate a brand color.
Don't add a highlight the sample doesn't have, and don't give every bar the accent color.

Two bars per row — the paired style
Do
Two bars per row (before/after, two dates) is `template:'bar'`, `style:'paired'`: name the series in `fields.columns` in the source's order and the legend, row label and both printed values come with it.
A value may be the source's own string (`839.8M`, `$0.58`): printed verbatim, its magnitude drives the bar.
Mixed units keep the default per-row scale — each row normalises to its own largest series, so the pair carries the fall and the printed numbers carry the level. One unit for every row: `scale:'shared'`.
`fields.unit` prints a unit under a row label, `fields.delta` a change column, `fields.group` a heading above each group.
Do not
Don't index a series to 100 to fake a pair, and don't drop one of the two series.
Don't put a second bar series in `fields.line` — that is a text column, not a bar.

Legend — always include
Do
Always reproduce the legend.
Match the marker to the render type: bar / stacked / area a square, line a line, reference / forecast / threshold a dashed line, scatter / point a dot, a named company / token / entity a logo chip.
Do not
Don't drop the legend when importing a chart graphic.
Don't mismatch marker count, shape, or color to the series.

Fidelity
Do
Check every value, label, axis title and legend marker against the sample.
Do not
Don't drop the axis titles, and don't leave x-axis labels horizontal — always slant them.
