#!/usr/bin/env bash
set -euo pipefail

usage() {
	echo "Usage: bash scripts/dev/context-restore.sh --mode <brief|handoff|context|files|list> [--branch <name>] [--work-id <id>] [--list]"
	echo ""
	echo "Modes:"
	echo "  --mode brief    show the compact branch/work brief"
	echo "  --mode handoff  show the fuller handoff artifact"
	echo "  --mode context  compatibility alias for --mode brief"
	echo "  --mode files    show file-recovery guidance only"
	echo "  --mode list     list available branch artifacts"
}

sanitize() {
	printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9._-]+/-/g; s/^-+|-+$//g'
}

MODE=""
TARGET_BRANCH=""
WORK_ID=""
LIST_ONLY=0

while [ "$#" -gt 0 ]; do
	case "$1" in
		--mode)
			MODE="${2:-}"
			shift 2
			;;
		--branch)
			TARGET_BRANCH="${2:-}"
			shift 2
			;;
		--work-id)
			WORK_ID="${2:-}"
			shift 2
			;;
		--list)
			LIST_ONLY=1
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

if [ -z "$MODE" ]; then
	echo "[ctx:restore] ambiguous request."
	echo "[ctx:restore] choose explicit mode:"
	echo "  --mode brief"
	echo "  --mode handoff"
	echo "  --mode files"
	exit 1
fi

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

if [ -n "$WORK_ID" ]; then
	WORK_SAFE="$(sanitize "$WORK_ID")"
	if [ -f "$BASE_DIR/briefs/${WORK_SAFE}.md" ]; then
		BRIEF_FILE="$BASE_DIR/briefs/${WORK_SAFE}.md"
	fi
	if [ -f "$BASE_DIR/handoffs/${WORK_SAFE}.md" ]; then
		HANDOFF_FILE="$BASE_DIR/handoffs/${WORK_SAFE}.md"
	fi
	if [ -f "$BASE_DIR/checkpoints/${WORK_SAFE}.md" ]; then
		CHECKPOINT_FILE="$BASE_DIR/checkpoints/${WORK_SAFE}.md"
	fi
fi

if [ "$LIST_ONLY" -eq 1 ] || [ "$MODE" = "list" ]; then
	echo "[ctx:restore] branch=$TARGET_BRANCH"
	echo ""
	echo "checkpoint:"
	if [ -f "$CHECKPOINT_FILE" ]; then
		echo "- ${CHECKPOINT_FILE#$ROOT_DIR/}"
	else
		echo "- (none)"
	fi
	echo ""
	echo "brief:"
	if [ -f "$BRIEF_FILE" ]; then
		echo "- ${BRIEF_FILE#$ROOT_DIR/}"
	else
		echo "- (none)"
	fi
	echo ""
	echo "handoff:"
	if [ -f "$HANDOFF_FILE" ]; then
		echo "- ${HANDOFF_FILE#$ROOT_DIR/}"
	else
		echo "- (none)"
	fi
	exit 0
fi

if [ "$MODE" = "files" ]; then
	echo "[ctx:restore] file recovery mode selected."
	echo "This command does not modify files automatically."
	echo ""
	echo "Recommended manual flow:"
	echo "1. git status --short --branch"
	echo "2. git log --oneline --decorate -n 20"
	echo "3. git diff <target> -- <file>"
	echo "4. If needed, create a safety branch before any restore operation."
	exit 0
fi

if [ "$MODE" = "context" ]; then
	echo "[ctx:restore] mode=context is now an alias for mode=brief."
	MODE="brief"
fi

SOURCE_FILE=""
case "$MODE" in
	brief)
		SOURCE_FILE="$BRIEF_FILE"
		;;
	handoff)
		SOURCE_FILE="$HANDOFF_FILE"
		;;
	*)
		echo "[ctx:restore] invalid mode: $MODE"
		usage
		exit 1
		;;
esac

if [ ! -f "$SOURCE_FILE" ]; then
	if [ "$MODE" = "brief" ] && [ -f "$CHECKPOINT_FILE" ]; then
		echo "[ctx:restore] brief missing; regenerating from latest checkpoint/snapshot."
		if [ -n "$WORK_ID" ]; then
			bash scripts/dev/context-compact.sh --work-id "$WORK_ID" >/dev/null
		else
			bash scripts/dev/context-compact.sh >/dev/null
		fi
	else
		echo "[ctx:restore] no $MODE artifact found for branch $TARGET_BRANCH."
		echo "[ctx:restore] run: npm run ctx:save -- --title '<task>'"
		echo "[ctx:restore] and: npm run ctx:checkpoint -- --work-id '<W-ID>' --surface '<surface>' --objective '<objective>'"
		exit 1
	fi
fi

echo "[ctx:restore] mode=$MODE"
echo "[ctx:restore] source=${SOURCE_FILE#$ROOT_DIR/}"
echo ""
cat "$SOURCE_FILE"
