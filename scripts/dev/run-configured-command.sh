#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
	echo "Usage: bash scripts/dev/run-configured-command.sh <check|build|gate>"
	exit 1
fi

NAME="$1"
ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

CONFIG_CMD=""
if [ -f scripts/dev/context-config.mjs ]; then
	CONFIG_CMD="$(node scripts/dev/context-config.mjs get-string "commands.$NAME" || true)"
fi

if [ -n "$CONFIG_CMD" ]; then
	echo "[run-configured] commands.$NAME -> $CONFIG_CMD"
	sh -lc "$CONFIG_CMD"
	exit 0
fi

if [ -f package.json ]; then
	echo "[run-configured] npm run $NAME --if-present"
	npm run "$NAME" --if-present
	exit 0
fi

echo "[run-configured] no command configured for '$NAME'; skipping."
