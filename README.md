# VC_Grants

> Single source of truth: this `README.md` is the canonical collaboration and execution guide for humans and agents.

VC fundraising pipeline automation - search, apply, follow-up, and track investment deals

## 0) Agent Collaboration Protocol (SSOT)

1. Re-read this `README.md` at the start of each non-trivial task.
2. Use `AGENTS.md` for mandatory execution rules.
3. Route documentation through `docs/README.md` instead of scanning the whole repo.
4. Record start/end evidence in `docs/AGENT_WATCH_LOG.md`.
5. Use semantic checkpoints for non-trivial work:
   - `npm run ctx:checkpoint -- --work-id "<W-ID>" --surface "<surface>" --objective "<objective>"`
6. Pass `npm run docs:check` and `npm run ctx:check -- --strict` before push or merge.
7. On feature branches, create a coordination claim before meaningful edits:
   - `npm run coord:claim -- --work-id "<W-ID>" --agent "<agent>" --surface "<surface>" --summary "<summary>" --path "<prefix>"`
   - feature branches should declare at least one owned path prefix
8. If project-specific `check`/`build` commands exist, wire them in `context-kit.json` and include them in your gate.
9. Do not commit `.agent-context/`.
10. Do not work directly on `main`; use a `codex/<task-name>` branch.

## 1) Overview

- Name: `VC_Grants`
- Stack: `Python / SQLite / Telegram`
- Phase: `re-design`
- Next deadline: `TBD`

## 1.1) Context Routing

The goal is not to read more files. The goal is to read the right files first.

1. Collaboration rules: `README.md`, `AGENTS.md`
2. Canonical doc router: `docs/README.md`
3. System intent and structure: `docs/SYSTEM_INTENT.md`, `ARCHITECTURE.md`
4. Context retrieval discipline and measurement: `docs/CONTEXT_ENGINEERING.md`, `docs/CONTEXT_EVALUATION.md`
5. Query-time retrieval layer: `docs/CONTEXTUAL_RETRIEVAL.md`
6. Claude-native repo layer: `docs/CLAUDE_COMPATIBILITY.md`, `.claude/README.md`
7. Agent blueprint design: `docs/AGENT_FACTORY.md`, `agents/README.md`
8. Tool contract design: `docs/TOOL_DESIGN.md`, `tools/README.md`
9. Agent runtime telemetry: `docs/AGENT_OBSERVABILITY.md`
10. Open-source platform layers: `docs/CONTEXT_PLATFORM.md`, `docs/SANDBOX_POLICY.md`
11. Parallel-agent ownership and handoff: `docs/MULTI_AGENT_COORDINATION.md`
12. Git operating rules: `docs/GIT_WORKFLOW.md`
13. Stable canonical entry docs:
   - `docs/DESIGN.md`
   - `docs/ENGINEERING.md`
   - `docs/PLANS.md`
   - `docs/PRODUCT_SENSE.md`
   - `docs/QUALITY_SCORE.md`
   - `docs/RELIABILITY.md`
   - `docs/SECURITY.md`
   - `docs/HARNESS.md`
12. Historical material: `docs/archive/`

## 2) Quick Start

```bash
npm run safe:hooks
npm run safe:git-config
npm run docs:refresh
npm run docs:check
npm run safe:status
```

## 3) Context Commands

- `npm run ctx:save`
- `npm run ctx:checkpoint`
- `npm run ctx:compact`
- `npm run ctx:check -- --strict`
- `npm run ctx:status`
- `npm run ctx:restore -- --mode brief`
- `npm run ctx:restore -- --mode handoff`
- `npm run ctx:pin`

## 3.1) Coordination Commands

- `npm run coord:claim`
- `npm run coord:list`
- `npm run coord:check`
- `npm run coord:release`

## 3.2) Git Commands

- `npm run safe:git-config`
- `npm run safe:status`
- `npm run safe:worktree -- <task-name> [base-branch]`
- `npm run safe:sync`
- `npm run safe:sync:gate`

## 3.3) Platform Commands

- `npm run agent:refresh`
- `npm run agent:new -- --id "<agent-id>" --role "<role>" --surface "<surface>"`
- `npm run tool:refresh`
- `npm run tool:new -- --id "<tool-id>" --surface "<surface>"`
- `npm run agent:start -- --agent "<agent-id>" --surface "<surface>"`
- `npm run agent:event -- --type "<event-type>"`
- `npm run agent:finish -- --status success --baseline-minutes <n>`
- `npm run agent:report`
- `npm run registry:refresh`
- `npm run registry:query -- --q "<term>"`
- `npm run registry:describe -- --kind "<kind>" --id "<id>"`
- `npm run registry:serve`
- `npm run retrieve:refresh`
- `npm run retrieve:query -- --q "<term>"`
- `npm run eval:ab:record`
- `npm run eval:ab:refresh`
- `npm run value:demo`
- `npm run sandbox:check`

### Context Artifact Model

1. `snapshot`
   - machine state, branch state, changed files
2. `checkpoint`
   - semantic working memory
3. `status`
   - single latest resume surface for the current branch or work item
4. `brief`
   - compact resume artifact with slightly more detail
5. `handoff`
   - fuller transfer artifact for the next session or agent

Paths:

- `.agent-context/snapshots/`
- `.agent-context/checkpoints/`
- `.agent-context/status/`
- `.agent-context/briefs/`
- `.agent-context/handoffs/`
- `.agent-context/compact/`

## 4) Configuration

Project-specific truth for this kit lives in:

- `context-kit.json`
- `docs/product-specs/*.md`
- `docs/design-docs/*.md`
- `docs/exec-plans/active/*.md`
- `docs/CONTEXT_ENGINEERING.md`
- `docs/CONTEXT_EVALUATION.md`
- `docs/CLAUDE_COMPATIBILITY.md`
- `docs/CONTEXT_PLATFORM.md`
- `docs/CONTEXTUAL_RETRIEVAL.md`
- `docs/AGENT_FACTORY.md`
- `docs/TOOL_DESIGN.md`
- `docs/AGENT_OBSERVABILITY.md`
- `docs/MULTI_AGENT_COORDINATION.md`
- `docs/GIT_WORKFLOW.md`
- `docs/SANDBOX_POLICY.md`
- `.claude/settings.json`
- `.claude/agents/*.md`
- `.claude/commands/*.md`
- `.claude/hooks/*.sh`
- `agents/*.json`
- `tools/*.json`

If route, store, or API discovery differs from the defaults, update `context-kit.json`.
