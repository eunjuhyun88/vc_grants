#!/usr/bin/env bash
set -euo pipefail

usage() {
	echo "Usage: bash scripts/dev/context-checkpoint.sh --work-id <id> --surface <surface-id> --objective <text> [options]"
	echo ""
	echo "Required:"
	echo "  --work-id <id>"
	echo "  --surface <surface-id>"
	echo "  --objective <text>"
	echo ""
	echo "Optional repeatable fields:"
	echo "  --status <in_progress|blocked|ready_for_impl|ready_for_push>"
	echo "  --why <text>"
	echo "  --scope <text>"
	echo "  --doc <path>"
	echo "  --file <path>"
	echo "  --decision <text>"
	echo "  --rejected <text>"
	echo "  --question <text>"
	echo "  --next <text>"
	echo "  --exit <text>"
}

sanitize() {
	printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9._-]+/-/g; s/^-+|-+$//g'
}

print_list() {
	local item=""
	local wrote=0
	for item in "$@"; do
		if [ -n "$item" ]; then
			echo "- $item"
			wrote=1
		fi
	done
	if [ "$wrote" -eq 0 ]; then
		echo "- none"
	fi
}

WORK_ID=""
SURFACE=""
STATUS="in_progress"
OBJECTIVE=""
WHY_NOW=""
SCOPE=""

declare -a DOCS=()
declare -a FILES=()
declare -a DECISIONS=()
declare -a REJECTED=()
declare -a QUESTIONS=()
declare -a NEXT_ACTIONS=()
declare -a EXIT_CRITERIA=()

while [ "$#" -gt 0 ]; do
	case "$1" in
		--work-id)
			WORK_ID="${2:-}"
			shift 2
			;;
		--surface)
			SURFACE="${2:-}"
			shift 2
			;;
		--status)
			STATUS="${2:-}"
			shift 2
			;;
		--objective)
			OBJECTIVE="${2:-}"
			shift 2
			;;
		--why)
			WHY_NOW="${2:-}"
			shift 2
			;;
		--scope)
			SCOPE="${2:-}"
			shift 2
			;;
		--doc)
			DOCS+=("${2:-}")
			shift 2
			;;
		--file)
			FILES+=("${2:-}")
			shift 2
			;;
		--decision)
			DECISIONS+=("${2:-}")
			shift 2
			;;
		--rejected)
			REJECTED+=("${2:-}")
			shift 2
			;;
		--question)
			QUESTIONS+=("${2:-}")
			shift 2
			;;
		--next)
			NEXT_ACTIONS+=("${2:-}")
			shift 2
			;;
		--exit)
			EXIT_CRITERIA+=("${2:-}")
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

if [ -z "$WORK_ID" ] || [ -z "$SURFACE" ] || [ -z "$OBJECTIVE" ]; then
	echo "Missing required arguments."
	usage
	exit 1
fi

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || echo HEAD)"
if git rev-parse --verify HEAD >/dev/null 2>&1; then
	HEAD_SHA="$(git rev-parse --short HEAD)"
else
	HEAD_SHA="no-commit"
fi
TS_HUMAN="$(date '+%Y-%m-%d %H:%M:%S %z')"
TS_KEY="$(date '+%Y%m%d-%H%M%S')"
BRANCH_SAFE="$(sanitize "${BRANCH//\//-}")"
WORK_SAFE="$(sanitize "$WORK_ID")"

BASE_DIR="$ROOT_DIR/.agent-context"
CHECKPOINT_DIR="$BASE_DIR/checkpoints"
RUNTIME_DIR="$BASE_DIR/runtime"
CATALOG_FILE="$BASE_DIR/catalog.tsv"
CHECKPOINT_FILE="$CHECKPOINT_DIR/${WORK_SAFE}.md"
BRANCH_LATEST_FILE="$CHECKPOINT_DIR/${BRANCH_SAFE}-latest.md"
WORK_POINTER_FILE="$RUNTIME_DIR/${BRANCH_SAFE}.work-id"

mkdir -p "$CHECKPOINT_DIR" "$RUNTIME_DIR"

{
	echo "# Checkpoint"
	echo ""
	echo "- Work ID: $WORK_ID"
	echo "- Branch: $BRANCH"
	echo "- Head: $HEAD_SHA"
	echo "- Surface: $SURFACE"
	echo "- Status: $STATUS"
	echo "- Updated At: $TS_HUMAN"
	echo ""
	echo "## Objective"
	echo "$OBJECTIVE"
	echo ""
	echo "## Why Now"
	if [ -n "$WHY_NOW" ]; then
		echo "$WHY_NOW"
	else
		echo "- none"
	fi
	echo ""
	echo "## Scope"
	if [ -n "$SCOPE" ]; then
		echo "$SCOPE"
	else
		echo "- none"
	fi
	echo ""
	echo "## Owned Files"
	print_list "${FILES[@]-}"
	echo ""
	echo "## Canonical Docs Opened"
	print_list "${DOCS[@]-}"
	echo ""
	echo "## Decisions Made"
	print_list "${DECISIONS[@]-}"
	echo ""
	echo "## Rejected Alternatives"
	print_list "${REJECTED[@]-}"
	echo ""
	echo "## Open Questions"
	print_list "${QUESTIONS[@]-}"
	echo ""
	echo "## Next Actions"
	print_list "${NEXT_ACTIONS[@]-}"
	echo ""
	echo "## Exit Criteria"
	print_list "${EXIT_CRITERIA[@]-}"
} > "$CHECKPOINT_FILE"

cp "$CHECKPOINT_FILE" "$BRANCH_LATEST_FILE"
printf '%s\n' "$WORK_ID" > "$WORK_POINTER_FILE"

if [ ! -f "$CATALOG_FILE" ]; then
	echo -e "timestamp\tartifact_type\tbranch\twork_id\tsurface\tstatus\tpath" > "$CATALOG_FILE"
fi

printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
	"$TS_KEY" \
	"checkpoint" \
	"$BRANCH" \
	"$WORK_ID" \
	"$SURFACE" \
	"$STATUS" \
	"${CHECKPOINT_FILE#$ROOT_DIR/}" >> "$CATALOG_FILE"

echo "[ctx:checkpoint] saved: ${CHECKPOINT_FILE#$ROOT_DIR/}"
echo "[ctx:checkpoint] branch latest: ${BRANCH_LATEST_FILE#$ROOT_DIR/}"
