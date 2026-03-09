#!/usr/bin/env bash
set -euo pipefail

usage() {
	echo "Usage: bash scripts/dev/context-auto.sh <stage>"
	echo ""
	echo "Env flags:"
	echo "  CTX_AUTO_DISABLED=1         # disable automation"
	echo "  CTX_AUTO_STRICT=1           # fail caller on save/compact error"
	echo "  CTX_AUTO_SKIP_COMPACT=1     # save only, skip brief/handoff refresh"
	echo "  CTX_AUTO_MIN_INTERVAL_SEC   # throttle per branch+stage (default: 300)"
	echo "  CTX_WORK_ID                 # optional explicit work id"
	echo "  CTX_AGENT_ID                # optional agent id"
}

sanitize() {
	printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9._-]+/-/g; s/^-+|-+$//g'
}

run_step() {
	if "$@"; then
		return 0
	fi

	echo "[ctx:auto] warning: step failed: $*" >&2
	if [ "${CTX_AUTO_STRICT:-0}" = "1" ]; then
		echo "[ctx:auto] strict mode enabled; aborting." >&2
		exit 1
	fi
	return 0
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
	usage
	exit 0
fi

STAGE="${1:-}"
if [ -z "$STAGE" ]; then
	usage
	exit 1
fi

if [ "${CTX_AUTO_DISABLED:-0}" = "1" ]; then
	echo "[ctx:auto] disabled by CTX_AUTO_DISABLED=1"
	exit 0
fi

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || echo HEAD)"
if [ "$BRANCH" = "HEAD" ]; then
	echo "[ctx:auto] detached HEAD detected; skipping."
	exit 0
fi

if [ ! -f scripts/dev/context-save.sh ] || [ ! -f scripts/dev/context-compact.sh ]; then
	echo "[ctx:auto] context-save/compact scripts missing; skipping."
	exit 0
fi

MIN_INTERVAL="${CTX_AUTO_MIN_INTERVAL_SEC:-300}"
if ! [[ "$MIN_INTERVAL" =~ ^[0-9]+$ ]]; then
	MIN_INTERVAL=300
fi

BRANCH_SAFE="$(sanitize "${BRANCH//\//-}")"
STAGE_SAFE="$(sanitize "$STAGE")"
RUNTIME_DIR="$ROOT_DIR/.agent-context/runtime"
MARKER_FILE="$RUNTIME_DIR/$BRANCH_SAFE-$STAGE_SAFE.epoch"
mkdir -p "$RUNTIME_DIR"

NOW_EPOCH="$(date '+%s')"
if [ -f "$MARKER_FILE" ]; then
	LAST_EPOCH="$(cat "$MARKER_FILE" 2>/dev/null || echo 0)"
	if [[ "$LAST_EPOCH" =~ ^[0-9]+$ ]]; then
		DELTA=$((NOW_EPOCH - LAST_EPOCH))
		if [ "$DELTA" -lt "$MIN_INTERVAL" ]; then
			echo "[ctx:auto] throttled (${DELTA}s < ${MIN_INTERVAL}s) for $BRANCH@$STAGE"
			exit 0
		fi
	fi
fi

TS_KEY="$(date '+%Y%m%d-%H%M')"
WORK_ID="${CTX_WORK_ID:-AUTO-$TS_KEY-$BRANCH_SAFE-$STAGE_SAFE}"
AGENT_ID="${CTX_AGENT_ID:-auto}"
TITLE="auto-$STAGE_SAFE"
NOTES="Auto context snapshot at stage=$STAGE on branch=$BRANCH."

echo "[ctx:auto] stage=$STAGE branch=$BRANCH"
run_step bash scripts/dev/context-save.sh \
	--title "$TITLE" \
	--work-id "$WORK_ID" \
	--agent "$AGENT_ID" \
	--notes "$NOTES"
if [ "${CTX_AUTO_SKIP_COMPACT:-0}" = "1" ]; then
	echo "[ctx:auto] compact refresh skipped by CTX_AUTO_SKIP_COMPACT=1"
else
	run_step bash scripts/dev/context-compact.sh --work-id "$WORK_ID"
fi

echo "$NOW_EPOCH" > "$MARKER_FILE"
echo "[ctx:auto] done"
