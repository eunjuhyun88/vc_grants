#!/usr/bin/env bash
set -euo pipefail

RUN_GATE=0
if [ "${1:-}" = "--gate" ]; then
	RUN_GATE=1
elif [ "${1:-}" = "" ]; then
	:
else
	echo "Usage: bash scripts/dev/sync-branch.sh [--gate]"
	exit 1
fi

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

MAIN_BRANCH="${CTX_MAIN_BRANCH:-$(node scripts/dev/context-config.mjs get-string git.mainBranch 2>/dev/null || true)}"
MAIN_BRANCH="${MAIN_BRANCH:-main}"

if ! git diff --quiet || ! git diff --cached --quiet; then
	echo "Working tree has uncommitted changes. Commit or stash first."
	git status --short --branch
	exit 1
fi

CURRENT_BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || echo HEAD)"

if [ -f scripts/dev/context-auto.sh ]; then
	echo "[safe-sync] context auto snapshot (before sync)"
	bash scripts/dev/context-auto.sh safe-sync-start || true
fi

echo "[safe-sync] fetching origin"
git fetch origin --prune

if ! git rev-parse --verify "origin/$MAIN_BRANCH" >/dev/null 2>&1; then
	echo "[safe-sync] origin/$MAIN_BRANCH not found. Check remote configuration."
	exit 1
fi

if [ "$CURRENT_BRANCH" = "$MAIN_BRANCH" ]; then
	echo "[safe-sync] $MAIN_BRANCH branch: pull --ff-only"
	git pull --ff-only origin "$MAIN_BRANCH"
else
	if git merge-base --is-ancestor "origin/$MAIN_BRANCH" HEAD; then
		echo "[safe-sync] $CURRENT_BRANCH already includes origin/$MAIN_BRANCH"
	else
		echo "[safe-sync] rebasing $CURRENT_BRANCH onto origin/$MAIN_BRANCH"
		git rebase "origin/$MAIN_BRANCH"
	fi
fi

if [ "$RUN_GATE" -eq 1 ]; then
	echo "[safe-sync] running npm run gate:context"
	npm run gate:context
	if [ -x scripts/dev/run-configured-command.sh ]; then
		bash scripts/dev/run-configured-command.sh gate
		bash scripts/dev/run-configured-command.sh check
		bash scripts/dev/run-configured-command.sh build
	fi
else
	echo "[safe-sync] running configured project check"
	if [ -x scripts/dev/run-configured-command.sh ]; then
		bash scripts/dev/run-configured-command.sh check
	fi
fi

if [ -f scripts/dev/context-auto.sh ]; then
	echo "[safe-sync] context auto snapshot (after sync)"
	bash scripts/dev/context-auto.sh safe-sync-end || true
fi

echo "[safe-sync] done"
