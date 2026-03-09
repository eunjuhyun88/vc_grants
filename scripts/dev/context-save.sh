#!/usr/bin/env bash
set -euo pipefail

usage() {
	echo "Usage: bash scripts/dev/context-save.sh [--title <text>] [--work-id <id>] [--agent <name>] [--notes <text>]"
	echo ""
	echo "Example:"
	echo "  npm run ctx:save -- --title 'intel policy handoff' --work-id 'W-20260226-2151-backend-codex' --agent 'codex'"
}

sanitize() {
	printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9._-]+/-/g; s/^-+|-+$//g'
}

TITLE="manual"
WORK_ID=""
AGENT_ID="${USER:-agent}"
NOTES=""

while [ "$#" -gt 0 ]; do
	case "$1" in
		--title)
			TITLE="${2:-}"
			shift 2
			;;
		--work-id)
			WORK_ID="${2:-}"
			shift 2
			;;
		--agent)
			AGENT_ID="${2:-}"
			shift 2
			;;
		--notes)
			NOTES="${2:-}"
			shift 2
			;;
		-h|--help)
			usage
			exit 0
			;;
		*)
			echo "Unknown option: $1"
			usage
			exit 1
			;;
	esac
done

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

MAIN_BRANCH="${CTX_MAIN_BRANCH:-$(node scripts/dev/context-config.mjs get-string git.mainBranch 2>/dev/null || true)}"
MAIN_BRANCH="${MAIN_BRANCH:-main}"

BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || echo HEAD)"
HAS_HEAD=0
if git rev-parse --verify HEAD >/dev/null 2>&1; then
	HAS_HEAD=1
	HEAD_SHA="$(git rev-parse --short HEAD)"
else
	HEAD_SHA="no-commit"
fi
TS_HUMAN="$(date '+%Y-%m-%d %H:%M:%S %z')"
TS_KEY="$(date '+%Y%m%d-%H%M%S')"

