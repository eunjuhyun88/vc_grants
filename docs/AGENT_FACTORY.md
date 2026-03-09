# Agent Factory

This document defines how a repository-local context system turns into reusable agent blueprints that other people can discover, trust, and run.

## Goal

Anyone should be able to:

1. inspect the canonical context map
2. find an existing agent blueprint
3. understand what that agent reads and writes
4. scaffold a new agent without inventing ad-hoc instructions

## Source Of Truth

Agent blueprints live in:

- `agents/*.json`
- `agents/README.md`
- `docs/generated/agent-catalog.md`
- `docs/generated/agent-catalog.json`

The generated catalog is the discovery surface.

The individual manifests are the editable source of truth.

## Manifest Contract

Each agent manifest should declare:

- `id`
- `name`
- `role`
- `summary`
- `surfaces`
- `reads`
- `writes`
- `outputs`
- `handoff`
- `prompt`

The key idea is simple: an agent is not just a prompt. It is a bounded worker with explicit context inputs and ownership outputs.

## Creation Flow

1. Route through `README.md`, `AGENTS.md`, and `docs/README.md`
2. Open the smallest canonical docs that define the surface
3. Scaffold the manifest:
   - `npm run agent:new -- --id "<agent-id>" --role "<role>" --surface "<surface>"`
4. Refresh generated artifacts:
   - `npm run agent:refresh`
   - `npm run docs:refresh`
5. Validate:
   - `npm run docs:check`
   - `npm run registry:query -- --kind agent --q "<agent-id>"`

## Design Rules

1. Agent manifests should point to canonical docs, not archive docs.
2. Agent manifests should name owned write prefixes explicitly.
3. Agent prompts should be short and role-specific.
4. Surface ownership should be declared with `surfaces`, not hidden in prose.
5. Public-facing agents should remain understandable from the manifest alone.

## Anti-Patterns

- giant prompt blobs in chat threads only
- agents with no declared write scope
- agents that depend on `docs/archive/`
- agents that require humans to remember hidden setup rules

## Open-Source Readiness

The kit is only broadly reusable if outsiders can discover working agents quickly.

That means:

- `docs/generated/agent-catalog.md` must stay current
- the registry manifest must expose agents
- the search API must return agents
- scaffolded agents must already follow the repo's context discipline
