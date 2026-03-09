# Context Registry

This generated manifest is the portable index for open-source discovery, local API serving, and agent-side search.

## Registry Overview

- Registry enabled: `yes`
- Public base URL: `not configured`
- Search kinds: `surface, doc, command, retrieval, agent, tool`
- Publish tags: `vc-grants, context-kit`

## Surfaces

| Surface | Label | Spec | Routes |
| --- | --- | --- | --- |
| `core` | Core surface | `docs/product-specs/core.md` | / |

## Canonical Docs

| Path | Role | Authority |
| --- | --- | --- |
| `README.md` | root-router | canonical |
| `AGENTS.md` | agent-rules | canonical |
| `ARCHITECTURE.md` | architecture-map | canonical |
| `docs/README.md` | docs-router | canonical |
| `docs/SYSTEM_INTENT.md` | system-intent | canonical |
| `docs/CONTEXT_ENGINEERING.md` | context-engineering | canonical |
| `docs/CONTEXT_EVALUATION.md` | context-evaluation | canonical |
| `docs/CONTEXT_PLATFORM.md` | context-platform | canonical |
| `docs/AGENT_FACTORY.md` | agent-factory | canonical |
| `docs/TOOL_DESIGN.md` | tool-design | canonical |
| `docs/AGENT_OBSERVABILITY.md` | agent-observability | canonical |
| `docs/MULTI_AGENT_COORDINATION.md` | coordination | canonical |
| `docs/SANDBOX_POLICY.md` | sandbox-policy | canonical |
| `docs/DESIGN.md` | design-authority | canonical |
| `docs/ENGINEERING.md` | engineering-authority | canonical |
| `docs/PLANS.md` | planning-authority | canonical |
| `docs/PRODUCT_SENSE.md` | product-heuristics | canonical |
| `docs/QUALITY_SCORE.md` | quality-score | canonical |
| `docs/RELIABILITY.md` | reliability | canonical |
| `docs/SECURITY.md` | security | canonical |
| `docs/HARNESS.md` | harness | canonical |
| `docs/product-specs/core.md` | surface-core | surface-canonical |

## Commands

