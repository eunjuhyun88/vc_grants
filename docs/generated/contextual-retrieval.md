# Contextual Retrieval

This generated artifact summarizes the query-time retrieval index for canonical docs.

## Retrieval Model

- Retrieval mode: deterministic contextual BM25
- Chunk context: path, authority, section headings, and surface ownership are prepended before indexing
- Goal: reduce full-doc scanning when the agent is uncertain what to open next

## Index Stats

- Source docs indexed: `27`
- Chunks indexed: `154`
- Chunk size (words): `120`
- Overlap size (words): `30`
- Default top-k: `5`

## Top Indexed Paths

| Path | Chunk Count |
| --- | --- |
| `docs/CONTEXT_EVALUATION.md` | 22 |
| `docs/CONTEXT_ENGINEERING.md` | 18 |
| `README.md` | 12 |
| `docs/CONTEXT_PLATFORM.md` | 9 |
| `docs/MULTI_AGENT_COORDINATION.md` | 9 |
| `AGENTS.md` | 8 |
| `docs/AGENT_FACTORY.md` | 8 |
| `docs/AGENT_OBSERVABILITY.md` | 7 |
| `docs/product-specs/core.md` | 7 |
| `docs/CONTEXTUAL_RETRIEVAL.md` | 6 |
| `docs/ENGINEERING.md` | 6 |
| `docs/SANDBOX_POLICY.md` | 6 |
| `docs/TOOL_DESIGN.md` | 6 |
| `ARCHITECTURE.md` | 5 |
| `docs/QUALITY_SCORE.md` | 4 |

## Commands

- `npm run retrieve:query -- --q "<term>"`
- `npm run registry:serve` then `GET /retrieve?q=<term>`

## Limits

- This is a lexical/contextual bootstrap index, not an embedding+rereank system.
- For very large repos, the JSON index may later move to runtime-only storage.

