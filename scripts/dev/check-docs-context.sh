#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
cd "$ROOT_DIR"

node scripts/dev/refresh-generated-context.mjs --check
node scripts/dev/refresh-context-retrieval.mjs --check
node scripts/dev/refresh-agent-catalog.mjs --check
node scripts/dev/refresh-tool-catalog.mjs --check
node scripts/dev/refresh-agent-usage-report.mjs --check
node scripts/dev/refresh-context-registry.mjs --check
node scripts/dev/refresh-context-ab-report.mjs --check
node scripts/dev/refresh-sandbox-policy-report.mjs --check
node scripts/dev/refresh-doc-governance.mjs --check
node scripts/dev/refresh-context-metrics.mjs --check
node scripts/dev/refresh-context-value-demo.mjs --check
node scripts/dev/bootstrap-claude-compat.mjs --check

FAIL=0

has_fixed_text() {
	local needle="$1"
	local path="$2"
	if command -v rg >/dev/null 2>&1; then
		rg -Fq "$needle" "$path"
	else
		grep -Fq -- "$needle" "$path"
	fi
}

ok() {
	echo "[docs:check] ok: $1"
}

fail() {
	echo "[docs:check] fail: $1"
	FAIL=1
}

require_file() {
	local path="$1"
	if [ -f "$path" ]; then
		ok "file exists: $path"
	else
		fail "missing file: $path"
	fi
}

require_dir() {
	local path="$1"
	if [ -d "$path" ]; then
		ok "dir exists: $path"
	else
		fail "missing dir: $path"
	fi
}

require_text() {
	local path="$1"
	local needle="$2"
	local label="${3:-$needle}"
	if has_fixed_text "$needle" "$path"; then
		ok "text present in $path: $label"
	else
		fail "missing text in $path: $label"
	fi
}

require_max_lines() {
	local path="$1"
	local max_lines="$2"
	local actual_lines
	actual_lines="$(wc -l < "$path" | tr -d ' ')"
	if [ "$actual_lines" -le "$max_lines" ]; then
		ok "line budget ok for $path: $actual_lines <= $max_lines"
	else
		fail "line budget exceeded for $path: $actual_lines > $max_lines"
	fi
}

require_absent() {
	local path="$1"
	local needle="$2"
	local label="${3:-$needle}"
	if has_fixed_text "$needle" "$path"; then
		fail "unexpected text in $path: $label"
	else
		ok "text absent in $path: $label"
	fi
}

REQUIRED_DIRS=(
	"docs"
	"docs/archive"
	"docs/design-docs"
	"docs/product-specs"
	"docs/exec-plans"
	"docs/exec-plans/active"
	"docs/exec-plans/completed"
	"docs/generated"
	"docs/references"
	"agents"
	"tools"
	"scripts/dev"
	".claude"
	".claude/agents"
	".claude/commands"
	".claude/hooks"
	".githooks"
	"prompts"
	"lint"
)