| Command | Category | Script |
| --- | --- | --- |
| `agent:event` | agent | `node scripts/dev/log-agent-event.mjs` |
| `agent:finish` | agent | `node scripts/dev/finish-agent-run.mjs` |
| `agent:new` | agent | `node scripts/dev/scaffold-agent.mjs` |
| `agent:refresh` | agent | `node scripts/dev/refresh-agent-catalog.mjs && node scripts/dev/refresh-context-registry.mjs` |
| `agent:report` | agent | `node scripts/dev/refresh-agent-usage-report.mjs` |
| `agent:start` | agent | `node scripts/dev/start-agent-run.mjs` |
| `coord:check` | coord | `node scripts/dev/check-agent-coordination.mjs` |
| `coord:claim` | coord | `node scripts/dev/claim-work.mjs` |
| `coord:list` | coord | `node scripts/dev/list-work-claims.mjs` |
| `coord:release` | coord | `node scripts/dev/release-work.mjs` |
| `ctx:auto` | ctx | `bash scripts/dev/context-auto.sh` |
| `ctx:check` | ctx | `bash scripts/dev/check-context-quality.sh` |
| `ctx:checkpoint` | ctx | `bash scripts/dev/context-checkpoint.sh` |
| `ctx:compact` | ctx | `bash scripts/dev/context-compact.sh` |
| `ctx:pin` | ctx | `bash scripts/dev/context-pin.sh` |
| `ctx:restore` | ctx | `bash scripts/dev/context-restore.sh` |
| `ctx:save` | ctx | `bash scripts/dev/context-save.sh` |
| `docs:check` | docs | `bash scripts/dev/check-docs-context.sh` |
| `docs:refresh` | docs | `node scripts/dev/refresh-generated-context.mjs && node scripts/dev/refresh-context-retrieval.mjs && node scripts/dev/refresh-agent-catalog.mjs && node scripts/dev/refresh-tool-catalog.mjs && node scripts/dev/refresh-agent-usage-report.mjs && node scripts/dev/refresh-context-registry.mjs && node scripts/dev/refresh-context-ab-report.mjs && node scripts/dev/refresh-sandbox-policy-report.mjs && node scripts/dev/refresh-doc-governance.mjs && node scripts/dev/refresh-context-metrics.mjs && node scripts/dev/refresh-context-value-demo.mjs` |
| `docs:refresh:check` | docs | `node scripts/dev/refresh-generated-context.mjs --check && node scripts/dev/refresh-context-retrieval.mjs --check && node scripts/dev/refresh-agent-catalog.mjs --check && node scripts/dev/refresh-tool-catalog.mjs --check && node scripts/dev/refresh-agent-usage-report.mjs --check && node scripts/dev/refresh-context-registry.mjs --check && node scripts/dev/refresh-context-ab-report.mjs --check && node scripts/dev/refresh-sandbox-policy-report.mjs --check && node scripts/dev/refresh-doc-governance.mjs --check && node scripts/dev/refresh-context-metrics.mjs --check && node scripts/dev/refresh-context-value-demo.mjs --check` |
| `eval:ab:record` | eval | `node scripts/dev/record-context-ab-eval.mjs` |
| `eval:ab:refresh` | eval | `node scripts/dev/refresh-context-ab-report.mjs` |
| `gate:context` | gate | `npm run docs:check && npm run ctx:check -- --strict && npm run coord:check && npm run sandbox:check` |
| `harness:all` | harness | `bash scripts/dev/run-full-context-harness.sh` |
| `harness:benchmark` | harness | `node scripts/dev/run-context-benchmark.mjs` |
| `harness:browser` | harness | `bash scripts/dev/run-browser-context-harness.sh` |
| `harness:smoke` | harness | `bash scripts/dev/run-context-harness.sh` |
| `registry:describe` | registry | `node scripts/dev/describe-context-entry.mjs` |
| `registry:query` | registry | `node scripts/dev/query-context-registry.mjs` |
| `registry:refresh` | registry | `node scripts/dev/refresh-context-registry.mjs` |
| `registry:serve` | registry | `node scripts/dev/serve-context-registry.mjs` |
| `retrieve:query` | retrieve | `node scripts/dev/query-context-retrieval.mjs` |
| `retrieve:refresh` | retrieve | `node scripts/dev/refresh-context-retrieval.mjs` |
| `safe:git-config` | safe | `bash scripts/dev/bootstrap-git-config.sh` |
| `safe:hooks` | safe | `bash scripts/dev/install-git-hooks.sh` |
| `safe:status` | safe | `bash scripts/dev/safe-status.sh` |
| `safe:sync` | safe | `bash scripts/dev/sync-branch.sh` |
| `safe:sync:gate` | safe | `bash scripts/dev/sync-branch.sh --gate` |
| `safe:worktree` | safe | `bash scripts/dev/new-worktree.sh` |
| `sandbox:check` | sandbox | `node scripts/dev/refresh-sandbox-policy-report.mjs --validate-only` |
| `tool:new` | tool | `node scripts/dev/scaffold-tool.mjs` |
| `tool:refresh` | tool | `node scripts/dev/refresh-tool-catalog.mjs && node scripts/dev/refresh-context-registry.mjs` |

## Agents

| Agent | Role | Surfaces | Manifest |
| --- | --- | --- | --- |
| `implementer` | implementer | `core` | `agents/implementer.json` |
| `planner` | planner | `core` | `agents/planner.json` |
| `reviewer` | reviewer | `core` | `agents/reviewer.json` |

## Tools

| Tool | Scope | Surfaces | Manifest |
| --- | --- | --- | --- |
| `context-retrieve` | context-api | `core` | `tools/context-retrieve.json` |
| `coord-claim` | coordination | `core` | `tools/coord-claim.json` |
| `registry-search` | context-api | `core` | `tools/registry-search.json` |

## Retrieval

- Retrieval enabled: `yes`
- Indexed sources: `27`
- Indexed chunks: `154`

## Telemetry

- Telemetry enabled: `yes`
- Usage report: `docs/generated/agent-usage-report.json`

## How To Use

- Query locally with `npm run registry:query -- --q "<term>"`.
- Search just agents with `npm run registry:query -- --kind agent --q "<term>"`.
- Search reusable tools with `npm run registry:query -- --kind tool --q "<term>"`.
- Inspect one contract with `npm run registry:describe -- --kind "<kind>" --id "<id>"`.
- Record measured work with `npm run agent:start`, `npm run agent:event`, `npm run agent:finish`, and `npm run agent:report`.
- Query retrieval chunks with `npm run retrieve:query -- --q "<term>"`.
- Scaffold a new blueprint with `npm run agent:new -- --id "<agent-id>" --role "<role>" --surface "<surface>"`.
- Scaffold a new tool contract with `npm run tool:new -- --id "<tool-id>" --surface "<surface>"`.
- Serve locally with `npm run registry:serve` to expose `/manifest`, `/agents`, `/tools`, and `/search`.
- Publish the JSON manifest if you want external agents or indexes to discover this repo.

