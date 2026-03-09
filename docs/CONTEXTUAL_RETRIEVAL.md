# Contextual Retrieval

## Retrieval Model

This repository uses a deterministic contextual retrieval layer for canonical docs.

The retrieval index is built from:

- root collaboration docs
- canonical docs under `docs/`
- design docs
- surface specs

Each chunk is indexed with a contextual prefix that includes:

- source path
- authority/role
- section heading path
- surface ownership

This follows the same high-level idea as contextual retrieval: retrieval should rank a chunk using both the chunk content and the chunk's local meaning inside the broader document graph.

## Query Workflow

Use this order when the correct next doc is unclear:

1. small map first
   - `README.md`
   - `AGENTS.md`
   - `docs/README.md`
2. generated maps if the task already has a known route/store/API
3. contextual retrieval if the task is still ambiguous
   - `npm run retrieve:query -- --q "<question>"`
4. open only the highest-scoring canonical docs or sections

The goal is not to replace canonical docs. The goal is to make the jump from uncertainty to the right canonical doc set cheaper.

## Retrieval Commands

- `npm run retrieve:refresh`
- `npm run retrieve:query -- --q "<term>"`
- `npm run registry:serve` then `GET /retrieve?q=<term>`

## Scoring

Current bootstrap scoring combines:

- contextual lexical score
- raw chunk lexical score
- path match bonus
- heading match bonus
- optional surface match bonus

This is intentionally deterministic and repo-local. It does not require external embeddings to be useful.

## Limits

- This is not yet an embedding+rereank pipeline.
- It is strongest on canonical docs and weaker on vague or low-information prose.
- Very large repos may later move the JSON index to runtime-only storage instead of `docs/generated/`.

## Success Criteria

Retrieval is healthy when:

- the top few results point to canonical docs instead of broad scans
- routed mode opens fewer docs before first edit on ambiguous tasks
- the retrieval index remains cheap enough to regenerate during `docs:refresh`

