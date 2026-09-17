# fp-design-flowchart — verbatim FOUR PILLARS guideline (appendix)

Served by `fp_design_rules('fp-design-flowchart', appendix=True)`, not by default: the
decision card in SKILL.md carries what you author, this file carries the frame
arithmetic, Figma node ids, exact strokes and marker geometry behind it. Both files
are covered by the skill's digest.

---
Required by `fp_render` and `fp_edit` for any document containing a diagram grammar. Load
`fp-design-system` first — the frame, typography and color rules there apply on top of
these.

---

I N F O G R A P H I C   S Y S T E M   ·   F L O W   N O D E S
Guideline for Flowchart

Build a flowchart infographic from the attached diagram, matching the Four Pillars
infographic design guide file (key: jBj4UaRajwWiexlIHv2WH3).

Before building, open and follow the "Prompt Guideline" frame (node 310:2),
especially the Vectors and Text boxes sections.

Core rules (the ones people forget):
- Clone the Frame Guide and use its background; never rebuild the chrome.
  Diagram sits in the 1696px safe zone, centered.
- Pretendard (file's font styles). Bind colors to the design-system color styles.
- Every connector is a real pen / vector stroke — never a rotated rectangle.
- Every arrow is a pen vector with a V-arrowhead (see Flowchart Arrows, 209:3167) —
  diagonal arrows included.
- Boxes: text-box padding 24 vertical / 40 horizontal, gap 16, corner radius 10.
  Use these numbers as written — don't copy spacing off an inspected reference box instead.
- Color — decide the situation first:
  · No highlight → slate palette only.
  · Emphasize ONE node → keep every other node on slate, and style only that node:
      – fill: TWO layers — #1A1B1D (Slate/900) at 50%, plus the POINT COLOR at 8% on top
      – stroke: point color at 60%, 1.2px
      – background blur
      – drop shadow in the point color (glow)
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
