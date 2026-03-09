---
description: Rehydrate the current task from Memento working memory and canonical docs before touching code.
---

1. Run `git status --short --branch`.
2. Run `npm run ctx:restore -- --mode brief`.
3. If no brief exists, read `README.md`, `AGENTS.md`, `docs/README.md`, `docs/SYSTEM_INTENT.md`, and `ARCHITECTURE.md`.
4. Summarize:
   - current objective
   - next step
   - read-first docs
   - open questions
5. Do not start in `docs/archive/` unless canonical docs are insufficient.
