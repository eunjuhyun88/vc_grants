# Tool Design

This document defines how repo-local tool contracts should be described so agents can use them without reading long prompt prose.

## Design Rules

- keep each tool single-purpose
- prefer a few explicit tools over many overlapping aliases
- declare input and output contracts in machine-readable manifests
- declare safety and side-effect level explicitly
- prefer read-only tools by default
- keep invocation explicit: npm script or HTTP endpoint

## Tool Contract Shape

Each `tools/*.json` manifest should declare:

- `id`, `name`, `summary`
- `scope`
- `surfaces`
- `reads` and `writes`
- `inputs` and `outputs`
- `invocation`
- `safety`

The minimum bar is that an outsider can inspect the manifest and know:

- when to use the tool
- what it expects
- what it returns
- whether it writes repo state

## Anti-Patterns

- wrapping the same behavior in several near-identical tools
- hiding destructive behavior inside a read-only-looking name
- forcing agents to guess JSON shapes from examples only
- making tools depend on chat-only instructions instead of manifests
- exposing large generic tools when smaller scoped tools would do

## Mechanical Enforcement

- keep tool manifests in `tools/*.json`
- refresh the generated catalog with `npm run tool:refresh`
- make the public registry expose tools through `/tools` and `kind=tool`
- keep registry, docs, and generated catalogs in sync through `npm run docs:check`

## Current Commands

- `npm run tool:new -- --id "<tool-id>" --surface "<surface>"`
- `npm run tool:refresh`
- `npm run registry:query -- --kind tool --q "<term>"`
- `npm run registry:describe -- --kind tool --id "<tool-id>"`
