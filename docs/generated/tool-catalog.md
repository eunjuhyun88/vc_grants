# Tool Catalog

This generated catalog lists repo-local tool contracts that agents can reuse without reading large free-form prompt text.

## Overview

- Tool count: `3`
- Public tools: `3`

## Tools

| ID | Scope | Surfaces | Safety | Invocation |
| --- | --- | --- | --- | --- |
| `context-retrieve` | context-api | `core` | `read-only` | `retrieve:query` |
| `coord-claim` | coordination | `core` | `writes-generated` | `coord:claim` |
| `registry-search` | context-api | `core` | `read-only` | `registry:query` |

## How To Use

- Create a new tool contract with `npm run tool:new -- --id "<tool-id>" --surface "<surface>"`.
- Refresh generated artifacts with `npm run tool:refresh` and `npm run docs:refresh`.
- Search the public manifest with `npm run registry:query -- --kind tool --q "<term>"`.

