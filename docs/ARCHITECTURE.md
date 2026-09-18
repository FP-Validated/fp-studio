# FP Studio architecture, v0.3

## Product boundary

OpenWorker is the application, not merely a backend to a replacement app. Its React/Tauri shell, transcript, composer, sidebar, session navigation, settings, approvals and artifact viewer remain. FP adds a capability to the existing Cowork agent and a deterministic renderer process. It does not add a second agent loop, Figma, OMP, a canvas editor or a template gallery.

```text
Original OpenWorker conversation
  user + agent + existing ask_user (no web search, no page fetch)
           |
  FP brief, the sources the USER supplied, claims, free composition
           |
  fp_render(expected document + research revisions)
           |
  bounded child process running the pinned FP compiler
           |
  static outlined SVG -> resvg -> actual PNG
           |
  one SQLite transaction: source + receipt + SVG + PNG
           |
  repairable artifact files -> original Artifact Viewer
```

## Ownership

| Owner | Responsibility |
|---|---|
| OpenWorker | Models, chat, permission evaluation, web networking, attachments, session lifecycle |
| FP research module | Captured text receipts, brief, claim bindings, review findings |
| FP tools | Revision checks, operation intent, commit/publication behavior |
| Original FP compiler | Semantic composition, layout and its own compiler audit |
| Render controller | Child process limits, environment filtering, Stop hook and cross-process render lock |
| SQLite Store | Immutable revisions, sources, publication receipts and authoritative artifact bytes |
| Original GUI | User conversation and artifact display; no new editing surface |

## Light or dark is the user's call

Every colour in a frame comes from one theme pack, so the pack is not a preference to be
inferred: a render before the user has said light or dark is a guess presented as a result.
`fp_render` refuses until the declaration exists, and the refusal names the single call that
produces one. Nothing the model writes can satisfy it - a document field is the model's own
text, and a gate whose way out is a string the model composes is not a gate.

Two channels carry the user's words and both record the same way: the message they type
reaches `capture_turn`, and an answer to `ask_user` comes back through the server's
`question_asker`. A colour word alone is not a declaration, or "Batch Prover And Light
Client Prover" would silently choose paper; a mode word beside it, a Korean particle
("다크로"), or a message short enough to be an answer is.

The light pack is the dark pack's measured DIFFERENCE, resolved by `loadTheme` through
`extends`, because two full copies of 560 fields drift and the drift is invisible until it
renders. The neutral ramp is mirrored by rank, so paper and ink trade places while every
role reference stays as it was; chromatic colour keeps its hue and loses only enough
lightness to clear 3:1 against paper. Measured overrides beat both rules and each names the
Figma node it was read from. A rendered receipt pins every file in the chain, so a base
edited afterwards moves the fingerprint.

A light version and a dark version are two artifacts, not two revisions of one: rendering an
existing document with the other pack is refused, and the refusal says to use another name.

## Source versus authority

Evidence is what the user hands over: an attached image, a structure pasted into the message, a file under a granted root. This build registers no web search and no page fetch. A user who attaches a source asked for that source, and the delivered failure this removal exists for is a frame whose numbers came from a page the model found rather than from the image in the message. The tool factories remain upstream; the FP build does not register them.

A local source receipt proves which file bytes were captured, not who authored the file. A captured excerpt is not proof of correctness or entailment. Numeric bindings link an exact typed source-document value to a stated claim; they cannot establish that a chart's interpretation is fair. Text-only statements and numbers embedded in arbitrary prose are not exhaustively classified by the numeric coverage check.

The agent and user still resolve purpose, audience, comparison periods, denominators, units, disputed evidence and presentation. There is no automatic aesthetic score and no claim that a successful compiler audit is a perfect infographic.

## Read/write boundary

