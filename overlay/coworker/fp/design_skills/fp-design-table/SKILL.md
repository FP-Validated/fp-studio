---
name: fp-design-table
description: MANDATORY rules for every FP table grammar — container fill and border, header row, body rows, cell padding and fill sizing, merged key cells, fields and data fidelity.
allowed-tools: fp_design_rules, fp_inspect, fp_source, fp_render, fp_edit
---

Required by `fp_render` and `fp_edit` for any document containing a table grammar. Load
`fp-design-system` first — the frame, typography and color rules there apply on top of
these.

The container fill and border, header-row fill, cell padding, fill sizing and merged-cell
arithmetic are the renderer's: it draws them from the Table frame, and they are verbatim in
`fp_design_rules('fp-design-table', appendix=True)` for when a rendered table has to be
inspected against a number. This card is the part you author.

---

Width & emphasis
Do
Build the table at full 1696px width.
Keep emphasis the sample actually has (e.g., a bold totals row), exactly as shown.
Highlight only the row or column the sample marks (행 = row, 열 = column) — point-color nothing else.
Do not
Don't shrink columns to text width — full 1696px unless asked.
Don't make the first column brighter, whiter, or bolder than the rest.
Don't add emphasis the sample doesn't have.
Don't remove emphasis the sample does have.
Don't shade a column: the header shade belongs to the top row only.

Fields & Data
Do
Delete empty Note / Date / Source fields — no placeholder text.
Re-check every value against the sample, character-by-character, at the end.
Do not
Don't add, change, or drop any data or label.
Don't invent a source, note, or subtitle the sample doesn't have.
