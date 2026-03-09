#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

CURRENT_BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || echo HEAD)"
MAIN_BRANCH="${CTX_MAIN_BRANCH:-$(node scripts/dev/context-config.mjs get-string git.mainBranch 2>/dev/null || true)}"
MAIN_BRANCH="${MAIN_BRANCH:-main}"
HAS_HEAD=0
if git rev-parse --verify HEAD >/dev/null 2>&1; then
	HAS_HEAD=1
fi

printf "Repo: %s\n" "$ROOT_DIR"
printf "Branch: %s\n" "$CURRENT_BRANCH"
printf "\n[git status]\n"
git status --short --branch

printf "\n[worktrees]\n"
git worktree list

printf "\n[changed files vs origin/%s]\n" "$MAIN_BRANCH"
if [ "$HAS_HEAD" -eq 0 ]; then
	echo "no commits yet"
elif git rev-parse --verify "origin/$MAIN_BRANCH" >/dev/null 2>&1; then
	if git diff --quiet "origin/$MAIN_BRANCH"...HEAD; then
		echo "none"
	else
		git diff --name-only "origin/$MAIN_BRANCH"...HEAD
	fi
else
	echo "origin/$MAIN_BRANCH not found (run: git fetch origin $MAIN_BRANCH)"
fi

printf "\n[uncommitted files]\n"
if git diff --quiet && git diff --cached --quiet; then
	echo "clean"
else
	git status --short
fi

if [ -f scripts/dev/context-auto.sh ]; then
	echo ""
	echo "[ctx:auto] safe-status trigger"
	bash scripts/dev/context-auto.sh safe-status || true
fi

if [ -f scripts/dev/list-work-claims.mjs ]; then
	echo ""
	echo "[coordination] active claims"
	node scripts/dev/list-work-claims.mjs --current-branch || true
fi
