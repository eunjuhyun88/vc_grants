#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
	echo "Usage: bash scripts/dev/new-worktree.sh <task-name> [base-branch]"
	echo "Example: bash scripts/dev/new-worktree.sh wallet-login-fix main"
	exit 1
fi

TASK_NAME="$1"
BASE_BRANCH="${2:-main}"
ROOT_DIR="$(git rev-parse --show-toplevel)"
REPO_NAME="$(basename "$ROOT_DIR")"
PARENT_DIR="$(dirname "$ROOT_DIR")"

SLUG="$(printf '%s' "$TASK_NAME" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g')"
if [ -z "$SLUG" ]; then
	echo "Invalid task name: $TASK_NAME"
	exit 1
fi

BRANCH_NAME="codex/$SLUG"
TARGET_DIR="$PARENT_DIR/$REPO_NAME-$SLUG"

cd "$ROOT_DIR"

if [ -e "$TARGET_DIR" ]; then
	echo "Target already exists: $TARGET_DIR"
	exit 1
fi

if ! git rev-parse --verify "$BASE_BRANCH" >/dev/null 2>&1; then
	echo "Base branch not found locally: $BASE_BRANCH"
	echo "Try: git fetch origin $BASE_BRANCH:$BASE_BRANCH"
	exit 1
fi

if git rev-parse --verify "$BRANCH_NAME" >/dev/null 2>&1; then
	echo "Using existing branch: $BRANCH_NAME"
	git worktree add "$TARGET_DIR" "$BRANCH_NAME"
else
	echo "Creating branch: $BRANCH_NAME (base: $BASE_BRANCH)"
	git worktree add -b "$BRANCH_NAME" "$TARGET_DIR" "$BASE_BRANCH"
fi

echo ""
echo "Created worktree: $TARGET_DIR"
echo "Next steps:"
echo "  cd $TARGET_DIR"
echo "  npm install"
echo "  npm run safe:status"
echo "  npm run coord:claim -- --work-id \"W-$(date +%Y%m%d-%H%M)-$SLUG-agent\" --agent \"<agent>\" --surface \"<surface>\" --summary \"$TASK_NAME\" --path \"<prefix>\""
