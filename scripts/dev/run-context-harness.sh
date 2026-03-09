#!/usr/bin/env bash
set -euo pipefail

usage() {
	echo "Usage: bash scripts/dev/run-context-harness.sh [--run-id <id>] [--base-url <url>] [--log-file <path>] [--page <route>] [--api <route:statuses>]"
}

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

BASE_URL="http://localhost:4173"
LOG_FILE=""
RUN_ID=""
declare -a PAGE_TARGETS=()
declare -a API_TARGETS=()

while [ "$#" -gt 0 ]; do
	case "$1" in
		--run-id)
			RUN_ID="${2:-}"
			shift 2
			;;
		--base-url)
			BASE_URL="${2:-}"
			shift 2
			;;
		--log-file)
			LOG_FILE="${2:-}"
			shift 2
			;;
		--page)
			PAGE_TARGETS+=("${2:-}")
			shift 2
			;;
		--api)
			API_TARGETS+=("${2:-}")
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

if [ -z "$RUN_ID" ]; then
	RUN_ID="$(date +%Y%m%d-%H%M%S)-harness"
fi

if [ "${#PAGE_TARGETS[@]}" -eq 0 ]; then
	while IFS= read -r page; do
		[ -n "$page" ] && PAGE_TARGETS+=("$page")
	done < <(node - <<'NODE'
const fs = require('fs');
const config = fs.existsSync('context-kit.json') ? JSON.parse(fs.readFileSync('context-kit.json', 'utf8')) : {};
for (const page of config.harness?.pages || ['/']) {
  process.stdout.write(`${page}\n`);
}
NODE
)
fi

if [ "${#API_TARGETS[@]}" -eq 0 ]; then
	while IFS= read -r row; do
		[ -n "$row" ] && API_TARGETS+=("$row")
	done < <(node - <<'NODE'
const fs = require('fs');
const config = fs.existsSync('context-kit.json') ? JSON.parse(fs.readFileSync('context-kit.json', 'utf8')) : {};
for (const item of config.harness?.apis || []) {
  const expected = Array.isArray(item.expected) ? item.expected.join(',') : String(item.expected ?? 200);
  process.stdout.write(`${item.route}:${expected}\n`);
}
NODE
)
fi

BASE_URL="${BASE_URL%/}"
ARTIFACT_DIR=".agent-context/harness/$RUN_ID"
RESPONSES_DIR="$ARTIFACT_DIR/responses"
mkdir -p "$RESPONSES_DIR"

PAGES_TSV="$ARTIFACT_DIR/pages.tsv"
APIS_TSV="$ARTIFACT_DIR/apis.tsv"
SUMMARY_MD="$ARTIFACT_DIR/summary.md"
LOG_TAIL="$ARTIFACT_DIR/logs-tail.txt"

printf 'route\tstatus\tcontent_type\tlatency_ms\tresult\n' > "$PAGES_TSV"
printf 'route\texpected\tstatus\tcontent_type\tlatency_ms\tresult\n' > "$APIS_TSV"

FAIL=0

capture_target() {
	local kind="$1"
	local route="$2"
	local expected="$3"
	local safe_name="${kind}$(printf '%s' "$route" | sed -E 's#[^a-zA-Z0-9._-]+#_#g')"
	local headers_file="$RESPONSES_DIR/${safe_name}.headers.txt"
	local body_file="$RESPONSES_DIR/${safe_name}.body.txt"
	local output=""
	local status="000"
	local content_type=""
	local time_total="0"
	local result="fail"
	local url="$BASE_URL$route"

	set +e
	output="$(curl -sS -L -o "$body_file" -D "$headers_file" -w '%{http_code}\t%{content_type}\t%{time_total}' "$url" 2>"$RESPONSES_DIR/${safe_name}.stderr.txt")"
	local curl_status=$?
	set -e

	if [ "$curl_status" -eq 0 ]; then
		status="$(printf '%s' "$output" | awk -F'\t' '{print $1}')"
		content_type="$(printf '%s' "$output" | awk -F'\t' '{print $2}')"
		time_total="$(printf '%s' "$output" | awk -F'\t' '{print $3}')"
	fi

	local latency_ms
	latency_ms="$(awk -v t="${time_total:-0}" 'BEGIN { printf "%.0f", t * 1000 }')"

	if [ "$kind" = "page" ]; then
		if [ "$status" = "200" ] && printf '%s' "$content_type" | grep -Fqi 'text/html'; then
			result="pass"
		fi
		printf '%s\t%s\t%s\t%s\t%s\n' "$route" "$status" "$content_type" "$latency_ms" "$result" >> "$PAGES_TSV"
	else
		if printf '%s' ",$expected," | grep -Fq ",$status,"; then
			result="pass"
		fi
		printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$route" "$expected" "$status" "$content_type" "$latency_ms" "$result" >> "$APIS_TSV"
	fi

	if [ "$result" != "pass" ]; then
		FAIL=1
	fi
}

if [ "${#PAGE_TARGETS[@]}" -gt 0 ]; then
	for route in "${PAGE_TARGETS[@]}"; do
		capture_target "page" "$route" "200"
	done
fi

if [ "${#API_TARGETS[@]}" -gt 0 ]; then
	for target in "${API_TARGETS[@]}"; do
		route="${target%%:*}"
		expected="${target#*:}"
		capture_target "api" "$route" "$expected"
	done
fi

if [ -n "$LOG_FILE" ] && [ -f "$LOG_FILE" ]; then
	tail -n 200 "$LOG_FILE" > "$LOG_TAIL"
fi

PAGE_PASSES="$(awk -F'\t' 'NR > 1 && $5 == "pass" {count++} END {print count + 0}' "$PAGES_TSV")"
PAGE_TOTAL="$(awk 'END {print NR - 1}' "$PAGES_TSV")"
API_PASSES="$(awk -F'\t' 'NR > 1 && $6 == "pass" {count++} END {print count + 0}' "$APIS_TSV")"
API_TOTAL="$(awk 'END {print NR - 1}' "$APIS_TSV")"

cat > "$SUMMARY_MD" <<EOF
# Context Harness Summary

- Run: \`$RUN_ID\`
- Base URL: \`$BASE_URL\`
- Page targets passed: \`$PAGE_PASSES / $PAGE_TOTAL\`
- API targets passed: \`$API_PASSES / $API_TOTAL\`
- Log tail captured: \`$( [ -f "$LOG_TAIL" ] && printf 'yes' || printf 'no' )\`

## Artifacts

- \`$PAGES_TSV\`
- \`$APIS_TSV\`
- \`$RESPONSES_DIR/\`
$( [ -f "$LOG_TAIL" ] && printf -- "- \`%s\`\n" "$LOG_TAIL" )
EOF

echo "[harness] wrote artifacts: $ARTIFACT_DIR"

if [ "$FAIL" -ne 0 ]; then
	echo "[harness] failed."
	exit 1
fi

echo "[harness] passed."
