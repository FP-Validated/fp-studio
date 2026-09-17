# fp-design-table — verbatim FOUR PILLARS guideline (appendix)

Served by `fp_design_rules('fp-design-table', appendix=True)`, not by default: the
decision card in SKILL.md carries what you author, this file carries the frame
arithmetic, Figma node ids, exact strokes and marker geometry behind it. Both files
are covered by the skill's digest.

---
Required by `fp_render` and `fp_edit` for any document containing a table grammar. Load
`fp-design-system` first — the frame, typography and color rules there apply on top of
these.

---

I N F O G R A P H I C   S Y S T E M   ·   F L O W   N O D E S
Guideline for table design
Match the "Table" frame (243:307). Follow the full Prompt Guideline (310:2) first; the rules below are the table-specific specifics.
Design-system variables to bind to: Slate/900 (249:19) · Slate/600 (249:16) · Text/White (250:2) · Text/Grey 2 (250:4).
Frame & Width
Do
Clone the Frame Guide (209:3364) and keep its background / chrome.
Build the table at full 1696px width, origin x112, top y300.
Resize the frame height to fit, then set footer + watermark Y last.
Do not
Don't rebuild the chrome.
Don't shrink columns to text width — full 1696px unless asked.
Container (table background)
Do
Fill: Slate/900 #1A1B1D at 50% opacity — bound to the variable.
Border: Slate/600 1px, inside align — bound to the variable.
Corner radius 16, clip content.
Do not
Don't use raw hex — bind fill and stroke to variables.
Don't apply 50% opacity to anything except the table background fill.
Don't put a gradient on the container.
Header Row
Do
Fill: solid #3C3E44 at 25%.
Bottom divider: Slate/600 1px.
Text: Pretendard Bold 28 / line-height 38, Text/White.
Do not
Don't use a gradient on the header.
Don't render header text any color or weight other than bold white.
Body Rows
Do
Transparent fill (no fill).
Bottom divider: Slate/600 1px; last row has no bottom border (the container border closes it).
Every cell, including the first column: Pretendard Regular 28 / line-height 38, Text/Grey 2.
Keep emphasis the sample actually has (e.g., a bold totals row), exactly as shown.
Do not
Don't make the first column brighter, whiter, or bolder than the rest.
Don't add emphasis the sample doesn't have.
Don't remove emphasis the sample does have.
Cells
Do
Padding 28 on all sides.
Cells fill the row height (vertical sizing = FILL, never hug) — so a filled cell's background covers the whole row even when a sibling cell wraps taller; text aligned top-left.
Merged / grouped key cells span and center in their group; the grouped column sets the row height.
Do not
Don't vertically center via counterAxisAlignItems — use text alignment.
Don't let a merged cell sit at the top of its group.
Fields & Data
Do
Delete empty Note / Date / Source fields — no placeholder text.
Re-check every value against the sample, character-by-character, at the end.
Do not
Don't add, change, or drop any data or label.
Don't invent a source, note, or subtitle the sample doesn't have.