REQUIRED_FILES=(
	"README.md"
	"AGENTS.md"
	"CLAUDE.md"
	"ARCHITECTURE.md"
	"context-kit.json"
	"docs/README.md"
	"docs/SYSTEM_INTENT.md"
	"docs/CONTEXT_ENGINEERING.md"
	"docs/CONTEXT_EVALUATION.md"
	"docs/CLAUDE_COMPATIBILITY.md"
	"docs/CONTEXT_PLATFORM.md"
	"docs/CONTEXTUAL_RETRIEVAL.md"
	"docs/AGENT_FACTORY.md"
	"docs/TOOL_DESIGN.md"
	"docs/AGENT_OBSERVABILITY.md"
	"docs/MULTI_AGENT_COORDINATION.md"
	"docs/GIT_WORKFLOW.md"
	"docs/SANDBOX_POLICY.md"
	"docs/DESIGN.md"
	"docs/ENGINEERING.md"
	"docs/PLANS.md"
	"docs/PRODUCT_SENSE.md"
	"docs/QUALITY_SCORE.md"
	"docs/RELIABILITY.md"
	"docs/SECURITY.md"
	"docs/HARNESS.md"
	"docs/AGENT_CONTEXT_PROTOCOL.md"
	"docs/AGENT_WATCH_LOG.md"
	"docs/design-docs/index.md"
	"docs/design-docs/core-beliefs.md"
	"docs/exec-plans/index.md"
	"docs/exec-plans/active/README.md"
	"docs/exec-plans/active/context-system-rollout.md"
	"docs/exec-plans/completed/README.md"
	"docs/exec-plans/tech-debt-tracker.md"
	"docs/generated/README.md"
	"docs/generated/docs-catalog.md"
	"docs/generated/legacy-doc-audit.md"
	"docs/generated/context-contract-report.md"
	"docs/generated/context-efficiency-report.md"
	"docs/generated/contextual-retrieval.md"
	"docs/generated/agent-catalog.md"
	"docs/generated/tool-catalog.md"
	"docs/generated/agent-usage-report.md"
	"docs/generated/context-registry.md"
	"docs/generated/context-ab-report.md"
	"docs/generated/sandbox-policy-report.md"
	"docs/generated/context-value-demo.md"
	"docs/generated/project-truth-bootstrap.md"
	"docs/generated/claude-compatibility-bootstrap.md"
	"docs/generated/route-map.md"
	"docs/generated/store-authority-map.md"
	"docs/generated/api-group-map.md"
	"docs/references/index.md"
	"docs/archive/README.md"
	"agents/README.md"
	".claude/README.md"
	".claude/settings.json"
	".claude/agents/README.md"
	".claude/agents/planner.md"
	".claude/agents/implementer.md"
	".claude/agents/reviewer.md"
	".claude/commands/README.md"
	".claude/commands/resume-context.md"
	".claude/commands/checkpoint-context.md"
	".claude/commands/gc-context.md"
	".claude/hooks/README.md"
	".claude/hooks/session-start.sh"
	".claude/hooks/post-edit.sh"
	".claude/hooks/pre-compact.sh"
	".claude/hooks/stop-context.sh"
	"tools/README.md"
	"scripts/dev/context-config.mjs"
	"scripts/dev/context-save.sh"
	"scripts/dev/context-checkpoint.sh"
	"scripts/dev/context-compact.sh"
	"scripts/dev/check-context-quality.sh"
	"scripts/dev/context-restore.sh"
	"scripts/dev/context-pin.sh"
	"scripts/dev/context-auto.sh"
	"scripts/dev/bootstrap-project-truth.mjs"
	"scripts/dev/bootstrap-claude-compat.mjs"
	"scripts/dev/bootstrap-git-config.sh"
	"scripts/dev/coordination-lib.mjs"
	"scripts/dev/claim-work.mjs"
	"scripts/dev/list-work-claims.mjs"
	"scripts/dev/check-agent-coordination.mjs"
	"scripts/dev/release-work.mjs"
	"scripts/dev/check-docs-context.sh"
	"scripts/dev/refresh-generated-context.mjs"
	"scripts/dev/context-retrieval-lib.mjs"
	"scripts/dev/refresh-context-retrieval.mjs"
	"scripts/dev/query-context-retrieval.mjs"
	"scripts/dev/agent-catalog-lib.mjs"
	"scripts/dev/tool-catalog-lib.mjs"
	"scripts/dev/agent-telemetry-lib.mjs"
	"scripts/dev/refresh-agent-catalog.mjs"
	"scripts/dev/refresh-tool-catalog.mjs"
	"scripts/dev/scaffold-agent.mjs"
	"scripts/dev/scaffold-tool.mjs"
	"scripts/dev/start-agent-run.mjs"
	"scripts/dev/log-agent-event.mjs"
	"scripts/dev/finish-agent-run.mjs"
	"scripts/dev/refresh-agent-usage-report.mjs"
	"scripts/dev/refresh-doc-governance.mjs"
	"scripts/dev/refresh-context-metrics.mjs"
	"scripts/dev/context-registry-lib.mjs"
	"scripts/dev/refresh-context-registry.mjs"
	"scripts/dev/query-context-registry.mjs"
	"scripts/dev/describe-context-entry.mjs"
	"scripts/dev/serve-context-registry.mjs"
	"scripts/dev/record-context-ab-eval.mjs"
	"scripts/dev/refresh-context-ab-report.mjs"
	"scripts/dev/refresh-sandbox-policy-report.mjs"
	"scripts/dev/refresh-context-value-demo.mjs"
	"scripts/dev/run-context-harness.sh"
	"scripts/dev/run-browser-context-harness.sh"
	"scripts/dev/run-full-context-harness.sh"
	"scripts/dev/run-context-benchmark.mjs"
	"scripts/dev/run-configured-command.sh"
	"scripts/dev/inject-package-scripts.mjs"
	"scripts/dev/post-merge-sync.sh"
	".githooks/pre-push"
	".githooks/post-merge"
	"prompts/feature-loop-template.md"
	"prompts/think-tool-prompt.md"
	"prompts/gc-loop-prompt.md"
	"lint/eslint-architecture.js"
)

