#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

RUN_ID="$(date +%Y%m%d-%H%M%S)-harness"

SMOKE_ARGS=(--run-id "$RUN_ID")
BROWSER_ARGS=(--run-id "$RUN_ID")

while [ "$#" -gt 0 ]; do
	SMOKE_ARGS+=("$1")
	BROWSER_ARGS+=("$1")
	shift 1
done

bash scripts/dev/run-context-harness.sh "${SMOKE_ARGS[@]}"
bash scripts/dev/run-browser-context-harness.sh "${BROWSER_ARGS[@]}"

echo "[harness:all] completed run: $RUN_ID"
