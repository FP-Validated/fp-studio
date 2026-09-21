# Downstream diff policy

The user's approved product is the stock OpenWorker GUI with an infographic capability.

Allowed changes:
- Register FP capability and append product-specific instructions to the existing Cowork agent.
- Add intrinsic FP write-risk/path rules without weakening stock permission floors.
- Register no web search and no page fetch: FP Studio draws the source the user supplies, so the research surface is removed rather than wrapped. The upstream tool factories are untouched; the patched `build_engine` does not register them, and the upstream test that asserted registration is patched to assert its absence.
- Attach renderer cancellation to the existing Stop mechanism.
- Add artifact refresh/open behavior in App and RightRail, preserving their JSX and CSS.
- Add a pure request-order helper and its tests.
- Isolate bundle ID, updater endpoints and local state paths; stage and sign renderer dependencies.
- Ship the FOUR PILLARS design rules as read-only skill data ahead of user skills, and enforce them in `fp_render`.
- Add subscription sign-in and model discovery inside the stock providers package, reached through the stock descriptor registry. No new screen: the existing Settings/provider setup renders them.
- Add a `ko` locale catalog beside `en`/`zh`, and locale/label strings for the above in the stock catalogs.
- Replace the app icon set with the fork's icons.
- Add one fork-owned E2E smoke spec (`surfaces/gui/e2e/fp-smoke.spec.ts`) as the release gate. The upstream
  suite pins upstream's product name and wording that this fork changes, so 181 of its 221 specs fail by
  construction; the fork's spec asserts the same shell under FP Studio identity, against the same mocks.
- Capture what the user supplies into the session workspace as FP sources when a message arrives:
  image attachments, and diagrams/tables pasted as text (box-drawing or arrow glyphs, an ASCII box
  rule, a markdown table, or a fence naming a diagram language). A redraw then names the source by
  id and sha256 instead of replaying a data URL, and a paste is readable evidence rather than a
  sentence in the transcript. Best-effort: a capture failure never blocks the user's message, the
  detector is deliberately narrow so prose and pasted code are not captured, and nothing about the
  stock attachment path changes. The workspace for that capture — and for a light/dark declaration
  answered through `ask_user` — is `manager.engine_workspace(...)`, the same resolution the engine
  binds, because the socket's `?workspace=` is empty on the connection that carries a new session's
  first message: the one with the attachment in it.
- Refuse `read_file` on a file whose first bytes are not UTF-8 text, naming the path and its size.
  Upstream decoded with `errors="replace"`, so a read of a rendered PNG returned 2,000 lines of
  U+FFFD (919,016 characters, re-sent on every later model call of the turn) and offered three more
  pages of it. Text files, including non-ASCII text, are unaffected.
- Add `fp_capture_image` and the `fp-design-reproduce` rules for redrawing a supplied source. A
  captured reference is no longer opt-in: `fp_render`/`fp_edit` refuse a document that neither
  transcribes it nor records the user's own words in `referenceWaiver`.
- Serve the per-grammar design rules back at `fp_review` as an addressable checklist, and refuse
  `fp_publish` until every rule has a verdict. Same stock tools, same chat — no review screen.
- Price an attachment in the auto-compaction estimate at what a vision/file call costs
  (`IMAGE_TOKENS`, `FILE_TOKENS`) instead of at the length of its base64, carry the newest
  `CARRY_IMAGES` reference images across the compaction boundary with the block, let a token cap the
  user typed raise the trigger for a model whose context window is not in the matrix
  (`cap_explicit`), and report why a summarizer call failed — in the log, in the notice and in the
  Retry/Trim prompt — with a pause before the single retry. A 1.1 MB screenshot is ~1.47 M base64
  characters, which chars/4 read as ~367 k tokens: a brand-new session compacted itself on its first
  turn, 3.6x "over" a 102,400 trigger it was using ~1,200 tokens of, the boundary landed after the
  user's only message, and the summary of the picture the user asked to have redrawn was the word
  "[image]". The model then worked blind and the trim notice repeated on every turn that carried an
  image. The trigger policy, the boundary rules and the spec'd Settings overrides are otherwise
  unchanged.

Not allowed without a new explicit product decision:
- Replacing App, Sidebar, Composer, Transcript, RightRail or artifact viewer.
- New Canvas, Inspector, project dashboard, template selection, prepared-layout onboarding or comment panel.
- A second chat engine, OMP requirement, Figma requirement, general agent-JavaScript execution in the privileged UI.

## How the gates work

Every change to a pinned-upstream file is declared: one entry per hunk in `scripts/fp_edits.py`
(path, anchor unique in the upstream blob, replacement, label), plus the replaced binary icons in
`assets/icons` and the re-serialised `tauri.conf.json`. `patch_openworker.py` applies that set and
writes what it applied to `.fp-patch-manifest.json` in the assembled checkout.

`check_upstream_ui.py` then proves by reconstruction, for every file under `surfaces/gui`:

    upstream blob at the locked commit + the recorded edits == downstream file, byte for byte

Downstream-only GUI files (the request-order helper, the `ko` catalog, the IME test) cannot be
reconstructed from an upstream blob, so they are enumerated in that gate and in `check_overlay.py`.
Regenerate the edit table from a reference checkout with `scripts/regen_edits.py`; never hand-edit
a hunk. A hand-edited hunk, a drifted anchor or an undeclared change fails assembly.

This is a regression guard for the intended patch, not a formal proof of every possible behavioral
difference.