for dir in "${REQUIRED_DIRS[@]}"; do
	require_dir "$dir"
done

for file in "${REQUIRED_FILES[@]}"; do
	require_file "$file"
done

REGISTRY_MANIFEST_PATH="$(node scripts/dev/context-config.mjs get-string registry.manifestPath)"
if [ -z "$REGISTRY_MANIFEST_PATH" ]; then
	REGISTRY_MANIFEST_PATH="docs/generated/context-registry.json"
fi
require_file "$REGISTRY_MANIFEST_PATH"

AGENT_CATALOG_PATH="$(node scripts/dev/context-config.mjs get-string agents.catalogPath)"
if [ -z "$AGENT_CATALOG_PATH" ]; then
	AGENT_CATALOG_PATH="docs/generated/agent-catalog.json"
fi
require_file "$AGENT_CATALOG_PATH"

TOOL_CATALOG_PATH="$(node scripts/dev/context-config.mjs get-string tools.catalogPath)"
if [ -z "$TOOL_CATALOG_PATH" ]; then
	TOOL_CATALOG_PATH="docs/generated/tool-catalog.json"
fi
require_file "$TOOL_CATALOG_PATH"

AGENT_USAGE_REPORT_PATH="$(node scripts/dev/context-config.mjs get-string telemetry.reportPath)"
if [ -z "$AGENT_USAGE_REPORT_PATH" ]; then
	AGENT_USAGE_REPORT_PATH="docs/generated/agent-usage-report.json"
fi
require_file "$AGENT_USAGE_REPORT_PATH"

while IFS= read -r spec_path; do
	[ -n "$spec_path" ] || continue
	require_file "$spec_path"
	require_text "$spec_path" "## Context Contracts" "context contracts section in $spec_path"
done < <(node - <<'NODE'
const fs = require('fs');
const config = JSON.parse(fs.readFileSync('context-kit.json', 'utf8'));
for (const surface of config.surfaces || []) {
  if (surface.spec) process.stdout.write(`${surface.spec}\n`);
}
NODE
)

while IFS= read -r agent_path; do
	[ -n "$agent_path" ] || continue
	require_file "$agent_path"
done < <(node - <<'NODE'
const fs = require('fs');
const path = require('path');
const config = JSON.parse(fs.readFileSync('context-kit.json', 'utf8'));
const dir = config.agents?.dir || 'agents';
if (fs.existsSync(dir)) {
  for (const entry of fs.readdirSync(dir).sort()) {
    if (entry.endsWith('.json')) process.stdout.write(path.join(dir, entry) + '\n');
  }
}
NODE
)

while IFS= read -r tool_path; do
	[ -n "$tool_path" ] || continue
	require_file "$tool_path"
done < <(node - <<'NODE'
const fs = require('fs');
const path = require('path');
const config = JSON.parse(fs.readFileSync('context-kit.json', 'utf8'));
const dir = config.tools?.dir || 'tools';
if (fs.existsSync(dir)) {
  for (const entry of fs.readdirSync(dir).sort()) {
    if (entry.endsWith('.json')) process.stdout.write(path.join(dir, entry) + '\n');
  }
}
NODE
)

