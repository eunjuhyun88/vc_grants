#!/usr/bin/env bash
set -euo pipefail

usage() {
	echo "Usage: bash scripts/dev/context-compact.sh [--source <snapshot.md>] [--checkpoint <checkpoint.md>] [--work-id <id>] [--max-lines <n>]"
	echo ""
	echo "Generates branch-local brief and handoff artifacts from the latest snapshot and semantic checkpoint."
}

sanitize() {
	printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9._-]+/-/g; s/^-+|-+$//g'
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

trim_non_empty() {
	local limit="$1"
	awk 'NF {print}' | head -n "$limit"
}

meta_value() {
	local source="$1"
	local key="$2"
	awk -F': ' -v prefix="- $key" '$1 == prefix {print $2; exit}' "$source"
}

json_escape() {
	CTX_JSON_VALUE="$1" node -e 'const value = process.env.CTX_JSON_VALUE ?? ""; process.stdout.write(JSON.stringify(value).slice(1, -1));'
}

SOURCE_FILE=""
CHECKPOINT_FILE=""
WORK_ID=""
MAX_LINES=160

while [ "$#" -gt 0 ]; do
	case "$1" in
		--source)
			SOURCE_FILE="${2:-}"
			shift 2
			;;
		--checkpoint)
			CHECKPOINT_FILE="${2:-}"
			shift 2
			;;
		--work-id)
			WORK_ID="${2:-}"
			shift 2
			;;
		--max-lines)
			MAX_LINES="${2:-160}"
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

BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || echo HEAD)"
BRANCH_SAFE="$(sanitize "${BRANCH//\//-}")"
if git rev-parse --verify HEAD >/dev/null 2>&1; then
	HEAD_SHA="$(git rev-parse --short HEAD)"
else
	HEAD_SHA="no-commit"
fi
BASE_DIR="$ROOT_DIR/.agent-context"
SNAPSHOT_DIR="$BASE_DIR/snapshots/$BRANCH_SAFE"
CHECKPOINT_DIR="$BASE_DIR/checkpoints"
BRIEF_DIR="$BASE_DIR/briefs"
HANDOFF_DIR="$BASE_DIR/handoffs"
COMPACT_DIR="$BASE_DIR/compact"
RUNTIME_DIR="$BASE_DIR/runtime"
STATE_DIR="$BASE_DIR/state"
PINNED_FILE="$BASE_DIR/pinned-facts.md"
CATALOG_FILE="$BASE_DIR/catalog.tsv"

mkdir -p "$BRIEF_DIR" "$HANDOFF_DIR" "$COMPACT_DIR" "$RUNTIME_DIR" "$STATE_DIR"

if [ -z "$SOURCE_FILE" ]; then
	SOURCE_FILE="$(ls -1t "$SNAPSHOT_DIR"/*.md 2>/dev/null | head -n 1 || true)"
fi

if [ -z "$SOURCE_FILE" ] || [ ! -f "$SOURCE_FILE" ]; then
	echo "[ctx:compact] no snapshot found."
	echo "[ctx:compact] run: npm run ctx:save -- --title '<task>'"
	exit 1
fi

if [ -z "$CHECKPOINT_FILE" ] && [ -n "$WORK_ID" ]; then
	WORK_SAFE="$(sanitize "$WORK_ID")"
	CANDIDATE="$CHECKPOINT_DIR/${WORK_SAFE}.md"
	if [ -f "$CANDIDATE" ]; then
		CHECKPOINT_FILE="$CANDIDATE"
	fi
fi

if [ -z "$CHECKPOINT_FILE" ] || [ ! -f "$CHECKPOINT_FILE" ]; then
	BRANCH_CHECKPOINT="$CHECKPOINT_DIR/${BRANCH_SAFE}-latest.md"
	if [ -f "$BRANCH_CHECKPOINT" ]; then
		CHECKPOINT_FILE="$BRANCH_CHECKPOINT"
	fi
fi

HAS_CHECKPOINT=0
if [ -n "$CHECKPOINT_FILE" ] && [ -f "$CHECKPOINT_FILE" ]; then
	HAS_CHECKPOINT=1
fi

TS_HUMAN="$(date '+%Y-%m-%d %H:%M:%S %z')"
SNAPSHOT_OBJECTIVE="$(extract_section "$SOURCE_FILE" "Objective" | trim_non_empty 6)"
REPO_STATE="$(extract_section "$SOURCE_FILE" "Repo State" | trim_non_empty 12)"
UNCOMMITTED="$(extract_section "$SOURCE_FILE" "Uncommitted Files" | trim_non_empty 30)"
MAIN_BRANCH="${CTX_MAIN_BRANCH:-$(node scripts/dev/context-config.mjs get-string git.mainBranch 2>/dev/null || true)}"
MAIN_BRANCH="${MAIN_BRANCH:-main}"
CHANGED_FILES="$(extract_section "$SOURCE_FILE" "Changed Files vs origin/$MAIN_BRANCH" | trim_non_empty 30)"
RECENT_COMMITS="$(extract_section "$SOURCE_FILE" "Recent Commits" | trim_non_empty 10)"
RUNTIME_FLAGS="$(extract_section "$SOURCE_FILE" "Runtime Context Flags" | trim_non_empty 10)"
NOTES="$(extract_section "$SOURCE_FILE" "Notes" | trim_non_empty 12)"
RESUME_COMMANDS="$(extract_section "$SOURCE_FILE" "Resume Commands" | trim_non_empty 10)"

WORK_ID_EFFECTIVE="${WORK_ID:-}"
SURFACE="unknown"
STATUS="unknown"
CURRENT_OBJECTIVE="$SNAPSHOT_OBJECTIVE"
WHY_NOW="- none"
SCOPE="- none"
OWNED_FILES="- none"
CANONICAL_DOCS="- none"
DECISIONS="- none"
REJECTED="- none"
OPEN_QUESTIONS="- none"
NEXT_ACTIONS="- none"
EXIT_CRITERIA="- none"
WARNINGS=()

if [ "$HAS_CHECKPOINT" -eq 1 ]; then
	WORK_ID_EFFECTIVE="$(meta_value "$CHECKPOINT_FILE" "Work ID")"
	SURFACE="$(meta_value "$CHECKPOINT_FILE" "Surface")"
	STATUS="$(meta_value "$CHECKPOINT_FILE" "Status")"
	CURRENT_OBJECTIVE="$(extract_section "$CHECKPOINT_FILE" "Objective" | trim_non_empty 6)"
	WHY_NOW="$(extract_section "$CHECKPOINT_FILE" "Why Now" | trim_non_empty 10)"
	SCOPE="$(extract_section "$CHECKPOINT_FILE" "Scope" | trim_non_empty 12)"
	OWNED_FILES="$(extract_section "$CHECKPOINT_FILE" "Owned Files" | trim_non_empty 20)"
	CANONICAL_DOCS="$(extract_section "$CHECKPOINT_FILE" "Canonical Docs Opened" | trim_non_empty 12)"
	DECISIONS="$(extract_section "$CHECKPOINT_FILE" "Decisions Made" | trim_non_empty 12)"
	REJECTED="$(extract_section "$CHECKPOINT_FILE" "Rejected Alternatives" | trim_non_empty 10)"
	OPEN_QUESTIONS="$(extract_section "$CHECKPOINT_FILE" "Open Questions" | trim_non_empty 12)"
	NEXT_ACTIONS="$(extract_section "$CHECKPOINT_FILE" "Next Actions" | trim_non_empty 10)"
	EXIT_CRITERIA="$(extract_section "$CHECKPOINT_FILE" "Exit Criteria" | trim_non_empty 10)"
else
	WARNINGS+=("no semantic checkpoint recorded for this branch")
fi

if [ -z "$WORK_ID_EFFECTIVE" ]; then
	WORK_ID_EFFECTIVE="AUTO-$BRANCH_SAFE"
fi

WORK_SAFE="$(sanitize "$WORK_ID_EFFECTIVE")"
BRIEF_WORK_FILE="$BRIEF_DIR/${WORK_SAFE}.md"
BRIEF_BRANCH_FILE="$BRIEF_DIR/${BRANCH_SAFE}-latest.md"
HANDOFF_WORK_FILE="$HANDOFF_DIR/${WORK_SAFE}.md"
HANDOFF_BRANCH_FILE="$HANDOFF_DIR/${BRANCH_SAFE}-latest.md"
STATE_FILE="$STATE_DIR/${WORK_SAFE}.json"
COMPAT_FILE="$COMPACT_DIR/$BRANCH_SAFE-latest.md"

if [ -z "$CURRENT_OBJECTIVE" ] || printf '%s' "$CURRENT_OBJECTIVE" | grep -Eiq '^(auto-(safe-status|safe-sync-start|safe-sync-end|pre-push|post-merge)|unknown)$'; then
	WARNINGS+=("objective is still stage-like; checkpoint objective should replace automation stage names")
fi

if [ -z "$NEXT_ACTIONS" ] || [ "$NEXT_ACTIONS" = "- none" ]; then
	WARNINGS+=("next actions missing from semantic checkpoint")
fi

if [ -z "$OPEN_QUESTIONS" ] || [ "$OPEN_QUESTIONS" = "- none" ]; then
	WARNINGS+=("open questions missing from semantic checkpoint")
fi

PINNED_FACTS="- none"
if [ -f "$PINNED_FILE" ]; then
	PINNED_FACTS="$(sed -n '1,120p' "$PINNED_FILE" | trim_non_empty 40)"
	[ -n "$PINNED_FACTS" ] || PINNED_FACTS="- none"
fi

VALIDATION_SNAPSHOT=$(
	cat <<EOF
- docs:check: unknown
- check: unknown
- build: unknown
- head: $HEAD_SHA
- uncommitted_state: $( [ "$UNCOMMITTED" = "- clean" ] && echo clean || echo dirty )
EOF
)

READ_THESE_FIRST="$CANONICAL_DOCS"
if [ "$READ_THESE_FIRST" = "- none" ]; then
	READ_THESE_FIRST=$(
		cat <<EOF
- README.md
- docs/README.md
- ARCHITECTURE.md
- docs/AGENT_CONTEXT_PROTOCOL.md
EOF
	)
fi

HANDOFF_CHANGED_FILES="$CHANGED_FILES"
BRANCH_DIFF_CONTEXT="- none"
if [ "$HAS_CHECKPOINT" -eq 1 ] && [ "$OWNED_FILES" != "- none" ]; then
	HANDOFF_CHANGED_FILES="$OWNED_FILES"
	if [ -n "$CHANGED_FILES" ] && [ "$CHANGED_FILES" != "- none" ]; then
		BRANCH_DIFF_CONTEXT="$CHANGED_FILES"
	fi
fi

WARNING_BLOCK="- none"
if [ "${#WARNINGS[@]}" -gt 0 ]; then
	WARNING_BLOCK=""
	for warning in "${WARNINGS[@]}"; do
		WARNING_BLOCK+="- $warning"$'\n'
	done
	WARNING_BLOCK="$(printf '%s' "$WARNING_BLOCK" | trim_non_empty 20)"
fi

{
	echo "# Work Brief"
	echo ""
	echo "- Generated: $TS_HUMAN"
	echo "- Branch: $BRANCH"
	echo "- Head: $HEAD_SHA"
	echo "- Work ID: $WORK_ID_EFFECTIVE"
	echo "- Surface: $SURFACE"
	echo "- Status: $STATUS"
	echo "- Source snapshot: ${SOURCE_FILE#$ROOT_DIR/}"
	if [ "$HAS_CHECKPOINT" -eq 1 ]; then
		echo "- Source checkpoint: ${CHECKPOINT_FILE#$ROOT_DIR/}"
	else
		echo "- Source checkpoint: none"
	fi
	echo ""
	echo "## Current Objective"
	echo "${CURRENT_OBJECTIVE:-- none}"
	echo ""
	echo "## Why Now"
	echo "${WHY_NOW:-- none}"
	echo ""
	echo "## Repo State"
	echo "${REPO_STATE:-- none}"
	echo ""
	echo "## Owned Files"
	echo "${OWNED_FILES:-- none}"
	echo ""
	echo "## Locked Decisions"
	echo "${DECISIONS:-- none}"
	echo ""
	echo "## Open Questions"
	echo "${OPEN_QUESTIONS:-- none}"
	echo ""
	echo "## Immediate Next Step"
	echo "${NEXT_ACTIONS:-- none}"
	echo ""
	echo "## Exit Criteria"
	echo "${EXIT_CRITERIA:-- none}"
	echo ""
	echo "## Validation Snapshot"
	echo "$VALIDATION_SNAPSHOT"
	echo ""
	echo "## Read These First"
	echo "$READ_THESE_FIRST"
	echo ""
	echo "## Risks / Warnings"
	echo "$WARNING_BLOCK"
	echo ""
	echo "## Runtime Flags"
	echo "${RUNTIME_FLAGS:-- none}"
} | awk -v limit="$MAX_LINES" '
	NR <= limit {print}
	NR == limit + 1 {print ""; print "_(truncated by ctx:compact max-lines budget)_"}
' > "$BRIEF_WORK_FILE"

{
	echo "# Work Handoff"
	echo ""
	echo "- Generated: $TS_HUMAN"
	echo "- Branch: $BRANCH"
	echo "- Head: $HEAD_SHA"
	echo "- Work ID: $WORK_ID_EFFECTIVE"
	echo "- Surface: $SURFACE"
	echo "- Status: $STATUS"
	echo ""
	echo "## What Changed"
	echo "${HANDOFF_CHANGED_FILES:-- none}"
	echo ""
	echo "## Why This Direction Was Chosen"
	echo "${WHY_NOW:-- none}"
	echo ""
	echo "## Scope"
	echo "${SCOPE:-- none}"
	echo ""
	echo "## Branch Diff Context"
	echo "${BRANCH_DIFF_CONTEXT:-- none}"
	echo ""
	echo "## Remaining Work"
	echo "${NEXT_ACTIONS:-- none}"
	echo ""
	echo "## Rejected Alternatives"
	echo "${REJECTED:-- none}"
	echo ""
	echo "## Risks / Traps"
	echo "$WARNING_BLOCK"
	echo ""
	echo "## Open Questions"
	echo "${OPEN_QUESTIONS:-- none}"
	echo ""
	echo "## Exit Criteria"
	echo "${EXIT_CRITERIA:-- none}"
	echo ""
	echo "## Validate Before Push"
	echo "$VALIDATION_SNAPSHOT"
	echo ""
	echo "## Resume Commands"
	echo "${RESUME_COMMANDS:-- none}"
	echo ""
	echo "## Pinned Facts"
	echo "$PINNED_FACTS"
	echo ""
	echo "## Recent Commits"
	echo "${RECENT_COMMITS:-- none}"
	echo ""
	echo "## Notes"
	echo "${NOTES:-- none}"
} > "$HANDOFF_WORK_FILE"

cp "$BRIEF_WORK_FILE" "$BRIEF_BRANCH_FILE"
cp "$HANDOFF_WORK_FILE" "$HANDOFF_BRANCH_FILE"
cp "$BRIEF_WORK_FILE" "$COMPAT_FILE"
cp "$BRIEF_WORK_FILE" "$BASE_DIR/latest-brief-$BRANCH_SAFE.md"
cp "$HANDOFF_WORK_FILE" "$BASE_DIR/latest-handoff-$BRANCH_SAFE.md"
cp "$COMPAT_FILE" "$BASE_DIR/latest-compact-$BRANCH_SAFE.md"

cat > "$STATE_FILE" <<EOF
{
  "workId": "$(json_escape "$WORK_ID_EFFECTIVE")",
  "branch": "$(json_escape "$BRANCH")",
  "surface": "$(json_escape "$SURFACE")",
  "status": "$(json_escape "$STATUS")",
  "objective": "$(json_escape "$CURRENT_OBJECTIVE")",
  "whyNow": "$(json_escape "$WHY_NOW")",
  "scope": "$(json_escape "$SCOPE")",
  "ownedFiles": "$(json_escape "$OWNED_FILES")",
  "canonicalDocs": "$(json_escape "$CANONICAL_DOCS")",
  "openQuestions": "$(json_escape "$OPEN_QUESTIONS")",
  "nextActions": "$(json_escape "$NEXT_ACTIONS")",
  "head": "$(json_escape "$HEAD_SHA")",
  "checkpointPresent": $HAS_CHECKPOINT,
  "validation": {
    "docsCheck": "unknown",
    "check": "unknown",
    "build": "unknown"
  },
  "briefPath": "$(json_escape "${BRIEF_WORK_FILE#$ROOT_DIR/}")",
  "handoffPath": "$(json_escape "${HANDOFF_WORK_FILE#$ROOT_DIR/}")"
}
EOF

if [ ! -f "$CATALOG_FILE" ]; then
	echo -e "timestamp\tartifact_type\tbranch\twork_id\tsurface\tstatus\tpath" > "$CATALOG_FILE"
fi

TS_KEY="$(date '+%Y%m%d-%H%M%S')"
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
	"$TS_KEY" \
	"brief" \
	"$BRANCH" \
	"$WORK_ID_EFFECTIVE" \
	"$SURFACE" \
	"$STATUS" \
	"${BRIEF_WORK_FILE#$ROOT_DIR/}" >> "$CATALOG_FILE"
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
	"$TS_KEY" \
	"handoff" \
	"$BRANCH" \
	"$WORK_ID_EFFECTIVE" \
	"$SURFACE" \
	"$STATUS" \
	"${HANDOFF_WORK_FILE#$ROOT_DIR/}" >> "$CATALOG_FILE"

printf '%s\n' "$WORK_ID_EFFECTIVE" > "$RUNTIME_DIR/${BRANCH_SAFE}.latest-work-id"

echo "[ctx:compact] source: ${SOURCE_FILE#$ROOT_DIR/}"
if [ "$HAS_CHECKPOINT" -eq 1 ]; then
	echo "[ctx:compact] checkpoint: ${CHECKPOINT_FILE#$ROOT_DIR/}"
else
	echo "[ctx:compact] checkpoint: none (degraded fallback brief/handoff)"
fi
echo "[ctx:compact] brief: ${BRIEF_BRANCH_FILE#$ROOT_DIR/}"
echo "[ctx:compact] handoff: ${HANDOFF_BRANCH_FILE#$ROOT_DIR/}"
echo "[ctx:compact] compatibility output: ${COMPAT_FILE#$ROOT_DIR/}"
