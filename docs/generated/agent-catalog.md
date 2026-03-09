# Agent Catalog

This generated catalog lists the repo-local agent blueprints that outsiders can inspect and reuse.

## Overview

- Agent count: `3`
- Public agents: `3`

## Agents

| ID | Role | Surfaces | Manifest | Writes |
| --- | --- | --- | --- | --- |
| `implementer` | implementer | `core` | `agents/implementer.json` | `src/, .agent-context/, docs/AGENT_WATCH_LOG.md` |
| `planner` | planner | `core` | `agents/planner.json` | `docs/exec-plans/active/, .agent-context/, docs/AGENT_WATCH_LOG.md` |
| `reviewer` | reviewer | `core` | `agents/reviewer.json` | `.agent-context/, docs/AGENT_WATCH_LOG.md` |

## How To Use

- Create a new blueprint with `npm run agent:new -- --id "<agent-id>" --role "<role>" --surface "<surface>"`.
- Refresh generated artifacts with `npm run agent:refresh` and `npm run docs:refresh`.
- Search the public manifest with `npm run registry:query -- --kind agent --q "<term>"`.

