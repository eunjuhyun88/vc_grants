#!/usr/bin/env bash
set -euo pipefail

usage() {
	echo "Usage: bash scripts/dev/run-browser-context-harness.sh [--run-id <id>] [--base-url <url>] [--browser-bin <path>] [--page <route>]"
}

find_browser_bin() {
	local explicit="${CTX_BROWSER_BIN:-}"
	if [ -n "$explicit" ] && [ -x "$explicit" ]; then
		printf '%s\n' "$explicit"
		return 0
	fi

	local candidates=(
		"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
		"/Applications/Chromium.app/Contents/MacOS/Chromium"
		"/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
		"/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
	)

	local candidate=""
	for candidate in "${candidates[@]}"; do
		if [ -x "$candidate" ]; then
			printf '%s\n' "$candidate"
			return 0
		fi
	done

	return 1
}

run_with_timeout() {
	local timeout_sec="$1"
	shift
	python3 - "$timeout_sec" "$@" <<'PY'
import subprocess
import sys

timeout = float(sys.argv[1])
cmd = sys.argv[2:]
try:
    completed = subprocess.run(cmd, timeout=timeout, check=False)
    raise SystemExit(completed.returncode)
except subprocess.TimeoutExpired:
    raise SystemExit(124)
PY
}

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

RUN_ID=""
BASE_URL="http://localhost:4173"
BROWSER_BIN=""
WINDOW_SIZE="1440,900"
VIRTUAL_TIME_BUDGET="5000"
COMMAND_TIMEOUT_SEC="15"
declare -a PAGE_TARGETS=()

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
		--browser-bin)
			BROWSER_BIN="${2:-}"
			shift 2
			;;
		--page)
			PAGE_TARGETS+=("${2:-}")
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
for (const page of config.harness?.browserPages || config.harness?.pages || ['/']) {
  process.stdout.write(`${page}\n`);
}
NODE
)
fi

if [ -z "$BROWSER_BIN" ]; then
	if ! BROWSER_BIN="$(find_browser_bin)"; then
		echo "[browser-harness] failed: could not find a supported browser binary."
		exit 1
	fi
fi

BASE_URL="${BASE_URL%/}"
ARTIFACT_DIR=".agent-context/harness/$RUN_ID"
BROWSER_DIR="$ARTIFACT_DIR/browser"
SCREENSHOTS_DIR="$BROWSER_DIR/screenshots"
DOM_DIR="$BROWSER_DIR/dom"
STDERR_DIR="$BROWSER_DIR/stderr"
META_DIR="$BROWSER_DIR/meta"
mkdir -p "$SCREENSHOTS_DIR" "$DOM_DIR" "$STDERR_DIR" "$META_DIR"

BROWSER_TSV="$ARTIFACT_DIR/browser.tsv"
SUMMARY_MD="$ARTIFACT_DIR/summary.md"
printf 'route\tstatus\tcontent_type\tdom_bytes\tscreenshot_bytes\tresult\n' > "$BROWSER_TSV"

PROFILE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/context-kit-browser-profile.XXXXXX")"
cleanup() {
	rm -rf "$PROFILE_DIR"
}
trap cleanup EXIT

FAIL=0

capture_page() {
	local route="$1"
	local safe_name="page$(printf '%s' "$route" | sed -E 's#[^a-zA-Z0-9._-]+#_#g')"
	local screenshot_file="$SCREENSHOTS_DIR/${safe_name}.png"
	local dom_file="$DOM_DIR/${safe_name}.html"
	local stderr_file="$STDERR_DIR/${safe_name}.stderr.txt"
	local headers_file="$META_DIR/${safe_name}.headers.txt"
	local dom_profile_dir="$PROFILE_DIR/${safe_name}-dom"
	local screenshot_profile_dir="$PROFILE_DIR/${safe_name}-shot"
	local status="000"
	local content_type=""
	local result="fail"
	local dom_bytes="0"
	local screenshot_bytes="0"
	local url="$BASE_URL$route"
	local curl_output=""

	mkdir -p "$dom_profile_dir" "$screenshot_profile_dir"

	set +e
	curl_output="$(curl -sS -L -o /dev/null -D "$headers_file" -w '%{http_code}\t%{content_type}' "$url" 2>"$META_DIR/${safe_name}.curl.stderr.txt")"
	local curl_status=$?
	set -e

	if [ "$curl_status" -eq 0 ]; then
		status="$(printf '%s' "$curl_output" | awk -F'\t' '{print $1}')"
		content_type="$(printf '%s' "$curl_output" | awk -F'\t' '{print $2}')"
	fi

	set +e
	run_with_timeout "$COMMAND_TIMEOUT_SEC" "$BROWSER_BIN" \
		--headless \
		--disable-gpu \
		--hide-scrollbars \
		--no-first-run \
		--no-default-browser-check \
		--disable-background-networking \
		--user-data-dir="$dom_profile_dir" \
		--window-size="$WINDOW_SIZE" \
		--virtual-time-budget="$VIRTUAL_TIME_BUDGET" \
		--dump-dom \
		"$url" > "$dom_file" 2>> "$stderr_file"
	local dom_status=$?

	run_with_timeout "$COMMAND_TIMEOUT_SEC" "$BROWSER_BIN" \
		--headless \
		--disable-gpu \
		--hide-scrollbars \
		--no-first-run \
		--no-default-browser-check \
		--disable-background-networking \
		--user-data-dir="$screenshot_profile_dir" \
		--window-size="$WINDOW_SIZE" \
		--virtual-time-budget="$VIRTUAL_TIME_BUDGET" \
		--screenshot="$screenshot_file" \
		"$url" >/dev/null 2>> "$stderr_file"
	local screenshot_status=$?
	set -e

	[ -f "$dom_file" ] && dom_bytes="$(wc -c < "$dom_file" | tr -d ' ')"
	[ -f "$screenshot_file" ] && screenshot_bytes="$(wc -c < "$screenshot_file" | tr -d ' ')"

	if [ "$status" = "200" ] && printf '%s' "$content_type" | grep -Fqi 'text/html' \
		&& [ "${dom_bytes:-0}" -gt 0 ] && [ "${screenshot_bytes:-0}" -gt 0 ]; then
		result="pass"
	fi

	printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$route" "$status" "$content_type" "$dom_bytes" "$screenshot_bytes" "$result" >> "$BROWSER_TSV"

	if [ "$result" != "pass" ]; then
		FAIL=1
	fi
}

if [ "${#PAGE_TARGETS[@]}" -gt 0 ]; then
	for route in "${PAGE_TARGETS[@]}"; do
		capture_page "$route"
	done
fi

BROWSER_PASSES="$(awk -F'\t' 'NR > 1 && $6 == "pass" {count++} END {print count + 0}' "$BROWSER_TSV")"
BROWSER_TOTAL="$(awk 'END {print NR - 1}' "$BROWSER_TSV")"

cat > "$SUMMARY_MD" <<EOF
# Context Harness Summary

- Run: \`$RUN_ID\`
- Base URL: \`$BASE_URL\`
- Browser page captures passed: \`$BROWSER_PASSES / $BROWSER_TOTAL\`
- Browser binary: \`$BROWSER_BIN\`

## Artifacts

- \`$BROWSER_TSV\`
- \`$SCREENSHOTS_DIR/\`
- \`$DOM_DIR/\`
- \`$STDERR_DIR/\`
EOF

echo "[browser-harness] wrote artifacts: $ARTIFACT_DIR"

if [ "$FAIL" -ne 0 ]; then
	echo "[browser-harness] failed."
	exit 1
fi

echo "[browser-harness] passed."
