#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

if [ -f "scripts/dev/context-auto.sh" ]; then
	CTX_AUTO_SKIP_COMPACT=1 bash scripts/dev/context-auto.sh claude-post-edit >/dev/null 2>&1 || true
fi
