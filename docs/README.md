# Docs Context Map

Purpose:

- `README.md` is the collaboration SSOT
- this file is the task-level document router
- agents should read this before opening many docs

## Fast Start

1. `README.md`
2. `AGENTS.md`
3. `docs/SYSTEM_INTENT.md`
4. `ARCHITECTURE.md`
5. `docs/CONTEXT_ENGINEERING.md`
6. `docs/CLAUDE_COMPATIBILITY.md` when Claude-native commands, hooks, or local guidance are in play
7. `docs/CONTEXTUAL_RETRIEVAL.md` when the right canonical docs are still unclear
8. `docs/AGENT_FACTORY.md` when creating or revising reusable agents
9. `docs/TOOL_DESIGN.md` when creating or revising reusable tools
10. `docs/AGENT_OBSERVABILITY.md` when work needs runtime evidence or value measurement
11. `docs/CONTEXT_PLATFORM.md` for registry, open-source, or public evaluation work
12. `docs/MULTI_AGENT_COORDINATION.md` when parallel work is possible
13. `docs/GIT_WORKFLOW.md` when branching, syncing, or merge discipline matters
14. `docs/README.md`
15. the smallest relevant canonical doc subset

## Active Boundaries

- Active implementation target: the current git worktree rooted at this repository
- Canonical code should live in repo-local tracked paths
- `.agent-context/` is runtime memory, not authority
- `docs/archive/` is historical, not current authority
- `docs/AGENT_WATCH_LOG.md` is an operations log, not a design spec

## Structured Knowledge Base

- `docs/design-docs/`
  - stable design documents and beliefs
- `docs/product-specs/`
  - short surface specs keyed by `context-kit.json`
- `docs/exec-plans/`
  - active, completed, and debt-tracking execution docs
- `docs/generated/`
  - derived navigation and governance artifacts
- `docs/references/`
  - prompts, references, and supporting material
- `.claude/`
  - Claude-native agents, commands, hooks, and settings
- `agents/`
  - repo-local agent manifests that outsiders can inspect and reuse
- `tools/`
  - repo-local tool contracts that outsiders can inspect and reuse

## Canonical Entry Docs

| If you need... | Open this first | Then go deeper to... |
| --- | --- | --- |
| system intent | `docs/SYSTEM_INTENT.md` | `docs/design-docs/core-beliefs.md` |
| architecture map | `ARCHITECTURE.md` | `docs/DESIGN.md`, `docs/ENGINEERING.md` |
| retrieval order, anti-patterns, measurement | `docs/CONTEXT_ENGINEERING.md` | `docs/CONTEXT_EVALUATION.md`, `docs/generated/context-efficiency-report.md`, `docs/generated/context-value-demo.md` |
| Claude-native repo workflows | `docs/CLAUDE_COMPATIBILITY.md` | `.claude/README.md`, `.claude/agents/`, `.claude/commands/`, `.claude/hooks/` |
| query-time doc retrieval | `docs/CONTEXTUAL_RETRIEVAL.md` | `docs/generated/contextual-retrieval.md`, `npm run retrieve:query -- --q "<term>"` |
| reusable agent design and scaffolding | `docs/AGENT_FACTORY.md` | `agents/README.md`, `docs/generated/agent-catalog.md`, `npm run agent:new -- --id "<agent-id>" --role "<role>" --surface "<surface>"` |
| reusable tool contracts | `docs/TOOL_DESIGN.md` | `tools/README.md`, `docs/generated/tool-catalog.md`, `npm run tool:new -- --id "<tool-id>" --surface "<surface>"`, `npm run tool:refresh` |
| runtime telemetry and time-saved evidence | `docs/AGENT_OBSERVABILITY.md` | `docs/generated/agent-usage-report.md`, `npm run agent:start`, `npm run agent:finish`, `npm run agent:report` |
| registry/API, open-source packaging, public evaluation | `docs/CONTEXT_PLATFORM.md` | `docs/generated/context-registry.md`, `docs/generated/context-ab-report.md`, `npm run registry:describe -- --kind "<kind>" --id "<id>"` |
| concurrent ownership, handoff, path boundaries | `docs/MULTI_AGENT_COORDINATION.md` | `context-kit.json`, `.agent-context/coordination/`, `scripts/dev/check-agent-coordination.mjs` |
| branch/worktree/sync discipline | `docs/GIT_WORKFLOW.md` | `scripts/dev/safe-status.sh`, `scripts/dev/new-worktree.sh`, `scripts/dev/sync-branch.sh`, `scripts/dev/bootstrap-git-config.sh` |
| current design authority | `docs/DESIGN.md` | `docs/design-docs/index.md`, active plans |
| implementation/state ownership | `docs/ENGINEERING.md` | `docs/generated/route-map.md`, `docs/generated/store-authority-map.md`, `docs/generated/api-group-map.md` |
| product scope and heuristics | `docs/PRODUCT_SENSE.md` | `docs/product-specs/*.md` |
| current plans | `docs/PLANS.md` | `docs/exec-plans/index.md` |
| quality/drift priorities | `docs/QUALITY_SCORE.md` | `docs/generated/legacy-doc-audit.md`, `docs/exec-plans/tech-debt-tracker.md` |
| harness and local evidence | `docs/HARNESS.md` | `scripts/dev/run-context-harness.sh`, `scripts/dev/run-browser-context-harness.sh` |
| security boundaries | `docs/SECURITY.md` | `docs/SANDBOX_POLICY.md`, supporting references |

## Promotion Rules

- Stable collaboration rules go in `README.md` or `AGENTS.md`
- Stable architecture routing goes in `ARCHITECTURE.md`
- Stable retrieval and anti-pattern rules go in `docs/CONTEXT_ENGINEERING.md`
- Stable Claude-native routing and automation rules go in `docs/CLAUDE_COMPATIBILITY.md`
- Stable query-time retrieval behavior goes in `docs/CONTEXTUAL_RETRIEVAL.md`
- Stable agent blueprint rules go in `docs/AGENT_FACTORY.md`
- Stable tool contract rules go in `docs/TOOL_DESIGN.md`
- Stable runtime telemetry rules go in `docs/AGENT_OBSERVABILITY.md`
- Stable platform/registry/sandbox rules go in `docs/CONTEXT_PLATFORM.md` and `docs/SANDBOX_POLICY.md`
- Stable task routing goes in `docs/README.md`
- Stable product behavior goes in `docs/product-specs/*.md`
- Current implementation work goes in `docs/exec-plans/active/`
- Historical material moves to `docs/archive/`
