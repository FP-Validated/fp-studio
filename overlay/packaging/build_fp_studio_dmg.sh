#!/usr/bin/env bash
# Package the STOCK OpenWorker application plus FP capability; no replacement desktop UI.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
GUI="$ROOT/surfaces/gui"
RT="$ROOT/fp_runtime"
KIT="$ROOT/vendor/fp-kit"
STAGE="$GUI/src-tauri/binaries/fp-runtime"
MODE="${1:---release}"
[ "$(uname -s)" = "Darwin" ] || { echo 'ERROR: Build this DMG on macOS.' >&2; exit 1; }
case "$MODE" in --release|--development) ;; *) echo 'Use --release or --development' >&2; exit 1;; esac
: "${FP_NODE_BINARY:?Set FP_NODE_BINARY to a self-contained official Node executable for this Mac architecture}"
: "${FP_FONT_DIR:?Set FP_FONT_DIR to your Pretendard TTF/OTF directory}"
[ -x "$FP_NODE_BINARY" ] && [ -d "$FP_FONT_DIR" ] || { echo 'Invalid Node/font path' >&2; exit 1; }
[ -x "$ROOT/.venv/bin/python" ] || { echo 'Run OpenWorker setup_dev_env.sh first' >&2; exit 1; }
[ -f "$RT/node_modules/@resvg/resvg-wasm/index_bg.wasm" ] || { echo 'Install fp_runtime dependencies first' >&2; exit 1; }
[ -d "$KIT/node_modules" ] || { echo 'Install fp-kit dependencies first' >&2; exit 1; }
[ -f "$KIT/dist/src/index.js" ] || { echo 'Build fp-kit first' >&2; exit 1; }
lipo -verify_arch "$(uname -m)" "$FP_NODE_BINARY"
# A Homebrew node can depend on dylibs absent from a colleague's Mac.
otool -L "$FP_NODE_BINARY" | tail -n +2 | awk '{print $1}' | while read -r lib; do
  case "$lib" in /usr/lib/*|/System/Library/*) ;; *) echo "Non-portable Node dylib: $lib" >&2; exit 1;; esac
done
if [ "$MODE" = '--release' ]; then
  : "${APPLE_SIGNING_IDENTITY:?Developer ID Application identity required for release}"
  [ "${OCW_SKIP_NOTARIZE:-0}" != '1' ] || { echo 'Release cannot skip notarization' >&2; exit 1; }
fi

# Compare against the pinned UPSTREAM commit, including changes already committed downstream.
"$ROOT/.venv/bin/python" "$ROOT/fp-studio/scripts/check_upstream_ui.py" "$ROOT"

# New staging directory only; never follow or remove a user's convenience symlink.
[ ! -L "$STAGE" ] || { echo 'Refusing symlinked runtime stage' >&2; exit 1; }
mkdir -p "$(dirname "$STAGE")"
TMP="$(mktemp -d "$(dirname "$STAGE")/.fp-runtime.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/node/bin" "$TMP/fonts" "$TMP/fp-kit/src" "$TMP/fp-kit/docs"
cp "$RT/worker.mjs" "$RT/package.json" "$TMP/"
cp -RL "$RT/lib" "$RT/node_modules" "$TMP/"
cp "$FP_NODE_BINARY" "$TMP/node/bin/node"
chmod +x "$TMP/node/bin/node"
# The kit's entry imports other modules (and their dependencies). Omitting node_modules
# yields a DMG that works in a dev checkout but fails on a clean Mac.
for dir in dist themes templates schemas node_modules; do cp -RL "$KIT/$dir" "$TMP/fp-kit/$dir"; done
cp "$KIT/src/types.ts" "$TMP/fp-kit/src/types.ts"
cp "$KIT/docs/DESIGN-LANGUAGE.md" "$TMP/fp-kit/docs/DESIGN-LANGUAGE.md"
cp "$KIT/package.json" "$KIT/LICENSE" "$TMP/fp-kit/"
[ ! -f "$KIT/THIRD_PARTY_NOTICES.md" ] || cp "$KIT/THIRD_PARTY_NOTICES.md" "$TMP/fp-kit/"
find "$FP_FONT_DIR" -maxdepth 1 -type f \( -iname '*.ttf' -o -iname '*.otf' \) -exec cp {} "$TMP/fonts/" \;
[ -n "$(find "$TMP/fonts" -type f -print -quit)" ] || { echo 'No fonts copied' >&2; exit 1; }
# Supply NOTICE/license material alongside production font assets in your internal build.
find "$FP_FONT_DIR" -maxdepth 1 -type f \( -iname '*license*' -o -iname '*notice*' -o -iname 'OFL*' \) -exec cp {} "$TMP/fonts/" \;

# The FOUR PILLARS design rules ship INSIDE the bundle: fp_render enforces them at
# runtime, so a DMG without them cannot render at all. Fail closed here rather than
# shipping an app that refuses every render on a clean Mac.
mkdir -p "$TMP/design-skills"
cp -R "$ROOT/coworker/fp/design_skills/." "$TMP/design-skills/"
FP_STUDIO_DESIGN_SKILLS="$TMP/design-skills" "$ROOT/.venv/bin/python" -c '
import sys
sys.path.insert(0, "'"$ROOT"'")
from coworker.fp import design
gaps = design.missing()
if gaps:
    raise SystemExit("Design rules missing from the bundle: " + ", ".join(gaps))
print("design rules staged: " + ", ".join(f"{n}@{design.digest(n)[:12]}" for n in design.SKILLS))
'

# Fail closed on REAL renderer integration. There is no skip-if-unavailable path.
export FP_STUDIO_RUNTIME_DIR="$TMP"
unset FP_STUDIO_RENDER_CMD FP_STUDIO_TESTING NODE_OPTIONS NODE_PATH
(cd "$ROOT" && .venv/bin/python -m pytest -q tests/test_fp_core_v03.py tests/test_fp_process_v03.py tests/test_fp_migration_v03.py tests/test_fp_live_runtime.py tests/test_fp_permission_integration.py tests/test_fp_design_rules.py tests/test_fp_sdk_routing.py tests/test_fp_token_economy.py)
(cd "$KIT" && npm test)
(cd "$GUI" && npm test && npm run build)
# The upstream E2E suite pins upstream's product name and its exact settings/sidebar/
# account wording; this fork changes both, so 181 of its 221 specs fail by construction
# rather than on a regression. The gate that still means something is the fork's own
# shell smoke test against the same hermetic mocks: stock sidebar, personas and composer
# under FP Studio identity, and no second application.
if [ "$MODE" = '--release' ]; then (cd "$GUI" && npm run e2e -- e2e/fp-smoke.spec.ts); fi

# Original build_dmg.sh imports the build identity before signing nested executables.
# Our additive hook there signs Node, then hashes the final staged bytes before Tauri.
# Only remove the known generated resource slot after all preflight tests pass.
[ ! -e "$STAGE" ] || rm -rf "$STAGE"
mv "$TMP" "$STAGE"
trap - EXIT
export FP_STUDIO_RUNTIME_DIR="$STAGE"
# Cargo's release default is `strip = "debuginfo"`, and it applies to HOST units too.
# With the current stable toolchain that strip removes the Rust metadata section from
# proc-macro dylibs on macOS, so every proc-macro dependent fails to compile with
# "can't find crate for `thiserror_impl`". Override the host/proc-macro units only; the
# shipped binary is still stripped by the release profile.
export CARGO_PROFILE_RELEASE_BUILD_OVERRIDE_STRIP=none
"$HERE/build_dmg.sh"
APP="$GUI/src-tauri/target/release/bundle/macos/FP Studio.app"
if [ "$MODE" = '--release' ]; then
  codesign --verify --deep --strict --verbose=2 "$APP"
  spctl --assess --type execute --verbose=2 "$APP"
  found=0
  for dmg in "$GUI/src-tauri/target/release/bundle/dmg/FP Studio_"*.dmg; do
    [ -f "$dmg" ] || continue
    xcrun stapler validate "$dmg"
    shasum -a 256 "$dmg" > "$dmg.sha256"
    found=1
  done
  [ "$found" = '1' ] || { echo 'No notarized DMG found' >&2; exit 1; }
else
  echo 'Development build only. Do not describe this as a signed/notarized release.'
fi