require_text "README.md" "## 1.1) Context Routing" "context routing section"
require_text "README.md" "### Context Artifact Model" "context artifact model section"
require_text "README.md" "ctx:checkpoint" "checkpoint command in readme"
require_text "AGENTS.md" "ctx:checkpoint" "checkpoint command in agents"
require_text "AGENTS.md" "docs/CONTEXT_ENGINEERING.md" "context engineering doc in agents"
require_text "AGENTS.md" "docs/AGENT_FACTORY.md" "agent factory doc in agents"
require_text "AGENTS.md" "docs/TOOL_DESIGN.md" "tool design doc in agents"
require_text "ARCHITECTURE.md" "## Canonical Doc Entry Points" "architecture entry section"
require_text "docs/README.md" "## Canonical Entry Docs" "canonical entry docs"
require_text "docs/SYSTEM_INTENT.md" "## Non-Negotiable Invariants" "system invariants"
require_text "docs/CONTEXT_ENGINEERING.md" "## Context Layers" "context layers"
require_text "docs/CONTEXT_ENGINEERING.md" "## Retrieval Order" "retrieval order"
require_text "docs/CONTEXT_ENGINEERING.md" "## Anti-Patterns" "anti-patterns"
require_text "docs/CONTEXT_ENGINEERING.md" "## Mechanical Enforcement" "mechanical enforcement"
require_text "docs/CLAUDE_COMPATIBILITY.md" "## Mapping" "Claude compatibility mapping"
require_text "docs/CLAUDE_COMPATIBILITY.md" "## Local Guidance Bootstrap" "Claude local guidance bootstrap"
require_text "docs/CONTEXT_EVALUATION.md" "## What To Measure" "context evaluation metrics"
require_text "docs/CONTEXT_EVALUATION.md" "## Final Context Acceptance" "final context acceptance"
require_text "docs/CONTEXT_PLATFORM.md" "## Registry Model" "context registry model"
require_text "docs/AGENT_FACTORY.md" "## Manifest Contract" "agent manifest contract"
require_text "docs/TOOL_DESIGN.md" "## Tool Contract Shape" "tool contract shape"
require_text "docs/AGENT_OBSERVABILITY.md" "## Core Metrics" "agent observability core metrics"
require_text "docs/CONTEXT_PLATFORM.md" "## Evaluation Model" "context platform evaluation model"
require_text "docs/CONTEXTUAL_RETRIEVAL.md" "## Retrieval Model" "contextual retrieval model"
require_text "docs/CONTEXTUAL_RETRIEVAL.md" "## Query Workflow" "contextual retrieval query workflow"
require_text "docs/GIT_WORKFLOW.md" "## Branch Rules" "git workflow branch rules"
require_text "docs/GIT_WORKFLOW.md" "## Recommended Local Git Config" "git workflow config section"
require_text "docs/SANDBOX_POLICY.md" "## Sandbox Threat Model" "sandbox threat model"
require_text "docs/SANDBOX_POLICY.md" "## Mechanical Enforcement" "sandbox mechanical enforcement"
require_text "docs/MULTI_AGENT_COORDINATION.md" "## Coordination Model" "coordination model"
require_text "docs/MULTI_AGENT_COORDINATION.md" "## Conflict Rules" "coordination conflict rules"
require_text "docs/DESIGN.md" "## Design Authority Stack" "design authority stack"
require_text "docs/ENGINEERING.md" "## State Authority" "state authority"
require_text "docs/PLANS.md" "## Current Active Planning Surface" "active planning"
require_text "docs/PRODUCT_SENSE.md" "## Core Product Heuristics" "product heuristics"
require_text "docs/QUALITY_SCORE.md" "Scale:" "quality scale"
require_text "docs/QUALITY_SCORE.md" "Context handoff quality" "context handoff row"
require_text "docs/RELIABILITY.md" "## Reliability Rules" "reliability rules"
require_text "docs/SECURITY.md" "## Security Non-Negotiables" "security non-negotiables"
require_text "docs/HARNESS.md" "## Harness Layers" "harness layers"
require_text "docs/AGENT_CONTEXT_PROTOCOL.md" "## 2) Context Architecture" "context architecture"
require_text "docs/archive/README.md" "## Archive Rules" "archive rules"
require_text "docs/generated/docs-catalog.md" "# Docs Catalog" "docs catalog heading"
require_text "docs/generated/legacy-doc-audit.md" "# Legacy Doc Audit" "legacy audit heading"
require_text "docs/generated/context-contract-report.md" "# Context Contract Report" "contract report heading"
require_text "docs/generated/context-efficiency-report.md" "# Context Efficiency Report" "context efficiency heading"
require_text "docs/generated/context-efficiency-report.md" "## Structural Scorecard" "context efficiency scorecard"
require_text "docs/generated/context-efficiency-report.md" "## Structural Readiness" "context structural readiness"
require_text "docs/generated/contextual-retrieval.md" "# Contextual Retrieval" "contextual retrieval heading"
require_text "docs/generated/agent-catalog.md" "# Agent Catalog" "agent catalog heading"
require_text "docs/generated/tool-catalog.md" "# Tool Catalog" "tool catalog heading"
require_text "docs/generated/agent-usage-report.md" "# Agent Usage Report" "agent usage report heading"
require_text "docs/generated/context-registry.md" "# Context Registry" "context registry heading"
require_text "docs/generated/context-ab-report.md" "# Context A/B Report" "context ab report heading"
require_text "docs/generated/sandbox-policy-report.md" "# Sandbox Policy Report" "sandbox policy report heading"
require_text "docs/generated/context-value-demo.md" "# Context Value Demo" "context value demo heading"
require_text "docs/generated/project-truth-bootstrap.md" "# Project Truth Bootstrap" "project truth bootstrap heading"
require_text "docs/generated/claude-compatibility-bootstrap.md" "# Claude Compatibility Bootstrap" "Claude compatibility bootstrap heading"
require_text ".claude/README.md" "## What Lives Here" "Claude router inventory"
require_text ".claude/agents/README.md" "## Included Defaults" "Claude agents defaults"
require_text ".claude/commands/README.md" "## Included Defaults" "Claude commands defaults"
require_text ".claude/hooks/README.md" "## Included Hooks" "Claude hooks defaults"

