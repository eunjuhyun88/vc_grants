# AGENTS.md

This file defines mandatory execution rules for coding agents in `VC_Grants`.

## Mandatory Start Sequence

1. Re-read `README.md` sections `0) Agent Collaboration Protocol (SSOT)` and `1.1) Context Routing`.
2. Re-read `docs/README.md` and open only the smallest relevant canonical doc set.
3. Re-read `docs/CONTEXT_ENGINEERING.md` when deciding retrieval order, compaction behavior, or evaluation.
4. If the task affects behavior, contracts, or architecture, open `docs/SYSTEM_INTENT.md` and `ARCHITECTURE.md`.
5. If the task is ambiguous, use `docs/CONTEXTUAL_RETRIEVAL.md` and `npm run retrieve:query -- --q "<term>"` before broad doc scanning.
6. If the task creates or changes reusable agents, open `docs/AGENT_FACTORY.md` and `agents/README.md`.
7. If the task creates or changes reusable tools, open `docs/TOOL_DESIGN.md` and `tools/README.md`.
8. If the task needs measured runtime evidence or time-saved tracking, open `docs/AGENT_OBSERVABILITY.md`.
9. If the task affects registry/API, public evaluation, or safety boundaries, open `docs/CONTEXT_PLATFORM.md` and `docs/SANDBOX_POLICY.md`.
10. If the task affects Claude-native commands, hooks, or local risk guidance, open `docs/CLAUDE_COMPATIBILITY.md` and `.claude/README.md`.
11. If the task involves branching, syncing, worktrees, or merge discipline, open `docs/GIT_WORKFLOW.md`.
12. Run `git status --short --branch`.
13. Reserve a work ID in the form `W-YYYYMMDD-HHMM-<repo>-<agent>`.
14. On feature branches, create or refresh a coordination claim:
   - `npm run coord:claim -- --work-id "<W-ID>" --agent "<agent>" --surface "<surface>" --summary "<summary>" --path "<prefix>"`
   - do not start meaningful edits on a feature branch without at least one claimed path prefix
15. Append a START entry in `docs/AGENT_WATCH_LOG.md`.
16. Run `npm run safe:status`.
17. For non-trivial work, create a semantic checkpoint:
   - `npm run ctx:checkpoint -- --work-id "<W-ID>" --surface "<surface>" --objective "<objective>"`
18. Work on a `codex/<task-name>` branch, not `main`.

## Mandatory Validation Gate

1. `npm run docs:check`
2. `npm run ctx:check -- --strict`
3. Project-specific `check`, `build`, or `gate` commands if configured in `context-kit.json`

If one fails, stop and fix it before push or merge.

## Context Budgeting Rules

1. `AGENTS.md` is a map, not a full manual.
2. Stable truth belongs in canonical docs or enforcement scripts.
3. Runtime memory belongs in `.agent-context/`, not in committed notes.
4. `docs/AGENT_WATCH_LOG.md` is evidence, not the primary resume surface.
5. Use `npm run ctx:restore -- --mode brief` first when resuming.
6. Keep the small map small enough that it still routes better than a broad docs dump.
7. Use `docs/MULTI_AGENT_COORDINATION.md` when two or more agents may touch related surfaces.
8. Use the registry manifest or query API before inventing new public discovery surfaces.
9. Use retrieval query before full canonical scans when task intent is fuzzy.
10. Use `docs/AGENT_FACTORY.md` before inventing a new agent prompt shape.
11. Use `docs/TOOL_DESIGN.md` before inventing a new tool wrapper.
12. Use `docs/AGENT_OBSERVABILITY.md` before claiming efficiency or time-saved wins.
13. If Claude Code is in use, keep `.claude/hooks/` deterministic and keep local `CLAUDE.md` files near risky directories short and specific.

## Finish Sequence

1. Update the relevant canonical docs if the task changed stable behavior.
2. Append FINISH evidence in `docs/AGENT_WATCH_LOG.md`.
3. Confirm the latest brief and handoff exist for the branch.
4. Release or hand off the active coordination claim.
5. Push or merge only with explicit human approval.
