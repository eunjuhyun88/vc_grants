#!/usr/bin/env bash
set -euo pipefail

usage() {
	echo "Usage: bash scripts/dev/check-context-quality.sh [--branch <name>] [--strict]"
	echo ""
	echo "Default checks the latest branch brief/handoff artifacts."
	echo "--strict fails when no semantic checkpoint-backed handoff exists."
}

sanitize() {
	printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9._-]+/-/g; s/^-+|-+$//g'
}

has_fixed_text() {
	local needle="$1"
	local path="$2"
	if command -v rg >/dev/null 2>&1; then
		rg -Fq "$needle" "$path"
	else
		grep -Fq -- "$needle" "$path"
	fi
}

extract_section() {
	local source="$1"
	local header="$2"
	awk -v h="## $header" '
		$0 == h {in_section=1; next}
		in_section && /^## / {exit}
		in_section {print}
	' "$source"
}

first_non_empty() {
	awk 'NF {print; exit}'
}

STRICT=0
TARGET_BRANCH=""

while [ "$#" -gt 0 ]; do
	case "$1" in
		--branch)
			TARGET_BRANCH="${2:-}"
			shift 2
			;;
		--strict)
			STRICT=1
			shift 1
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

if [ -z "$TARGET_BRANCH" ]; then
	TARGET_BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || echo HEAD)"
fi

BRANCH_SAFE="$(sanitize "${TARGET_BRANCH//\//-}")"
BASE_DIR="$ROOT_DIR/.agent-context"
BRIEF_FILE="$BASE_DIR/briefs/${BRANCH_SAFE}-latest.md"
HANDOFF_FILE="$BASE_DIR/handoffs/${BRANCH_SAFE}-latest.md"
CHECKPOINT_FILE="$BASE_DIR/checkpoints/${BRANCH_SAFE}-latest.md"

FAIL=0

pass() {
	echo "[ctx:check] ok: $1"
}

fail() {
	echo "[ctx:check] fail: $1"
	FAIL=1
}

if [ -f "$BRIEF_FILE" ]; then
	pass "brief exists: ${BRIEF_FILE#$ROOT_DIR/}"
else
	fail "brief missing: ${BRIEF_FILE#$ROOT_DIR/}"
fi

if [ -f "$HANDOFF_FILE" ]; then
	pass "handoff exists: ${HANDOFF_FILE#$ROOT_DIR/}"
else
	fail "handoff missing: ${HANDOFF_FILE#$ROOT_DIR/}"
fi

if [ -f "$CHECKPOINT_FILE" ]; then
	pass "checkpoint exists: ${CHECKPOINT_FILE#$ROOT_DIR/}"
else
	if [ "$STRICT" -eq 1 ]; then
		fail "checkpoint missing for strict mode: ${CHECKPOINT_FILE#$ROOT_DIR/}"
	fi
fi

if [ -f "$BRIEF_FILE" ]; then
	OBJECTIVE="$(extract_section "$BRIEF_FILE" "Current Objective" | first_non_empty || true)"
	NEXT_STEP="$(extract_section "$BRIEF_FILE" "Immediate Next Step" | first_non_empty || true)"
	READ_FIRST="$(extract_section "$BRIEF_FILE" "Read These First" | first_non_empty || true)"
	OPEN_QUESTIONS="$(extract_section "$BRIEF_FILE" "Open Questions" | first_non_empty || true)"

	if [ -n "$OBJECTIVE" ] && ! printf '%s' "$OBJECTIVE" | grep -Eiq '^(auto-(safe-status|safe-sync-start|safe-sync-end|pre-push|post-merge)|unknown|- none)$'; then
		pass "brief objective is semantic"
	else
		fail "brief objective is missing or stage-like"
	fi

	if [ -n "$NEXT_STEP" ] && ! printf '%s' "$NEXT_STEP" | grep -Eiq '^(- none|unknown)$'; then
		pass "brief next step is present"
	else
		fail "brief next step missing"
	fi

	if [ -n "$READ_FIRST" ] && ! printf '%s' "$READ_FIRST" | grep -Eiq '^(- none|unknown)$'; then
		pass "brief read-first docs are present"
	else
		fail "brief read-first docs missing"
	fi

	if [ -n "$OPEN_QUESTIONS" ]; then
		pass "brief open questions section populated"
	else
		fail "brief open questions missing"
	fi

	if has_fixed_text "Watch Log Tail" "$BRIEF_FILE"; then
		fail "brief contains watch log tail"
	else
		pass "brief excludes watch log tail"
	fi

	if [ "$STRICT" -eq 1 ] && has_fixed_text "no semantic checkpoint" "$BRIEF_FILE"; then
		fail "brief is degraded fallback without semantic checkpoint"
	fi
fi

if [ "$FAIL" -ne 0 ]; then
	echo "[ctx:check] context quality failed."
	exit 1
fi

echo "[ctx:check] context quality passed."
