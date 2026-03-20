# Contextual Retrieval

This generated artifact summarizes the query-time retrieval index for canonical docs.

## Retrieval Model

- Retrieval mode: deterministic contextual BM25
- Chunk context: path, authority, section headings, and surface ownership are prepended before indexing
- Goal: reduce full-doc scanning when the agent is uncertain what to open next

## Index Stats

- Source docs indexed: `46`
- Chunks indexed: `595`
- Chunk size (words): `120`
- Overlap size (words): `30`
- Default top-k: `5`

## Top Indexed Paths

| Path | Chunk Count |
| --- | --- |
| `docs/design-docs/AUTORESEARCH_ADOPTION.md` | 51 |
| `docs/design-docs/ARCHITECTURE.md` | 32 |
| `docs/design-docs/AGENT_CONTRACTS.md` | 31 |
| `docs/product-specs/DEV_SETUP.md` | 27 |
| `docs/product-specs/PRD.md` | 27 |
| `docs/product-specs/AGENTS_SPEC.md` | 25 |
| `docs/design-docs/PRIORITY_ALGORITHM.md` | 24 |
| `docs/product-specs/core.md` | 24 |
| `docs/CONTEXT_EVALUATION.md` | 22 |
| `docs/design-docs/DATA_FILL_SPEC.md` | 22 |
| `docs/design-docs/TELEGRAM_UX.md` | 21 |
| `docs/design-docs/OPERATIONS_MODEL.md` | 20 |
| `docs/design-docs/DB_SCHEMA.md` | 19 |
| `docs/product-specs/PIPELINE_SPEC.md` | 19 |
| `docs/CONTEXT_ENGINEERING.md` | 18 |

## Commands

- `npm run retrieve:query -- --q "<term>"`
- `npm run registry:serve` then `GET /retrieve?q=<term>`

## Limits

- This is a lexical/contextual bootstrap index, not an embedding+rereank system.
- For very large repos, the JSON index may later move to runtime-only storage.