BRANCH_SAFE="$(sanitize "${BRANCH//\//-}")"
TITLE_SAFE="$(sanitize "$TITLE")"
if [ -z "$TITLE_SAFE" ]; then
	TITLE_SAFE="snapshot"
fi

BASE_DIR="$ROOT_DIR/.agent-context"
SNAPSHOT_DIR="$BASE_DIR/snapshots/$BRANCH_SAFE"
COMPACT_DIR="$BASE_DIR/compact"
INDEX_FILE="$BASE_DIR/index.tsv"
LATEST_FILE="$BASE_DIR/latest-$BRANCH_SAFE.md"
SNAPSHOT_FILE="$SNAPSHOT_DIR/${TS_KEY}-${TITLE_SAFE}.md"

mkdir -p "$SNAPSHOT_DIR" "$COMPACT_DIR"

UPSTREAM="$(git rev-parse --abbrev-ref --symbolic-full-name @{upstream} 2>/dev/null || true)"
AHEAD_BEHIND="n/a"
if [ "$HAS_HEAD" -eq 1 ] && [ -n "$UPSTREAM" ] && git rev-parse --verify "$UPSTREAM" >/dev/null 2>&1; then
	AHEAD_BEHIND="$(git rev-list --left-right --count HEAD..."$UPSTREAM" | awk '{print "ahead="$1", behind="$2}')"
fi

CHANGED_MAIN="none"
if [ "$HAS_HEAD" -eq 1 ] && git rev-parse --verify "origin/$MAIN_BRANCH" >/dev/null 2>&1; then
	CHANGED_MAIN="$(git diff --name-only "origin/$MAIN_BRANCH"...HEAD || true)"
	[ -n "$CHANGED_MAIN" ] || CHANGED_MAIN="none"
fi

UNCOMMITTED="$(git status --short || true)"
[ -n "$UNCOMMITTED" ] || UNCOMMITTED="clean"

RECENT_COMMITS="none"
if [ "$HAS_HEAD" -eq 1 ]; then
	RECENT_COMMITS="$(git log --oneline -n 8 || true)"
fi
[ -n "$RECENT_COMMITS" ] || RECENT_COMMITS="none"

WATCH_LOG="$ROOT_DIR/docs/AGENT_WATCH_LOG.md"
WATCH_LOG_PRESENT="no"
if [ -f "$WATCH_LOG" ]; then
	WATCH_LOG_PRESENT="yes"
fi

{
	echo "# Context Snapshot"
	echo ""
	echo "- Timestamp: $TS_HUMAN"
	echo "- Branch: $BRANCH"
	echo "- Head: $HEAD_SHA"
	echo "- Upstream: ${UPSTREAM:-none}"
	echo "- Ahead/Behind: $AHEAD_BEHIND"
	echo "- Agent: $AGENT_ID"
	echo "- Work ID: ${WORK_ID:-none}"
	echo "- Title: $TITLE"
	echo ""
	echo "## Objective"
	echo "$TITLE"
	echo ""
	echo "## Work Identity"
	echo "- agent: $AGENT_ID"
	echo "- work_id: ${WORK_ID:-none}"
	echo "- branch: $BRANCH"
	echo ""
	echo "## Repo State"
	echo "- root: $ROOT_DIR"
	echo "- head: $HEAD_SHA"
	echo "- upstream: ${UPSTREAM:-none}"
	echo "- ahead_behind: $AHEAD_BEHIND"
	echo ""
	echo "## Uncommitted Files"
	if [ "$UNCOMMITTED" = "clean" ]; then
		echo "- clean"
	else
		while IFS= read -r line; do
			[ -n "$line" ] && echo "- $line"
		done <<< "$UNCOMMITTED"
	fi
	echo ""
	echo "## Changed Files vs origin/$MAIN_BRANCH"
	if [ "$CHANGED_MAIN" = "none" ]; then
		echo "- none"
	else
		while IFS= read -r line; do
			[ -n "$line" ] && echo "- $line"
		done <<< "$CHANGED_MAIN"
	fi
	echo ""
	echo "## Recent Commits"
	if [ "$RECENT_COMMITS" = "none" ]; then
		echo "- none"
	else
		while IFS= read -r line; do
			[ -n "$line" ] && echo "- $line"
		done <<< "$RECENT_COMMITS"
	fi
	echo ""
	echo "## Runtime Context Flags"
	echo "- watch_log_present: $WATCH_LOG_PRESENT"
	echo "- checkpoint_latest: .agent-context/checkpoints/$BRANCH_SAFE-latest.md"
	echo "- brief_latest: .agent-context/briefs/$BRANCH_SAFE-latest.md"
	echo "- handoff_latest: .agent-context/handoffs/$BRANCH_SAFE-latest.md"
	echo ""
	echo "## Notes"
	if [ -n "$NOTES" ]; then
		echo "$NOTES"
	else
		echo "- none"
	fi
	echo ""
	echo "## Resume Commands"
	echo "- npm run safe:status"
	echo "- npm run ctx:compact"
	echo "- npm run ctx:restore -- --mode brief"
	echo "- npm run ctx:restore -- --mode handoff"
	echo "- npm run safe:sync"
} > "$SNAPSHOT_FILE"

cp "$SNAPSHOT_FILE" "$LATEST_FILE"

if [ ! -f "$INDEX_FILE" ]; then
	echo -e "timestamp\tbranch\thead\twork_id\tagent\ttitle\tpath" > "$INDEX_FILE"
fi
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
	"$TS_HUMAN" \
	"$BRANCH" \
	"$HEAD_SHA" \
	"${WORK_ID:-none}" \
	"$AGENT_ID" \
	"$TITLE" \
	"${SNAPSHOT_FILE#$ROOT_DIR/}" >> "$INDEX_FILE"

echo "[ctx:save] saved snapshot: ${SNAPSHOT_FILE#$ROOT_DIR/}"
echo "[ctx:save] updated latest pointer: ${LATEST_FILE#$ROOT_DIR/}"
