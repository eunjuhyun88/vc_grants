# Context Engineering

This file defines how context should be shaped, retrieved, compacted, and measured in this repository.

## Context Layers

1. Small map
   - `README.md`
   - `AGENTS.md`
   - `docs/README.md`
   - `ARCHITECTURE.md`
   - `docs/SYSTEM_INTENT.md`
   - `docs/CONTEXT_ENGINEERING.md`
   - `docs/CLAUDE_COMPATIBILITY.md` when Claude-native hooks, commands, or local guidance matter
2. Canonical surface docs
   - `docs/product-specs/*.md`
   - `docs/design-docs/*.md`
   - `docs/{DESIGN,ENGINEERING,PLANS,PRODUCT_SENSE,QUALITY_SCORE,RELIABILITY,SECURITY,HARNESS}.md`
3. Generated navigation
  - `docs/generated/{route-map,store-authority-map,api-group-map}.md`
  - `docs/generated/context-efficiency-report.md`
  - `docs/generated/context-registry.{md,json}`
4. Agent blueprints
  - `docs/AGENT_FACTORY.md`
  - `agents/*.json`
  - `docs/generated/agent-catalog.{md,json}`
5. Query-time retrieval
  - `docs/CONTEXTUAL_RETRIEVAL.md`
  - `docs/generated/contextual-retrieval.md`
  - `docs/generated/contextual-retrieval-index.json`
6. Platform boundary
  - `docs/CONTEXT_PLATFORM.md`
  - `docs/generated/context-ab-report.md`
  - `docs/generated/sandbox-policy-report.md`
7. Coordination boundary
  - `docs/MULTI_AGENT_COORDINATION.md`
  - `.agent-context/coordination/claims/*`
8. Active plans
  - `docs/exec-plans/active/*.md`
9. Historical context
  - `docs/archive/*`
10. Runtime working memory
  - `.agent-context/*`

## Retrieval Order

Agents should not load context in arbitrary order.

### Standard order

1. `README.md`
2. `AGENTS.md`
3. `docs/README.md`
4. `ARCHITECTURE.md`
5. `docs/SYSTEM_INTENT.md`
6. `docs/CONTEXT_ENGINEERING.md`
7. the smallest surface-specific canonical docs
8. generated maps if route/store/API navigation is needed
9. active plans only if the canonical docs are insufficient

### Rule

The small map must be enough to decide what to read next.

If an agent must open large numbers of files before it can choose a path, the context system is failing.

## Anti-Patterns

### 1. Monolithic instruction dump

Bad:

- one giant `AGENTS.md`
- one giant prompt blob
- one giant design document with no routing

Why it fails:

- crowds out task-specific context
- becomes stale quickly
- turns all guidance into undifferentiated noise

### 2. Full-doc scanning

Bad:

- reading every file in `docs/` before starting
- opening `docs/archive/` by default
- scanning the full watch log before canonical docs

Why it fails:

- increases context pollution
- increases retrieval latency
- reduces focus on the active task

### 3. Runtime memory as authority

Bad:

- relying on `.agent-context/briefs/*` as source of truth
- putting stable architectural rules only in checkpoints or handoffs

Why it fails:

- branch-local memory is transient
- authority drifts away from versioned docs

### 4. Unmeasured “more context is better”

Bad:

- adding docs without bundle budgets
- adding retrieval steps without measuring reduction or recovery speed

Why it fails:

- context windows still degrade under excess load
- bigger context is not free

## Mechanical Enforcement

This repository should enforce context discipline mechanically.

### Current controls

- `scripts/dev/check-docs-context.sh`
  - required files, required headings, small-map line budgets, and placeholder/path hygiene checks
- `scripts/dev/check-context-quality.sh`
  - brief/handoff quality checks
- `scripts/dev/refresh-generated-context.mjs`
  - route/store/API discovery maps
- `scripts/dev/refresh-doc-governance.mjs`
  - authority catalog, legacy audit, contract report
- `scripts/dev/refresh-context-metrics.mjs`
  - bundle-size and savings report
- `scripts/dev/bootstrap-claude-compat.mjs`
  - Claude-native compatibility layer and risky-path local guidance bootstrap
- `scripts/dev/refresh-context-registry.mjs`
  - portable registry manifest and open-source query surface
- `scripts/dev/refresh-context-retrieval.mjs`
  - query-time chunk index and retrieval summary
- `scripts/dev/refresh-agent-catalog.mjs`
  - reusable agent blueprint catalog
- `scripts/dev/refresh-context-ab-report.mjs`
  - routed-vs-baseline task comparison summary
- `scripts/dev/refresh-sandbox-policy-report.mjs`
  - explicit sandbox boundary report
- `.githooks/pre-push`
  - enforces context and optional project gates before push
- `.claude/hooks/*`
  - refresh lightweight runtime memory and compaction artifacts inside Claude Code

Thresholds should start bootstrap-safe and tighten as the repo grows. The defaults live in `context-kit.json`.

## Compaction Policy

Use compaction when:

- the task spans multiple hours
- the agent has accumulated large tool output
- the session is being handed off
- the next phase depends more on decisions than on raw logs

Compaction is not a substitute for canonical docs.

## Measurement and Noise Control

Context engineering should be measured in two layers.

### A. Structural savings

Measured automatically:

- small-map bundle size
- canonical bundle size
- all-docs bundle size
- surface bundle size
- estimated reduction percentages

See:

- `docs/generated/context-efficiency-report.md`
- `docs/CONTEXT_EVALUATION.md`

### B. Task-level performance

Measured with controlled task runs:

- same model
- same prompt scaffolding
- same branch and code state
- same machine or container resource configuration
- same tool availability
- repeated runs per mode
- fixed retry policy
- fixed warmup policy

This follows the same basic principle highlighted by Anthropic’s infrastructure-noise work: do not mistake environment variance for model or context-system improvement.

### Noise-control rules

- Do not compare a routed run and a baseline run from different machine envelopes.
- Do not silently rerun only the worse mode.
- Record warmup runs separately from measured runs.
- Treat browser startup, local preview instability, and missing tool binaries as infra noise until classified.

## Success Criteria

The context system is healthy when:

- the small map is enough to route most tasks
- surface bundles are materially smaller than canonical/all-doc bundles
- retrieval can disambiguate the next canonical doc set without broad scans
- reusable agents can be discovered from repo-local manifests without hidden setup knowledge
- agents can resume work from brief/handoff artifacts quickly
- docs checks fail before drift spreads
- harness evidence can be produced without reading the full repo
- repeated benchmark runs stay under the configured noise threshold
