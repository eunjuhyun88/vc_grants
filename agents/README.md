# Agent Blueprints

This folder contains repo-local agent manifests.

Rules:

- each `*.json` file is one editable agent blueprint
- keep prompts short and role-specific
- declare `reads` and `writes` explicitly
- prefer canonical docs over large free-form prompt text
- refresh `docs/generated/agent-catalog.*` after edits

Useful commands:

- `npm run agent:new -- --id "<agent-id>" --role "<role>" --surface "<surface>"`
- `npm run agent:refresh`
- `npm run registry:query -- --kind agent --q "<term>"`
