# VC_Grants Architecture Map

Purpose:

- Top-level map for humans and agents
- Read this before large structural work
- Use this file to choose deeper docs

## Read Order

1. `README.md`
2. `AGENTS.md`
3. `docs/README.md`
4. `docs/SYSTEM_INTENT.md`
5. `docs/CONTEXT_ENGINEERING.md`
6. `docs/CLAUDE_COMPATIBILITY.md`
7. `docs/CONTEXTUAL_RETRIEVAL.md`
8. `docs/AGENT_FACTORY.md`
9. `docs/TOOL_DESIGN.md`
10. `docs/AGENT_OBSERVABILITY.md`
11. `docs/CONTEXT_PLATFORM.md`
12. `docs/MULTI_AGENT_COORDINATION.md`
13. `docs/GIT_WORKFLOW.md`
14. `ARCHITECTURE.md`
15. Relevant canonical docs from `docs/`

## System Map

```
Telegram 명령 → interface/telegram_app.py → interface/handlers/ (핸들러)
  → Deterministic: db/entity_store.py → Eligibility Filter → card_renderer.py → Telegram
  → Reasoned: agents/* → db/entity_store.py → card_renderer.py → Telegram

Agent Pipeline:
  Discovery Agent → Entity Resolution → Verification Agent → DB
  → Matching Agent → fit_recommendations → Output

Entity 계층: Organization → Program → Opportunity → Endpoint → Observation
```

## Non-Negotiable Boundaries

1. The current git worktree rooted at this repository is the canonical implementation target.
2. `docs/archive/` is not current authority.
3. Stable rules belong in canonical docs or scripts.
4. Product intent must be readable from repo-local markdown.
5. Agents should start with a small map and progressively disclose detail.

## Canonical Doc Entry Points

- Design and architecture: `docs/DESIGN.md`
- Implementation/state ownership: `docs/ENGINEERING.md`
- Product rules and user-value constraints: `docs/PRODUCT_SENSE.md`
- Current plans: `docs/PLANS.md`
- Context retrieval and measurement rules: `docs/CONTEXT_ENGINEERING.md`, `docs/CONTEXT_EVALUATION.md`
- Claude-native repo layer: `docs/CLAUDE_COMPATIBILITY.md`, `.claude/README.md`
- Query-time retrieval rules: `docs/CONTEXTUAL_RETRIEVAL.md`
- Agent blueprint rules: `docs/AGENT_FACTORY.md`, `agents/README.md`
- Tool contract rules: `docs/TOOL_DESIGN.md`, `tools/README.md`
- Agent runtime telemetry rules: `docs/AGENT_OBSERVABILITY.md`
- Context platform and discovery rules: `docs/CONTEXT_PLATFORM.md`
- Parallel-agent ownership rules: `docs/MULTI_AGENT_COORDINATION.md`
- Git workflow and sync rules: `docs/GIT_WORKFLOW.md`
- Reliability boundaries: `docs/RELIABILITY.md`
- Security boundaries: `docs/SECURITY.md`, `docs/SANDBOX_POLICY.md`
- Harness and legibility evidence: `docs/HARNESS.md`
