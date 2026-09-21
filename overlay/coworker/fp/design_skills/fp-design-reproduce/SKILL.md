---
name: fp-design-reproduce
description: MANDATORY rules for redrawing a source the user supplied — an attached image, or a diagram, mermaid graph or table pasted into the message. Transcribe before you draw, keep the source's grammar, structure, wiring, data and copy, change only the visual system.
allowed-tools: fp_design_rules, fp_capture_image, fp_inspect, fp_source, fp_source_text, fp_render, fp_edit
---

Required by `fp_render` and `fp_edit` for any document that names a `reference`. Load
`fp-design-system` first, plus the grammar skill the source uses (`fp-design-table`,
`fp-design-chart` or `fp-design-flowchart`) — those rules apply on top of these.

---

I N F O G R A P H I C   S Y S T E M   ·   R E P R O D U C E
Guideline for redrawing a supplied source

When the user hands over the thing to draw — an attached image, or an ASCII diagram, a
mermaid graph or a table pasted straight into the message — the source has already
decided what the visual says. You are re-typesetting it, not re-authoring it. The
grammar, the number of blocks, their reading order, the levels, the arrows, the
categories, the series, the values and the copy come from the source. The type scale,
the palette, spacing, strokes, corner radii and the frame come from the FP system.
A paste is not a briefing to interpret. Text is a source too.

Transcribe first
Do
Read the source and write `reference.blocks` in its reading order: one entry per block
the source shows, each with the `kind` (and `template` for a chart or a diagram) the
source uses, its nodes and directed edges, its categories, its series and their values,
and the text it carries.
Use the source id `fp_inspect` lists under `references` — an attached image and a pasted
structure are both captured when the message arrives. `fp_source_text` reads the paste
back verbatim; `fp_capture_image` captures an image file from a granted root.
State what you could not read in `reference.note` and ASK the user; an unreadable axis
label is a question, not a guess.
Do not
Don't start composing before the transcription exists.
Don't transcribe "about 40" as 40 — if the source does not state a value, say so and ask.
Don't treat a pasted diagram as inspiration for a better one.

Keep the source's structure
Do
Same grammar as the source: a grouped bar chart stays a grouped bar chart, an
architecture diagram stays that diagram.
Same blocks, same order, same count.
Keep every level and every arrow: the same nodes at the same depth, each edge pointing
the way the source points it. A box that contains other boxes stays a container, not a
row of peers.
Keep the source's emphasis: a highlighted bar, a bold total row, a callout — reproduce it
with FP tokens.
Do not
Don't re-route to a grammar you consider better, and don't "upgrade" a table to a chart.
Don't flatten a multi-level diagram into two rows because it packs more neatly.
Don't rewire, reverse, drop or add an arrow, and don't promote a nested box to a peer.
Don't add a KPI strip, a summary card, an insight line, an icon set or a legend the
source does not have.
Don't drop a block because it looks redundant, and don't merge two blocks into one.
Don't reorder, re-sort or re-scale categories, and don't change an axis range to flatter
the data.

Keep the source's data and copy
Do
Every value in the output comes from the transcription, character for character.
Keep units, denominators, periods, footnotes and the as-of date exactly as shown.
Keep labels verbatim; translate only if the user asks, and then keep the original in the
note.
Do not
Don't round, rebase, convert units, recompute percentages or fill a missing value.
Don't rewrite a label into a punchier one, and don't invent a title, source or note the
source does not have. An unrequested footer note is not neutral: it sits across the
frame's bottom band, and nobody asked for it.

Change the visual system, and only that
Do
Bind every colour to an FP palette variable; map the source's colour roles (emphasis,
neutral, negative) onto FP's, keeping which series is emphasised.
Apply the FP type scale (minimum 24, multiples of 4), spacing, corner radii and stroke
weights.
Keep the source's aspect intent: a wide banner stays wide; a portrait card stays portrait.
Do not
Don't copy the source's raw hex, fonts, shadows or gradients into the output.
Don't keep a decorative flourish that the FP system does not have.

Before you report it done
Do
Re-read the source against the render, block by block, value by value, arrow by arrow.
Count the source's groups/colours and confirm the render uses the same number — a source
that marks three groups is not a monochrome render, and a source with no colour is not a
rainbow.
Tell the user plainly what you changed (the visual system) and what you kept (everything
else), and list anything you could not read.
Do not
Don't call a redraw verified because the gate passed: the gate checks that your output
matches YOUR transcription, never that your transcription matches the source.
