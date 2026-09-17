# Downstream diff policy

The user's approved product is the stock OpenWorker GUI with an infographic capability.

Allowed changes:
- Register FP capability and append product-specific instructions to the existing Cowork agent.
- Add intrinsic FP write-risk/path rules without weakening stock permission floors.
- Capture successful existing web_fetch results without replacing web networking or bypassing approvals.
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
  stock attachment path changes.
- Add `fp_capture_image` and the `fp-design-reproduce` rules for redrawing a supplied source. A
  captured reference is no longer opt-in: `fp_render`/`fp_edit` refuse a document that neither
  transcribes it nor records the user's own words in `referenceWaiver`.
- Serve the per-grammar design rules back at `fp_review` as an addressable checklist, and refuse
  `fp_publish` until every rule has a verdict. Same stock tools, same chat — no review screen.

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