require_max_lines "AGENTS.md" 140
require_max_lines "ARCHITECTURE.md" 120
require_max_lines "docs/README.md" 180
require_max_lines "docs/CONTEXT_ENGINEERING.md" 220

require_absent "README.md" "__PROJECT_NAME__" "unrendered project placeholder"
require_absent "AGENTS.md" "__PROJECT_NAME__" "unrendered project placeholder in agents"
require_absent "docs/README.md" "__PROJECT_NAME__" "unrendered project placeholder in docs router"
require_absent "README.md" "{{PROJECT_NAME}}" "legacy moustache placeholder"
require_absent "AGENTS.md" "/Users/" "absolute local path in canonical doc"
require_absent "docs/README.md" "/Users/" "absolute local path in docs router"
require_absent "prompts/feature-loop-template.md" "docs/CONTEXT.md" "stale docs/CONTEXT reference in feature prompt"
require_absent "prompts/feature-loop-template.md" "NOTES.md" "stale NOTES reference in feature prompt"
require_absent "prompts/gc-loop-prompt.md" "docs/CONTEXT.md" "stale docs/CONTEXT reference in GC prompt"
require_absent "prompts/gc-loop-prompt.md" "NOTES.md" "stale NOTES reference in GC prompt"
require_absent "prompts/gc-loop-prompt.md" "skills/SKILLS.md" "stale skills registry reference in GC prompt"

if [ "$FAIL" -ne 0 ]; then
	echo "[docs:check] failed."
	exit 1
fi

echo "[docs:check] all context-system checks passed."
