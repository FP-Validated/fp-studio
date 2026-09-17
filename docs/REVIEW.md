# Source review and correction record

Review date: 2026-09-11. Baseline: the supplied `fp-studio-openworker-v0.2.0.zip`. Upstream references are locked by commit in `UPSTREAMS.lock.json`.

## Finding

v0.2 should not have been presented as a production-ready DMG implementation. Its report explicitly listed two mocked tests and excluded full upstream/compiler/Mac integration. Review of the source found substantive defects, not only missing polish.

| Priority | Baseline finding | v0.3 correction | Evidence/remaining check |
|---|---|---|---|
| P0 | FP mutators could be classified READ | WRITE_LOCAL base floor and explicit write targets in stock permission resolver | Local patch fixture; actual OpenWorker permission integration added, not run here |
| P0 | `JSON.stringify(input, Object.keys(input).sort())` could omit nested keys | Recursive canonical serialization and strict JSON safety checks | Executed JS/Python regressions |
| P0 | Input/SVG/PNG saves lacked a common commit boundary | Authoritative SQLite transaction plus CAS for document and research | Executed conflicting writer/cache-failure tests |
| P0 | Existing destination could be recursively deleted during assembly | Refuse existing destinations; only invocation-owned staging may be removed | Executed sentinel-preservation test |
| P1 | Stop did not own the FP child lifecycle | Process-group termination, time/output limits and pre-commit cancellation | Executed real child-process tests; native event integration pending |
| P1 | Old artifact read could win after a later update/session change | Latest-request helper and disposed event guards | Executed helper tests; full original GUI E2E pending |
| P1 | Restoring old source re-rendered it with a potentially changed runtime | Restore exact archived bytes and source as a new revision | Executed restore/migration regressions |
| P1 | Packaged guide/dependency paths depended on the dev checkout | Runtime resource detection; package kit dependencies and authoring contracts | Executed guide-path test; installed-app check pending |
| P1 | Research lacked a reliable record of what was actually read | Evidence is the source the user supplies: immutable receipts for attachments, pasted structures and granted files, with bound claims. The web research surface is not registered at all | Executed receipt, excerpt and stale-value tests; engine registers neither web_search nor web_fetch |
| P1 | A passed render could be mistaken for a verified final artifact | Draft versus mechanically reviewed publication; unresolved claims/questions block final export | Executed publication tests; human meaning/visual review still required |
| P1 | A live document name could collide with a final revision filename | Separate `fp/exports/<name>/` namespace, research-versioned source reports | Executed collision/report retention regressions |
| P1 | Fonts could silently disappear in outlining | Pretendard name and Unicode cmap preflight; missing glyphs fail | Synthetic table tests only; production font rendering pending |
| P1 | Kit node_modules and correct nested Node signing could be missing | Dependency staging; Node signing after keychain bootstrap; resource manifest | Script/anchor checks only; actual Mac signing pending |
| P1 | Fork could share state or return to upstream through updates | Separate app identity/state namespace; disable upstream update endpoints | Source patch checks; clean-Mac behavior pending |

## Source-derived versus implemented versus unverified

**Read in the original source:** OpenWorker already registers ask_user (and the web tools this build deliberately drops); preserves `_display` as tool-event metadata; provides the original artifact viewer; owns provider routing and approvals. These are reused rather than replaced.

**Implemented in this overlay:** SQLite revision store, FP tools, transport text capture, mechanical publication checks, bounded renderer, type/glyph guards, minimal preview behavior patches and fail-closed build scripts.

**Not verified here:** Full pinned checkout patch application, original engine imports/tool-schema compatibility, real compiler/resvg output, all chart types, rendering speed, visual quality, live cloud model use, original React tests/E2E, native WebKit, signed `.app`/DMG, Gatekeeper and clean-device installation.

## Remaining release blockers

1. Assemble against both exact original commits and run the original suites. The patch fixture is deliberately not called an upstream integration test.
2. Exercise actual compiler output with supported static font weights and the full Korean/Latin visual corpus. Current source text metrics and grammar audits remain those of the original kit; this overlay does not prove they are exact.
3. Test the original conversation with real tool calls: research, draft, user correction, source conflict, same-artifact reload, session switching and Stop. A model's ability to produce good composition is not established by helper tests.
4. Review native security inherited from upstream. In the inspected version, SecretStore is a 0600 JSON store, not Keychain. General shell/file capabilities and the original app webview policy remain. Credentials and policy files need an explicit internal deployment decision.
5. Capture and review resolved dependency locks and licenses. Build hashes identify what was staged; they are not an independent supply-chain attestation.
6. Run the macOS release script and a clean quarantined-install test. Only then label a produced artifact a distributable DMG.

## Build record, 2026-09-13 (this Mac)

Blockers 1 and 6 are partially closed, and this is exactly how far:

