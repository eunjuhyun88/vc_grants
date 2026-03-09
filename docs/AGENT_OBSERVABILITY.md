# Agent Observability

This document defines how agent runtime activity is recorded, summarized, and evaluated as evidence.

## Goal

The context system should not only route work correctly. It should also leave visible evidence that:

- agents found the right docs
- agents reached edits quickly
- resumed work stayed fast
- agent time was lower than the estimated manual baseline

## Runtime Artifacts

Telemetry lives in:

- `.agent-context/telemetry/runs/*.json`
- `.agent-context/telemetry/events/*.jsonl`
- `.agent-context/telemetry/active/*.json`
- `.agent-context/telemetry/telemetry.lock`
- `docs/generated/agent-usage-report.md`
- `docs/generated/agent-usage-report.json`

## Run Lifecycle

1. start a run
   - `npm run agent:start -- --agent "<agent-id>" --surface "<surface>"`
2. record important events
   - `npm run agent:event -- --type doc_open --path "docs/PLANS.md"`
   - `npm run agent:event -- --type first_edit --path "src/routes/+page.svelte"`
3. finish the run
   - `npm run agent:finish -- --status success --baseline-minutes 30`
4. refresh the report
   - `npm run agent:report`

Registry and retrieval queries are also auto-recorded when a branch has an active run.

## Economic Primitives

Each run should record a small set of comparable primitives:

- `taskComplexity`
- `skillLevel`
- `purpose`
- `autonomy`

These do not replace product analytics. They make agent work comparable enough that time-saved claims are not hand-wavy.

## Core Metrics

- run count
- success rate
- docs opened before first edit
- retrieval queries before first edit
- registry queries before first edit
- average run duration
- estimated baseline minutes
- estimated time saved
- primitive-level breakdowns for purpose, autonomy, and task complexity

## Rules

1. A run without finish data is incomplete evidence.
2. Estimated baseline minutes should be explicit, not implied.
3. Use the generated usage report for trends, not a single anecdotal run.
4. If a metric matters repeatedly, automate its event emission instead of relying on memory.
5. Report generation should not race run mutation; keep telemetry writes serialized.
