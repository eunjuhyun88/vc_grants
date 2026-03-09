#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

echo "[memento] Start order: README.md -> AGENTS.md -> docs/README.md -> ARCHITECTURE.md -> relevant canonical docs."

if [ -f "scripts/dev/context-restore.sh" ]; then
	if OUTPUT="$(bash scripts/dev/context-restore.sh --mode brief 2>/dev/null)"; then
		echo
		echo "[memento] Latest branch brief:"
		printf '%s\n' "$OUTPUT" | sed -n '1,120p'
	else
		echo "[memento] No branch brief yet. Create a semantic checkpoint before non-trivial work."
		echo "[memento] Example: npm run ctx:checkpoint -- --work-id \"W-...\" --surface \"<surface>\" --objective \"<objective>\""
	fi
fi