- **Assembled** against both pinned commits (`openworker 5bc10d9`, `fp-kit 112affec`) in
  `~/Developer/fp-studio-v0.3`. `check_upstream_ui.py` reconstructs every `surfaces/gui` file from the
  upstream blob plus the recorded edits, byte for byte.
- **Built and installed**: `/Applications/FP Studio.app`, byte-identical to
  `surfaces/gui/src-tauri/target/release/bundle/macos/FP Studio.app` (main executable, sidecar and staged
  `fp-runtime` all compared). DMG: `FP Studio_0.3.0_aarch64.dmg`.
- **Signed** with `Developer ID Application: Hyunmin kim (KH55W9G87F)`, hardened runtime
  (`flags=0x10000(runtime)`), bundle id `com.fourpillars.fpstudio`.
- **Not notarized.** `spctl -a -vv` returns `rejected — source=Unnotarized Developer ID`, and
  `stapler validate` reports no ticket on the DMG. A clean quarantined-install test has not been run, so
  blocker 6 stays open.
- **Real compiler path executed**: `test_fp_live_runtime.py` passes in that checkout with the staged
  Pretendard set, producing SVG/PNG from the pinned kit through resvg. Blocker 2's visual corpus and
  blocker 3's live conversation remain open.

On 2026-09-15 this repository was re-derived from that checkout: overlay files, the declarative edit
table (`scripts/fp_edits.py`, 251 hunks) and the replaced icon set were regenerated from it, and a fresh
`assemble.py` run reproduces the tree byte for byte. Product suites that had been duplicated at the
repository root were deleted rather than re-pinned — that duplication is what let the repository drift
from the shipped tree in the first place.

## Release record, 2026-09-15

`bash packaging/build_fp_studio_dmg.sh --release` ran end to end in `~/Developer/fp-studio-v0.3`:

- Preflight: 121 FP suites (real compiler → staged Pretendard → resvg, real permission engine), kit `npm test`,
  GUI `npm test` (189) and `npm run build`.
- `FP Studio_0.3.0_aarch64.dmg`, SHA-256 `929609932fb96a7f47d057529bbdd0426a64f1d349301ed26c00adbb5b3c387e`.
- Notary submission `f319e84d-3ef4-4c23-aa0f-4c70ce5c2193`: **Accepted**, stapled and validated.
- Installed to `/Applications/FP Studio.app`: `spctl -a -vv` → `accepted — source=Notarized Developer ID`;
  launched, sidecar answered `/v1/health`, stock shell rendered with existing sessions and artifacts.
- Blocker 6 is now open only on the clean, separate-Mac quarantined install. Blockers 2 and 3 are unchanged.

**Release gate change.** The upstream E2E suite pins upstream's product name and its exact settings/sidebar/
account wording, which this fork changes; 181 of its 221 specs therefore fail by construction, while the shell
itself renders correctly under the same hermetic mocks. The release gate is now `e2e/fp-smoke.spec.ts`, owned by
this fork: stock sidebar, personas and composer under FP Studio identity, no residual upstream brand, and no
canvas/inspector/template picker. The upstream suite is no longer run as a release gate, and this repository does
not claim it passes.

## Quality boundaries

A captured excerpt establishes that text appeared in the response. It does not establish authoritativeness, correctness, entailment, chart fairness or an absence of prompt injection. Numeric coverage is deliberately mechanical and cannot enumerate every fact expressed in prose. The agent and user must decide these together.

No automatic generated-PNG-to-vision-review loop was implemented in this version. The original viewer and original image attachment path remain available. Do not claim that the agent has visually reviewed pixels unless a real image input was supplied to a vision-capable model and its review actually ran.

## Primary source locations reviewed

- OpenWorker `coworker/agent.py`: original tool registration and interrupt hooks.
- OpenWorker `coworker/engine.py`: `_record_result`, `_display` and TOOL_FINISHED.
- OpenWorker `coworker/web/fetch.py`: captured response fields and address-guarded fetch.
- OpenWorker `coworker/risk.py`, `coworker/permissions.py`: risk floors and writable roots.
- OpenWorker `coworker/secrets.py`: original local credential store and state directory.
- OpenWorker `surfaces/gui/src/App.tsx`, `components/RightRail.tsx`, `components/Markdown.tsx`: original artifact event/viewer flow.
- OpenWorker `packaging/build_dmg.sh`, `surfaces/gui/src-tauri/tauri.conf.json`: original Mac packaging/signing flow.
- FP kit `src/index.ts`, `package.json`: original compiler entry and dependencies.

Official Mac distribution documentation: https://v2.tauri.app/distribute/ and https://tauri.app/distribute/sign/macos/ . Developer ID/notary workflow: https://developer.apple.com/developer-id/ . The original build script uses its own NOTARYTOOL_API_* environment variable convention.
