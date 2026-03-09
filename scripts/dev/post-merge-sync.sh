#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

CURRENT_BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || echo HEAD)"
echo "[post-merge] branch: $CURRENT_BRANCH"

if git rev-parse --verify ORIG_HEAD >/dev/null 2>&1; then
	if git diff --name-only ORIG_HEAD HEAD | grep -Eq "^(package\.json|package-lock\.json|npm-shrinkwrap\.json)$"; then
		echo "[post-merge] dependency manifest changed. Run npm install if needed."
	fi
fi

echo "[post-merge] running context gate"
npm run gate:context

if [ -x scripts/dev/run-configured-command.sh ]; then
	echo "[post-merge] running configured project check"
	bash scripts/dev/run-configured-command.sh check || true
fi

if [ -f scripts/dev/context-auto.sh ]; then
	echo "[post-merge] context auto snapshot"
	bash scripts/dev/context-auto.sh post-merge || true
fi

echo "[post-merge] sync check passed"
