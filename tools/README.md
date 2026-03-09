# Tool Contracts

This folder contains repo-local tool manifests.

Rules:

- each `*.json` file is one tool contract
- keep inputs and outputs explicit
- declare side effects honestly
- prefer canonical docs and retrieval over prompt-only tool descriptions
- refresh `docs/generated/tool-catalog.*` after edits

Useful commands:

- `npm run tool:new -- --id "<tool-id>" --surface "<surface>"`
- `npm run tool:refresh`
- `npm run docs:refresh` when you also want the wider generated surface refreshed
- `npm run registry:query -- --kind tool --q "<term>"`