The original risk base receives eight intrinsic WRITE_LOCAL entries: `fp_render`, `fp_edit`, `fp_restore`, `fp_research`, `fp_research_edit`, `fp_capture_source`, `fp_publish`, `fp_repair`. `fp_edit` and `fp_research_edit` apply JSON-pointer ops to the committed revision and then take the identical grammar/design/CAS/compiler path as a full render, so a cheaper argument is not a weaker write. Existing Plan/read-only rules deny these operations. The path resolver supplies the controlled `.fpstudio` and `fp/` targets. Existing user approvals remain visible, without a new modal system.

`fp_inspect`, `fp_source`, `fp_source_text`, `fp_guide`, `fp_history`, `fp_review` read state. They return bounded payloads (outline, hashes, slices, windows) because every tool result is replayed on each later model call; the store keeps the full document, receipts and fonts. Store initialization is a platform storage concern; these tools do not silently repair or replace presentation files. Repair is an explicit write tool.

The existing Cowork file and shell tools remain. Therefore neither the permission rules nor this addition are an OS security sandbox against arbitrary local code.

## Concurrency and crash behavior

Both `expected_revision` and `expected_research_revision` are checked before render and at commit. SQLite WAL and FULL synchronous transactions keep source and both output byte streams together. Concurrent writers using one expected revision cannot silently replace each other.

Renderer computation happens before the write transaction. A separate per-workspace file lock serializes the expensive process across sessions/processes. Stop kills the current process group, with an additional cancellation checkpoint before DB commit. Once a transaction has committed, Stop cannot retroactively undo it; history remains available.

The visible SVG, PNG and source file are separate filesystem objects and cannot be atomically replaced as a group. They are **caches**, not the source of truth. Materialization is serialized against new DB commits; a crash between file replacements can leave stale aliases. `fp_inspect` reports this, and approval-gated `fp_repair` reconstructs aliases from the database. Final exports live under `fp/exports/<name>/rNNNNNN.*`, avoiding live-name collisions. Source reports also include the research revision in the filename.

## Live preview without redesign

Only App and RightRail behavior hooks change, plus a pure TypeScript request-order helper:

- Successful FP render/restore returns `_display.fp_preview` metadata.
- The original engine already lifts `_display` onto its existing tool-finished event.
- App dispatches the existing `OPEN_ARTIFACT_EVENT` after a successful FP tool.
- RightRail continues to render its existing artifact component; a latest-request guard prevents stale results and session cross-talk.
- Already-open PNG stays selected when the corresponding SVG is updated.
- There is no token-by-token renderer. Updates occur at valid render checkpoints.

The updater, bundle identity and app state directory are isolated from upstream. The original React layout and labels are not redesigned. The UI guard compares against the locked upstream commit, including committed downstream changes.

## Versioning

A renderer receipt includes compiler commit, runtime version, compiled SDK JS hashes, Node/resvg versions, theme bytes and font hashes. A different fingerprint requires explicit runtime upgrade acknowledgement before a new render can commit. Prior artifacts remain readable without re-rendering. This is not a multi-version SDK installer or a promise of cross-platform bitwise raster equality.

v0.2 legacy files are imported explicitly with `python -m coworker.fp.migrate`. The import validates all source/artifacts before one database transaction and preserves originals. It does not migrate the discarded v0.1 custom app.

## Resource limits

Input JSON: 2 MiB, depth 64, 10,000 entries per array, safe finite numeric range. Renderer: 45-second combined queue/run budget, V8 heap flag 384 MiB, stdout 80 MiB, stderr 1 MiB. Text SVG: 8 MiB; outlined SVG/PNG: 32 MiB each; raster: 16 million pixels. Fonts: at most 24 files, 32 MiB each, 96 MiB total. Research source archive: 64 MiB; render history: 512 MiB.

These are application budgets, not a hard process RSS ceiling. WASM, native buffers, multiple browser copies and the original agent process need real Mac profiling. History is not silently pruned; the user must archive a full workspace when a quota is reached.

## Remaining qualification

Full original source assembly, dependency locks, original permission tests, all-grammar visual fixtures, production font/resvg output, full GUI E2E, cloud provider calls, native WebKit behavior, clean-Mac installation and signing/notarization have not been qualified in the Linux execution environment.
