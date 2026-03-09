#!/usr/bin/env bash
set -euo pipefail

usage() {
	echo "Usage: bash scripts/dev/context-pin.sh [--add <fact>] [--from-file <path>] [--list]"
	echo ""
	echo "Examples:"
	echo "  npm run ctx:pin -- --add 'Do not force-push main'"
	echo "  npm run ctx:pin -- --from-file ./notes/pinned.txt"
	echo "  npm run ctx:pin -- --list"
}

ADD_FACTS=()
SOURCE_FILE=""
LIST_ONLY=0

while [ "$#" -gt 0 ]; do
	case "$1" in
		--add)
			ADD_FACTS+=("${2:-}")
			shift 2
			;;
		--from-file)
			SOURCE_FILE="${2:-}"
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

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

BASE_DIR="$ROOT_DIR/.agent-context"
PINNED_FILE="$BASE_DIR/pinned-facts.md"
mkdir -p "$BASE_DIR"

if [ ! -f "$PINNED_FILE" ]; then
	{
		echo "# Pinned Facts"
		echo ""
		echo "- Keep only durable facts that must survive context reset."
		echo "- Avoid secrets or credentials."
		echo ""
	} > "$PINNED_FILE"
fi

if [ "$LIST_ONLY" -eq 1 ]; then
	cat "$PINNED_FILE"
	exit 0
fi

if [ -n "$SOURCE_FILE" ]; then
	if [ ! -f "$SOURCE_FILE" ]; then
		echo "Pinned source file not found: $SOURCE_FILE"
		exit 1
	fi
	while IFS= read -r line; do
		[ -n "$line" ] && ADD_FACTS+=("$line")
	done < "$SOURCE_FILE"
fi

if [ "${#ADD_FACTS[@]}" -eq 0 ]; then
	echo "Nothing to add."
	usage
	exit 1
fi

TS="$(date '+%Y-%m-%d %H:%M:%S %z')"
for fact in "${ADD_FACTS[@]}"; do
	[ -n "$fact" ] || continue
	echo "- [$TS] $fact" >> "$PINNED_FILE"
done

echo "[ctx:pin] updated: ${PINNED_FILE#$ROOT_DIR/}"
