#!/usr/bin/env bash
# Local regression suite: assembly mechanics and the overlay's own units.
# Product behaviour (render/research/migration/SDK/design rules/providers) lives in
# overlay/tests and needs an assembled checkout - upstream package plus the pinned kit.
# Does NOT claim native app, provider or original compiler integration.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p validation/js
python -m pytest -q tests | tee validation/python-tests.txt
if [ -n "${FP_ASSEMBLED:-}" ]; then
  python -m pytest -q "$FP_ASSEMBLED"/tests/test_fp_*.py "$FP_ASSEMBLED"/tests/test_subscription_auth.py \
    "$FP_ASSEMBLED"/tests/test_gemini_subscription.py | tee validation/assembled-tests.txt
else
  printf 'overlay/tests NOT run here: set FP_ASSEMBLED=<assembled checkout> to run the product suites.\n' \
    | tee validation/assembled-tests.txt
fi
node --test overlay/fp_runtime/tests/*.test.mjs | tee validation/node-tests.txt
tsc overlay/surfaces/gui/src/fp/latestArtifact.ts --outDir validation/js --target es2022 --module commonjs --strict
node --test tests/latestArtifact.test.cjs | tee validation/preview-tests.txt
python scripts/check_overlay.py | tee validation/overlay-contract.txt
python -m compileall -q scripts overlay/coworker
node --check overlay/fp_runtime/worker.mjs
bash -n overlay/packaging/build_fp_studio_dmg.sh
printf 'Python, TypeScript, Node and shell syntax checks passed. Native integration NOT run.\n' | tee validation/syntax.txt
python scripts/source_manifest.py
