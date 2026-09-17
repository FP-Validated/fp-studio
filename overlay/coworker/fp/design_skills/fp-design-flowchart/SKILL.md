---
name: fp-design-flowchart
description: MANDATORY rules for every FP diagram grammar (flowchart, architecture, data-flow, deployment, dependency, tree, sequence, swimlane, layers, state, er, uml-class, db-schema, nested, org-chart, process, loop, timeline, journey, story-map, kanban, fishbone, wardley, high-level, medallion, dp-integration, it-state, matrix) — node boxes, vector connectors, V-arrowheads, and the color situation.
allowed-tools: fp_design_rules, fp_inspect, fp_source, fp_render, fp_edit
---

Required by `fp_render` and `fp_edit` for any document containing a diagram grammar. Load
`fp-design-system` first — the frame, typography and color rules there apply on top of
these.

Connectors, V-arrowheads, box padding, gaps and corner radii are the renderer's: it draws
them from the Flowchart frames, and they are verbatim in
`fp_design_rules('fp-design-flowchart', appendix=True)` for when a rendered diagram has to
be inspected against a number. This card is the part you author.

---

I N F O G R A P H I C   S Y S T E M   ·   F L O W   N O D E S
Guideline for Flowchart — decisions

Core rules (the ones people forget):
- Clone the Frame Guide and use its background; never rebuild the chrome.
  Diagram sits in the 1696px safe zone, centered.
- Pretendard (file's font styles). Bind colors to the design-system color styles.
- Color — decide the situation first:
  · No highlight → slate palette only.
  · Emphasize ONE node → keep every other node on slate, and style only that node
    (two-layer fill, point-color stroke, background blur, point-color glow; the exact
    values are in the appendix).
  · Count the COLORS in the sample, not the boxes. If several boxes share ONE color,
    that is ONE highlighted group → give them all the SAME accent. Do not hand out
    different hues to boxes the sample colors identically.
  · Multiple genuinely DISTINCT series (the sample itself uses different colors for
    different things) → FP categorical palette (8 muted hues), not monochrome.
  · Company / brand diagram → that brand's real key color (sample the hex), don't substitute.
  · Only color what the sample highlights — never add a highlight the sample doesn't have.
  · Never DROP a color the sample has either. Colored edge/step labels stay colored —
    the color carries information, it is not decoration to clean up.
  · Take colors from the FP palette variables — never eyeball a hex off the sample image
    and never substitute your own. Map the sample's color to the nearest FP palette color
    and bind the variable (red → Coral/500 #D2705E = Semantic/Negative; there is no pure red).
- Keep the exact box order, labels, and arrow directions — don't rewire the flow
  or rename a step.
- After building, re-check every box label and arrow direction against the sample, and
  confirm the number of distinct colors you used equals the number in the sample.
