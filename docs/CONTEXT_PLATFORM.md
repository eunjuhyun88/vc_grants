# Context Platform

This document defines the extra layers needed when the context system becomes a reusable open-source platform instead of a repo-local convention.

## Registry Model

The platform should expose a portable manifest so external agents and tools can discover:

- surfaces
- canonical docs
- reusable agents
- reusable tools
- supported commands
- evaluation capabilities
- query-time retrieval capabilities

Current local artifacts:

- `docs/generated/context-registry.json`
- `docs/generated/context-registry.md`
- `npm run registry:query -- --q "<term>"`
- `npm run registry:describe -- --kind "<kind>" --id "<id>"`
- `npm run registry:serve`

## Agent Blueprint Model

The platform should expose reusable agent blueprints, not just docs and commands.

Current local artifacts:

- `docs/AGENT_FACTORY.md`
- `agents/*.json`
- `docs/generated/agent-catalog.md`
- `docs/generated/agent-catalog.json`
- `npm run agent:new -- --id "<agent-id>" --role "<role>" --surface "<surface>"`

Each manifest should remain legible without replaying a chat transcript. That is the minimum bar for a public agent blueprint.

## Tool Contract Model

The platform should expose reusable tool contracts, not just docs and commands.

Current local artifacts:

- `docs/TOOL_DESIGN.md`
- `tools/*.json`
- `docs/generated/tool-catalog.md`
- `docs/generated/tool-catalog.json`
- `npm run tool:new -- --id "<tool-id>" --surface "<surface>"`

Each contract should remain inspectable without hidden prompt glue. That is the minimum bar for a public tool surface.

## Retrieval Model

The platform should also expose a query-time retrieval surface for ambiguous tasks.

Current local artifacts:

- `docs/CONTEXTUAL_RETRIEVAL.md`
- `docs/generated/contextual-retrieval.md`
- `docs/generated/contextual-retrieval-index.json`
- `npm run retrieve:query -- --q "<term>"`
- `GET /retrieve?q=<term>` from `npm run registry:serve`

The JSON manifest is the stable machine-readable contract. The Markdown file is the human-readable index.

## Open API Model

The local registry server exposes:

- `GET /healthz`
- `GET /manifest`
- `GET /agents`
- `GET /tools`
- `GET /agent-usage`
- `GET /search?q=<term>&kind=<surface|doc|command|retrieval|agent|tool>`
- `GET /describe?kind=<kind>&id=<id>`

This is intentionally small. It is enough to:

- prove that discovery can be queried over HTTP
- back a future shared registry or catalog
- let users integrate the kit into tool routers without parsing Markdown
- let outsiders discover safe reusable tools before inventing new ones

The extra `describe` surface matters for agents because it turns discovery into an inspectable contract instead of a prompt-only guess.

## Evaluation Model

Open-source users should be able to see whether the context system helped.

Required evidence layers:

1. structural savings
   - `docs/generated/context-efficiency-report.md`
2. routed-vs-baseline task comparisons
   - `docs/generated/context-ab-report.md`
   - `npm run eval:ab:record`
3. runtime noise/stability
   - `.agent-context/evaluations/<run-id>/summary.md`
   - `npm run harness:benchmark -- --base-url <url>`
4. measured agent usage and time-saved evidence
   - `docs/generated/agent-usage-report.md`
   - `npm run agent:start`
   - `npm run agent:finish`
   - `npm run agent:report`

## Sandbox Model

Open-source distribution needs a visible safety boundary, not just trust.

Repo-local policy lives in:

- `context-kit.json -> sandbox`
- `docs/SANDBOX_POLICY.md`
- `docs/generated/sandbox-policy-report.md`

The kit does not pretend to be a full OS sandbox. Instead, it makes the intended boundary explicit and mechanically checkable.

## Visibility Model

If this kit is published for broad use, users should be able to see:

- what the repo exposes through the registry
- which reusable agents already exist
- whether measured runs show real time-saved evidence
- whether routed mode beat baseline mode
- whether runtime comparisons were noise-controlled
- what safety policy bounded agent execution

That is the minimum bar for a context platform that feels tangible instead of theoretical.
