# Agent Watch Log

Use this file as an evidence log for task start/end, not as the main design authority.

## Entry Template

### START

- Work ID:
- Branch:
- Base:
- Working tree:
- Task summary:
- Owned files:
- Validation snapshot:

### FINISH

- Work ID:
- Branch:
- Commit:
- Validation:
- Push/Merge status:
- Final working tree:

### START

- Work ID: `W-20260310-2012-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (`src/agents/discovery.py` modified; `VC_Fundraising0/`, `data/funding.db-shm`, `data/funding.db-wal` untracked)
- Task summary: reconstruct what product this repository is trying to build and how far the current implementation reflects that intent
- Owned files: `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`npm run safe:status`)

### START

- Work ID: `W-20260311-2228-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (prior docs/code/data changes remain uncommitted across `docs/`, `src/`, `output/`, `data/`, and `VC_Fundraising0/`; this task focuses on Twitter-backed discovery design + implementation under claimed search/interface/docs paths)
- Task summary: make Twitter/X a real candidate-discovery source using FxTwitter-backed fetch and canonicalize the discovery design so `/funding` and `/discover` can actually use social findings
- Owned files: `src/search/`, `src/agents/`, `src/interface/handlers/`, `docs/design-docs/`, `docs/exec-plans/active/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`npm run docs:check`, `npm run ctx:check -- --strict`, targeted pytest)

### START

- Work ID: `W-20260311-2318-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (prior docs/code/data changes remain uncommitted; this task adds an autoresearch adoption plan on top of the current Funding Intelligence discovery stack)
- Task summary: define how autoresearch should be adapted for Funding Intelligence so search strategies can improve automatically without changing fact/verification truth boundaries
- Owned files: `docs/design-docs/`, `docs/exec-plans/active/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`npm run docs:refresh`, `npm run docs:check`, `npm run ctx:check -- --strict`)

### FINISH

- Work ID: `W-20260311-2318-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `npm run docs:refresh` passed; `npm run docs:check` passed; `npm run ctx:check -- --strict` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task added `docs/design-docs/AUTORESEARCH_ADOPTION.md`, updated `docs/design-docs/index.md`, `docs/exec-plans/active/MVP_IMPLEMENTATION.md`, refreshed `docs/generated/*`, and updated `.agent-context/*`; unrelated prior worktree changes remain)

### FINISH

- Work ID: `W-20260311-2228-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `python3 -m pytest -q tests/search/test_social_engine.py tests/search/test_orchestrator.py tests/search/test_engines.py` passed; `python3 -m py_compile src/search/engines/social_engine.py src/core/config.py tests/search/test_social_engine.py` passed; runtime smoke `SocialSearchEngine.search(HOOT)` returned 19 social candidates via Tavily + FxTwitter; `npm run docs:refresh` passed; `npm run docs:check` passed; `npm run ctx:check -- --strict` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task updated `src/search/engines/social_engine.py`, `src/core/config.py`, `.env.example`, `tests/search/test_social_engine.py`, `docs/design-docs/SOCIAL_DISCOVERY.md`, `docs/design-docs/index.md`, `docs/product-specs/DEV_SETUP.md`, refreshed `docs/generated/*`, and updated `.agent-context/*`; unrelated prior worktree changes remain)

### FINISH

- Work ID: `W-20260310-2012-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `ctx:check -- --strict` passed; `docs:check` failed due missing `src/db/CLAUDE.md` required by Claude compatibility bootstrap
- Push/Merge status: not attempted
- Final working tree: dirty (`docs/AGENT_WATCH_LOG.md`, several `docs/generated/*` refreshed, user change in `src/agents/discovery.py`, untracked `VC_Fundraising0/`, `data/funding.db-shm`, `data/funding.db-wal`)

### START

- Work ID: `W-20260310-2040-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (`docs/generated/*` refreshed from prior task; `src/agents/discovery.py` modified; `VC_Fundraising0/`, `data/funding.db-shm`, `data/funding.db-wal` untracked)
- Task summary: replace placeholder Telegram surface spec and add supporting design docs for Telegram UX and operations model
- Owned files: `docs/product-specs/core.md`, `docs/design-docs/`
- Validation snapshot: pending (`npm run safe:status`)

### FINISH

- Work ID: `W-20260310-2040-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `docs:check` passed; `ctx:check -- --strict` passed; `coord:check` failed because the branch already contained unrelated user changes outside this claim
- Push/Merge status: not attempted
- Final working tree: dirty (this task updated canonical docs and refreshed `docs/generated/*`; unrelated user changes remain in `src/agents/discovery.py`, `VC_Fundraising0/`, `data/funding.db-shm`, `data/funding.db-wal`)

### START

- Work ID: `W-20260310-2116-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (previous doc work remains uncommitted; unrelated user changes remain in `src/agents/discovery.py`, `VC_Fundraising0/`, `data/funding.db-shm`, `data/funding.db-wal`)
- Task summary: integrate pasted PRD and system architecture into canonical product and design docs
- Owned files: `docs/product-specs/`, `docs/design-docs/`, `README.md`, `context-kit.json`
- Validation snapshot: pending (`npm run docs:check`, `npm run ctx:check -- --strict`)

### FINISH

- Work ID: `W-20260310-2116-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `docs:check` passed; `ctx:check -- --strict` passed; `coord:check` failed because the branch still contains unrelated user changes outside this claim boundary
- Push/Merge status: not attempted
- Final working tree: dirty (this task updated PRD and architecture docs plus regenerated `docs/generated/*`; unrelated user changes remain in `src/agents/discovery.py`, `VC_Fundraising0/`, `data/funding.db-shm`, `data/funding.db-wal`)

### START

- Work ID: `W-20260313-0326-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (large existing docs/code/data changes remain uncommitted across `docs/`, `src/`, `tests/`, `data/`, `output/`, and `VC_Fundraising0/`; this session resumes the social-discovery search-to-candidate flow on top of that state)
- Task summary: resume social discovery verification and funding candidate promotion flow, validate the current branch state, and complete any remaining search-layer fixes
- Owned files: `src/search/`, `tests/search/`, `docs/design-docs/`, `docs/exec-plans/active/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: `npm run safe:status` passed; `npm run coord:claim -- --work-id "W-20260313-0326-VC_Grants-codex" --agent "codex" --surface "core" ...` passed; `npm run docs:check` and `npm run ctx:check -- --strict` pending

### FINISH

- Work ID: `W-20260313-0326-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `python3 -m pytest -q tests/search tests/test_research_handler.py tests/test_chat_handler.py tests/test_telegram_app.py` passed (141 passed); `npm run docs:refresh` passed; `npm run docs:check` passed; `npm run ctx:check -- --strict` passed; `npm run coord:check` failed due extensive pre-existing branch changes outside this claim boundary
- Push/Merge status: not attempted
- Final working tree: dirty (this session added a fresh checkpoint/claim lifecycle, refreshed latest brief/handoff via `npm run ctx:compact`, updated `docs/AGENT_WATCH_LOG.md`, and refreshed `docs/generated/*`; unrelated large prior branch changes remain uncommitted)

### START

- Work ID: `W-20260313-0331-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (existing branch-wide docs/code/data changes remain; this task improves coordination tooling so already-dirty feature branches can declare an explicit repo-root claim instead of failing path-boundary checks)
- Task summary: add repo-root claim support to coordination tooling and document how to use it for broad resume work on a dirty feature branch
- Owned files: `scripts/dev/`, `docs/MULTI_AGENT_COORDINATION.md`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`npm run coord:check` should pass under a temporary root claim after the tooling change)

### FINISH

- Work ID: `W-20260313-0331-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `node --input-type=module -e "...coordination-lib smoke..."` passed; `npm run coord:claim -- --work-id "W-20260313-0331-VC_Grants-codex" --surface "core" --path "." ...` passed; `npm run coord:check` passed under the repo-root claim; `npm run docs:refresh` passed; `npm run docs:check` passed; `npm run ctx:check -- --strict` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task updated `scripts/dev/coordination-lib.mjs`, `scripts/dev/claim-work.mjs`, `docs/MULTI_AGENT_COORDINATION.md`, `docs/AGENT_WATCH_LOG.md`, refreshed `docs/generated/*`, and updated `.agent-context/*`; broad prior branch changes remain)

### START

- Work ID: `W-20260310-2121-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (canonical docs from prior planning work remain uncommitted; unrelated user changes remain in `src/agents/discovery.py`, `VC_Fundraising0/`, `data/funding.db-shm`, `data/funding.db-wal`)
- Task summary: turn the product and architecture docs into a concrete step-by-step implementation plan for building the system
- Owned files: `docs/exec-plans/active/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`npm run docs:check`, `npm run ctx:check -- --strict`)

### FINISH

- Work ID: `W-20260310-2121-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `docs:check` passed; `ctx:check -- --strict` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task updated the active implementation plan and repaired `.agent-context` resume artifacts; unrelated user changes remain in `src/agents/discovery.py`, `VC_Fundraising0/`, `data/funding.db-shm`, `data/funding.db-wal`)

### START

- Work ID: `W-20260310-2131-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (prior planning/docs changes remain uncommitted; code changes under review exist in `src/agents/discovery.py`, `src/core/config.py`, `src/core/errors.py`, `src/search/`, `tests/search/`; unrelated user files remain in `VC_Fundraising0/`, `data/funding.db-shm`, `data/funding.db-wal`)
- Task summary: review current discovery and search code changes against the Funding Intelligence Agent design and identify bugs, regressions, or coverage gaps
- Owned files: `src/agents/`, `src/core/`, `src/search/`, `tests/search/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (review-only task; no gate run yet for this work item)

### FINISH

- Work ID: `W-20260310-2131-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `python3 -m pytest -q tests/search` passed; import smoke for `src.search` failed on missing `SearchOrchestrator`; manual DDG HTML probe returned bot challenge instead of result markup
- Push/Merge status: not attempted
- Final working tree: dirty (review-only task; findings reported against existing changes, no product code was modified)

### START

- Work ID: `W-20260311-0048-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (prior docs/code changes remain uncommitted; spreadsheet extraction artifacts exist under `output/`; unrelated user files remain in `VC_Fundraising0/`, `data/funding.db-shm`, `data/funding.db-wal`)
- Task summary: resolve the spreadsheet review queue and produce final curated VC, grant, accelerator, and fund CSVs suitable for import/update work
- Owned files: `output/spreadsheet/`, `scripts/resolve_funding_review_queue.py`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`python3 -m py_compile scripts/resolve_funding_review_queue.py`, `npm run docs:check`, `npm run ctx:check -- --strict`)

### FINISH

- Work ID: `W-20260311-0048-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile scripts/resolve_funding_review_queue.py` passed; `npm run docs:refresh` passed; `npm run docs:check` passed; `npm run ctx:check -- --strict` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task added `scripts/resolve_funding_review_queue.py`, generated final curated CSV outputs under `output/spreadsheet/`, and refreshed `docs/generated/*`; unrelated user changes remain in docs/code and under `VC_Fundraising0/`, `data/funding.db-shm`, `data/funding.db-wal`)

### START

- Work ID: `W-20260311-0057-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (prior docs/code changes remain uncommitted; curated spreadsheet outputs exist under `output/`; legacy `data/seed_raw.json` is present and outdated relative to final CSVs)
- Task summary: optimize the final DB seed path by converting curated final CSVs into canonical seed JSON and aligning pipeline category ingestion with the current data model
- Owned files: `scripts/seed_importer.py`, `data/seed_raw.json`, `src/core/pipeline.py`, `tests/test_pipeline.py`, `output/spreadsheet/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`python3 scripts/seed_importer.py ...`, `pytest`, `npm run docs:check`, `npm run ctx:check -- --strict`)

### FINISH

- Work ID: `W-20260311-0057-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `PYTHONPYCACHEPREFIX=tmp/pycache python3 -m py_compile scripts/seed_importer.py src/core/pipeline.py src/db/entity_store.py tests/test_pipeline.py tests/test_seed_importer.py` passed; `python3 -m pytest -q tests/test_pipeline.py tests/test_seed_importer.py` passed; `python3 scripts/seed_importer.py --curated-csv output/spreadsheet/funding_sources_resolved.csv --output data/seed_raw.json` passed; `python3 -m src.core.pipeline --seed` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task replaced the seed importer with curated-CSV ingestion, regenerated `data/seed_raw.json` to 368 records, made seed loading idempotent and category-aware, updated `docs/design-docs/DB_SCHEMA.md`, and loaded the current SQLite DB; unrelated user changes remain across docs/code and under `VC_Fundraising0/`, `data/funding.db-shm`, `data/funding.db-wal`)

### START

- Work ID: `W-20260311-0127-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (curated seed path and prior docs/code changes remain uncommitted; spreadsheet outputs and regenerated `data/seed_raw.json` exist)
- Task summary: define a concrete source-to-entity fill spec for the user-provided funding datasets so the team knows exactly how to populate DB entities from the provided files
- Owned files: `docs/design-docs/`, `docs/exec-plans/active/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`npm run docs:check`, `npm run ctx:check -- --strict`)

### FINISH

- Work ID: `W-20260311-0127-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `npm run docs:refresh` passed; `npm run docs:check` passed; `npm run ctx:check -- --strict` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task added `docs/design-docs/DATA_FILL_SPEC.md`, updated `docs/design-docs/index.md` and `docs/exec-plans/active/MVP_IMPLEMENTATION.md`, refreshed `docs/generated/*`, and repaired runtime brief metadata; unrelated user changes remain elsewhere)

### START

- Work ID: `W-20260310-2224-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (prior doc work and unrelated code changes remain uncommitted; this task will only reshape canonical product/design docs)
- Task summary: refactor the Funding Intelligence Agent requirements into a cleaner v1.1 PRD and split data model, scoring, and Telegram command contracts into dedicated docs
- Owned files: `docs/product-specs/`, `docs/design-docs/`, `docs/generated/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`npm run docs:check`, `npm run ctx:check -- --strict`)

### FINISH

- Work ID: `W-20260310-2224-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `npm run docs:refresh` passed; `npm run docs:check` passed; `npm run ctx:check -- --strict` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task updated canonical product/design docs and refreshed generated docs; unrelated user/code changes remain in the worktree)

### START

- Work ID: `W-20260310-2314-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (prior doc work and unrelated code changes remain uncommitted; this task will compare current implementation against canonical docs and record the gap)
- Task summary: write the spec-code gap into canonical planning docs and audit current implementation against the new Funding Intelligence Agent documents
- Owned files: `docs/exec-plans/active/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`npm run docs:check`, `npm run ctx:check -- --strict`)

### FINISH

- Work ID: `W-20260310-2314-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `npm run docs:refresh` passed; `npm run docs:check` passed; `npm run ctx:check -- --strict` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task added `docs/exec-plans/active/SPEC_CODE_GAP_AUDIT.md`, updated `docs/exec-plans/active/MVP_IMPLEMENTATION.md`, refreshed generated docs, and repaired latest brief/checkpoint artifacts; unrelated user/code changes remain in the worktree)

### START

- Work ID: `W-20260310-2343-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (prior doc and code changes remain uncommitted; this task will analyze external spreadsheets/CSVs and prepare a normalized extract without reverting unrelated work)
- Task summary: inspect the provided VC fundraising spreadsheets and CSVs, extract company/program data, and organize it into a structured output suitable for repo updates
- Owned files: `output/spreadsheet/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`npm run safe:status`)

### FINISH

- Work ID: `W-20260310-2343-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `python3 -m py_compile scripts/funding_source_extract.py` passed; extractor run completed; `npm run docs:refresh` passed; `npm run docs:check` passed; `npm run ctx:check -- --strict` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task added `scripts/funding_source_extract.py` and generated `output/spreadsheet/*`; unrelated user/doc/code changes remain in the worktree)

### START

- Work ID: `W-20260311-0024-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (prior doc/code/data work remains uncommitted; this task only validates extract quality and splits clean list artifacts)
- Task summary: verify whether the extracted VC and funding lists are actually clean enough to use, then split the normalized output into clean VC, grant, accelerator, funding, and review-queue CSVs
- Owned files: `output/spreadsheet/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`npm run docs:check`, `npm run ctx:check -- --strict`)

### FINISH

- Work ID: `W-20260311-0024-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: clean split CSVs generated under `output/spreadsheet/`; `npm run docs:refresh` passed; `npm run docs:check` passed; `npm run ctx:check -- --strict` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task added split list artifacts under `output/spreadsheet/`, refreshed generated docs, and repaired latest brief/checkpoint artifacts; unrelated user/doc/code changes remain in the worktree)

### START

- Work ID: `W-20260311-0132-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (prior doc/code/data changes remain uncommitted; this task only adjusts ranking/design contracts for grant-specific traction signals without reverting unrelated work)
- Task summary: design grant prioritization rules that can account for high TVL and high transaction activity where relevant without penalizing infra and public-goods grants that should not require traction
- Owned files: `docs/design-docs/`, `docs/exec-plans/active/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`npm run docs:check`, `npm run ctx:check -- --strict`)

### FINISH

- Work ID: `W-20260311-0132-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `npm run docs:refresh` passed; `npm run docs:check` passed; `npm run ctx:check -- --strict` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task updated grant-ranking design contracts, refreshed generated docs, and repaired latest brief/handoff artifacts; unrelated user/doc/code changes remain in the worktree)

### START

- Work ID: `W-20260312-0033-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (prior doc/code/data changes remain uncommitted; this task only adds an evaluation benchmark and goal-seeking research loop runner without reverting unrelated work)
- Task summary: implement the first runnable autoresearch evaluation harness with a funding benchmark spec and a research loop runner that can keep iterating until project-level goal metrics are met
- Owned files: `eval/`, `scripts/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`npm run docs:check`, `npm run ctx:check -- --strict`, project checks if touched)

### FINISH

- Work ID: `W-20260312-0033-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation:
  - `python3 -m pytest -q tests/test_research_loop.py` passed
  - `python3 -m py_compile scripts/run_research_loop.py tests/test_research_loop.py` passed
  - `python3 scripts/run_research_loop.py --case hoot_actionable_top10 --max-runs-per-case 1` executed end-to-end, wrote `output/research-evals/20260311-154314.json`, and exited `2` because the goal was correctly unmet in fast-only mode
  - `npm run docs:refresh` passed
  - `npm run docs:check` passed
  - `npm run ctx:check -- --strict` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task added a benchmark spec, a temp-DB research loop runner, targeted tests, updated canonical autoresearch details, and refreshed generated docs; unrelated user/doc/code/data changes remain in the worktree)

### START

- Work ID: `W-20260312-0128-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (prior doc/code/data changes remain uncommitted; this task only improves the benchmark runner and search layer so goal-unmet runs actually adapt search behavior between attempts)
- Task summary: wire the research loop's next actions into real query/search adaptations, including better query batching and policy-driven search hints for subsequent attempts
- Owned files: `scripts/`, `src/search/`, `tests/`, `docs/design-docs/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`npm run docs:check`, `npm run ctx:check -- --strict`, targeted tests)

### FINISH

- Work ID: `W-20260312-0128-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation:
  - `python3 -m pytest -q tests/test_research_loop.py tests/search/test_funding_orchestrator.py` passed
  - `python3 -m py_compile scripts/run_research_loop.py src/search/funding_orchestrator.py tests/test_research_loop.py tests/search/test_funding_orchestrator.py` passed
  - `python3 scripts/run_research_loop.py --case hoot_actionable_top10 --max-runs-per-case 1` executed end-to-end, wrote `output/research-evals/20260311-163501.json`, and exited `2` because the fast-only goal remained unmet
  - partial 2-attempt smoke confirmed attempt 2 switched to `mode=deep` and logged `hint_count=24` before expanded web/social discovery
  - `npm run docs:refresh` passed
  - `npm run docs:check` passed
  - `npm run ctx:check -- --strict` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task made adaptive attempts inject real search hints, fixed seed-round query batching, added pure helper tests, updated canonical autoresearch details, and refreshed generated docs; unrelated user/doc/code/data changes remain in the worktree)

### START

- Work ID: `W-20260312-0142-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (prior doc/code/data/search work remains uncommitted; this task focuses on making the autoresearch loop keep adapting until a benchmark goal is met or a concrete stop reason is produced)
- Task summary: diagnose why the current research loop stalls below the user's target quality, then improve the adaptive loop so search and ranking continue refining toward the desired funding recommendations
- Owned files: `scripts/run_research_loop.py`, `src/search/`, `src/agents/`, `tests/`, `docs/design-docs/AUTORESEARCH_ADOPTION.md`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`npm run docs:check`, `npm run ctx:check -- --strict`, targeted tests)


### START

- Work ID: `W-20260312-0408-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (prior doc/code/data/search work remains uncommitted; this task only adds next-step design so autoresearch converges on the user's target outputs)
- Task summary: design the next improvements so autoresearch moves from discovery-only behavior toward project-aware actionable funding strategy outputs
- Owned files: `docs/design-docs/`, `docs/exec-plans/active/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`npm run docs:check`, `npm run ctx:check -- --strict`)

### FINISH

- Work ID: `W-20260312-0408-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Coordination: continued within the previously active autoresearch claim scope, then released `W-20260312-0142-VC_Grants-codex` after documenting the next-step convergence plan
- Validation:
  - `npm run docs:refresh` passed
  - `npm run docs:check` passed
  - `npm run ctx:check -- --strict` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task added the canonical next-step convergence plan, updated autoresearch adoption guidance, linked the plan from the active MVP execution plan and execution-plan index, refreshed generated docs, and updated latest semantic brief/checkpoint; unrelated user/doc/code/data changes remain in the worktree)

### START

- Work ID: `W-20260312-0415-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (prior doc/code/data/search work remains uncommitted; this task only implements the first output-oriented autoresearch convergence batch)
- Task summary: implement output-oriented benchmark cases, goal routing, ecosystem graph scaffolding, and research scaffolds so autoresearch can optimize toward funding list/map/dossier outputs
- Owned files: `eval/`, `scripts/run_research_loop.py`, `data/curated_ecosystem_graph.json`, `src/search/research_goal_router.py`, `src/research/`, `tests/test_research_loop.py`
- Validation snapshot: pending (`npm run docs:check`, `npm run ctx:check -- --strict`, targeted tests)

### FINISH

- Work ID: `W-20260312-0415-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation:
  - `python3 -m pytest -q tests/test_research_loop.py` passed
  - `python3 -m py_compile scripts/run_research_loop.py src/search/research_goal_router.py src/research/dossier_builder.py src/research/strategy_composer.py tests/test_research_loop.py` passed
  - `npm run docs:refresh` passed
  - `npm run docs:check` passed
  - `npm run ctx:check -- --strict` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task extended the benchmark and research runner with goal-aware routing, added a curated ecosystem graph, introduced initial dossier/strategy scaffolds, refreshed generated docs, and updated latest brief/checkpoint; unrelated user/doc/code/data changes remain in the worktree)

### START

- Work ID: `W-20260312-0437-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (prior doc/code/data/search work remains uncommitted; this task connects the new output-oriented autoresearch scaffolds to user-facing Telegram commands)
- Task summary: add user-facing `/funding_for_project`, `/funding_map`, and `/org` surfaces backed by the new goal-aware research and dossier scaffolds
- Owned files: `src/interface/`, `src/research/`, `src/search/`, `tests/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`pytest`, `npm run docs:check`, `npm run ctx:check -- --strict`)

### START

- Work ID: `W-20260312-0437-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (continuing under the same claim; this batch is limited to wiring the already-built research scaffolds into Telegram-facing command handlers and renderers)
- Task summary: resume `/funding_for_project`, `/funding_map`, and `/org` integration so autoresearch results become directly usable from the Telegram surface
- Owned files: `src/interface/`, `src/research/`, `src/search/`, `tests/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`pytest`, `npm run docs:check`, `npm run ctx:check -- --strict`)

### FINISH

- Work ID: `W-20260312-0437-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation:
  - `python3 -m py_compile src/interface/handlers/research_handler.py src/interface/card_renderer.py src/interface/telegram_app.py src/interface/handlers/profile_handler.py tests/test_card_renderer.py tests/test_research_handler.py` passed
  - `python3 -m pytest -q tests/test_card_renderer.py tests/test_research_handler.py tests/test_research_loop.py` passed
  - `npm run docs:refresh` passed
  - `npm run docs:check` passed
  - `npm run ctx:check -- --strict` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this batch added `/funding_for_project`, `/funding_map`, and `/org` handlers, new funding-map and org-dossier renderers, command registration/start-text updates, renderer and handler tests, refreshed generated docs, and updated command/core canonical docs; unrelated existing changes remain in the worktree)

### START

- Work ID: `W-20260312-0437-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (continuing the same Telegram research-output surface to add natural-language routing on top of the newly active commands)
- Task summary: route structured natural-language project/org requests in `chat_handler` to `/funding_for_project`, `/funding_map`, and `/org` equivalent behavior
- Owned files: `src/interface/handlers/chat_handler.py`, `src/interface/handlers/research_handler.py`, `tests/`, `docs/design-docs/TELEGRAM_UX.md`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`pytest`, `npm run docs:refresh`, `npm run docs:check`, `npm run ctx:check -- --strict`)

### FINISH

- Work ID: `W-20260312-0437-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation:
  - `python3 -m py_compile src/interface/handlers/chat_handler.py src/interface/handlers/research_handler.py src/interface/card_renderer.py tests/test_chat_handler.py tests/test_research_handler.py` passed
  - `python3 -m pytest -q tests/test_chat_handler.py tests/test_research_handler.py tests/test_card_renderer.py tests/test_research_loop.py` passed
  - `npm run docs:refresh` passed
  - `npm run docs:check` passed
  - `npm run ctx:check -- --strict` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this batch added structured natural-language routing for project funding views, funding maps, and org dossiers, updated the natural-language help/LLM intent prompt, added chat-handler parser tests, refreshed generated docs, and aligned Telegram UX docs; unrelated existing changes remain in the worktree)

- START `W-20260312-1521-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `continuous autoresearch adaptation and goal convergence runtime`
- FINISH `W-20260312-1521-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `added funding_program.md control file, continuous autoresearch cycles with carryover actions/results.tsv, updated autoresearch docs, expanded research-loop tests, and validated runtime smoke + repo gates`

- START `W-20260312-1535-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `discover external application endpoints like typeform from VC and ecosystem program pages`
- FINISH `W-20260312-1535-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `improved official-page apply-surface discovery for external form hosts (Typeform/Airtable/Google Forms/HubSpot etc.), added Jina/httpx candidate extraction, updated extractor/discovery prompts, and locked behavior with fetcher/extractor tests`

- START `W-20260312-1556-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `add actual cohort/program content plus official/apply links to research outputs`

- FINISH `W-20260312-1556-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `enriched research outputs with actual cohort/program descriptions and official/apply links via curated registry fallback, updated funding-map/org-dossier rendering, added tests, ran local Monad smoke, and passed repo gates`

- START `W-20260312-1612-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `show structured date lines in research output program and cohort details`

- FINISH `W-20260312-1612-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `added structured deadline text to program/cohort dossier blocks, rendered exact date or rolling state separately from status notes, updated tests/docs, and passed repo gates`

- START `W-20260312-1647-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `suppress stale past dates in research and funding output surfaces`

- FINISH `W-20260312-1647-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `suppressed stale past dates across research and funding outputs by dropping past exact deadlines from registry-derived program details and hiding past deadlines at render time, added tests, and passed repo gates`

- START `W-20260312-1656-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `filter stale exact-deadline opportunities out of search and actionable research outputs`

- FINISH `W-20260312-1656-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `moved stale exact-deadline handling from render-only to search/research eligibility, excluded stale registry rows from enrichment and dossier details, filtered actionable/current cards before funding outputs, added tests and smoke checks, and passed repo gates`

- FINISH `W-20260312-1656-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `extended current-eligibility enforcement to deterministic list/search/ranking/funding surfaces, added shared current-card filter and curated SQL stale-deadline guard, updated Telegram command spec, and passed repo gates`

- START `W-20260312-1745-VC_Grants-codex` | agent: `codex` | surface: `interface` | summary: `run live or end-to-end smoke tests for current-eligibility Telegram outputs`

- FINISH `W-20260312-1745-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `ran Telegram live-auth check plus local end-to-end smoke for list/ranking/research/natural-language outputs, confirmed no stale exact dates in user-facing responses, and verified live chat smoke is blocked only by missing chat updates`

- START `W-20260312-1758-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `tighten funding output quality after bad Telegram ranking result (wrong project label, unknown status rows, inflated fit scores)`
- FINISH `W-20260312-1758-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `tightened user-facing funding quality by requiring verified actionable rows only, adding page-content verification for links, suppressing generic homepage/stale/unknown/low-confidence results, reducing fit-score inflation, neutralizing generic project labels, updating Telegram contracts, validating 109 tests, and confirming the bad saved profile now returns only three verified actionable opportunities`

- START `W-20260312-2043-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `complete the optimal actionable-only funding architecture, align autoresearch to the user goal, and validate the real runtime path`
- FINISH `W-20260312-2043-VC_Grants-codex` | agent: `codex` | surface: `core` | summary: `completed the optimal actionable-only funding architecture by adding shared profile identity normalization/runtime repair, preventing generic auto-register names like Infra/null from being stored, centralizing current+actionable funding views, updating canonical docs, running a broken-profile smoke that repaired to HOOT and returned Nitro as actionable, and passing repo gates (119 tests, docs:refresh, docs:check, ctx:check -- --strict)`
- FINISH `W-20260312-2043-VC_Grants-codex` | agent: `codex` | surface: `interface` | summary: `improved bot setup UX by adding /setup_hoot and /reset_profile confirm, making /start profile-aware, seeding/updating the live Telegram user's HOOT profile, adding profile deletion/store tests, and re-passing docs/context gates`

- START 2026-03-12 23:47:58 KST | work_id=W-20260312-2347-VC_Grants-codex | agent=codex | surface=verification+live-output | summary=Tighten current-window verification and improve actionable funding quality
- START 2026-03-12 23:48:33 KST | work_id=W-20260312-2347-VC_Grants-codex | agent=codex | surface=core | summary=Tighten current-window verification and improve actionable funding quality
- FINISH 2026-03-13 00:01:55 KST | work_id=W-20260312-2347-VC_Grants-codex | agent=codex | surface=core | summary=Tightened current-window verification and apply-surface gating, stopped generic funding/build URLs from implying open, aligned reference apply-url selection, added Telegram single-instance polling guard, refreshed Nitro/Speedrun curated endpoints, validated focused pytest + docs/context gates, and confirmed HOOT fast-path now narrows to Outlier/Nitro/Speedrun/Alliance while live bot polling is still blocked by another external getUpdates caller.
- START 2026-03-13 00:40:00 KST | work_id=W-20260313-0039-VC_Grants-codex | agent=codex | surface=core | summary=Improve overall discovery breadth and targeted funding recall while preserving actionable quality
- FINISH 2026-03-13 00:56:49 KST | work_id=W-20260313-0039-VC_Grants-codex | agent=codex | surface=core | summary=Added watchlist-aware social discovery with seeded VC/L1/L2 account registry, account-targeted FxTwitter-backed query generation, funding/investment signal classification, smarter social apply-surface selection, updated social discovery docs and env/config contract, passed tests/search plus docs/context gates, and confirmed runtime recall is now structurally improved though live social results are currently blocked by Tavily quota on the only configured web search provider.

- START 2026-03-13 01:25:00 KST | work_id=W-20260313-0125-VC_Grants-codex | agent=codex | surface=core | summary=Add official-site social-handle discovery and autonomous X monitoring improvements
- FINISH 2026-03-13 01:33:30 KST | work_id=W-20260313-0125-VC_Grants-codex | agent=codex | surface=core | summary=Added official-site social-handle discovery, root-domain expansion for apply URLs, org-like handle filtering, dynamic watch-account merging, DDG-backed status URL fallback, updated social discovery docs/tests, verified Monad and Alliance runtime handle extraction paths, and re-passed targeted tests plus docs/context gates.

- 2026-03-13 02:14:24 +0900 | START | W-20260313-0214-VC_Grants-codex | codex | Refine VC account discovery and verified social funding signal path

- 2026-03-13 02:24:38 +0900 | FINISH | W-20260313-0214-VC_Grants-codex | codex | Expanded social watch accounts from seed/reference VC lists, persisted discovered handles, filtered research-only investment chatter from raw opportunities, updated social discovery docs/tests, and re-passed search/docs/context gates

- 2026-03-13 02:43:48 +0900 | FINISH | W-20260313-0214-VC_Grants-codex | codex | Added VC registry CSV expansion with region buckets, regional VC query diversity, persisted/discovered social account support, and re-passed search/docs/context gates

- 2026-03-13 04:56:30 +0900 | START | W-20260313-0454-VC_Grants-codex | codex | Add explicit country and region specific VC monitoring rounds to social discovery
- 2026-03-13 05:06:45 +0900 | FINISH | W-20260313-0454-VC_Grants-codex | codex | Implemented explicit social monitoring rounds for profile-priority, region-specific VC buckets, and ecosystem operators; executed X search per round with round-level metrics and raw opportunity provenance; updated social discovery docs/tests; validated 122 search tests plus docs/context gates
- 2026-03-13 05:43:05 +0900 | START | W-20260313-0531-VC_Grants-codex | codex | Persist social monitoring round hits and derive actionable alert candidates from verified social funding discoveries
- 2026-03-13 05:50:35 +0900 | FINISH | W-20260313-0531-VC_Grants-codex | codex | Added social_monitoring_events persistence and alert-candidate query path, linked social raw ingest to provenance rows, synced verification status back into social events, exposed verified actionable social alert candidates through MonitoringAgent output, updated social/operations docs, and passed focused tests plus docs/context gates
- 2026-03-13 07:30:50 +0900 | START | W-20260313-0730-VC_Grants-codex | codex | Connect verified social alert candidates to Telegram outbound delivery
- 2026-03-13 10:12:08 +0900 | FINISH | W-20260313-0730-VC_Grants-codex | codex | Added Telegram social alert background dispatch loop, recipient discovery from company profiles, deterministic social alert rendering with official/apply/social evidence, current-deadline gating in social alert queries, updated UX/operations/env docs, added focused dispatcher/entity/renderer tests, and passed pytest plus docs/context gates

### START

- Work ID: `W-20260314-0006-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (large existing docs/code/data changes remain; this task changes chat intake behavior so pasted funding URLs/leads trigger discovery-style handling instead of stopping at DB-backed views)
- Task summary: automatically treat user-supplied funding links and lead dumps as discovery/verification input in the Telegram chat flow
- Owned files: `src/interface/handlers/`, `src/search/`, `src/research/`, `tests/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (focused chat/funding tests plus docs/context gates)

### FINISH

- Work ID: `W-20260314-0006-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `python3 -m py_compile src/core/pipeline.py src/interface/handlers/search_handler.py src/interface/handlers/chat_handler.py tests/test_pipeline.py tests/test_chat_handler.py` passed; `./.venv/bin/pip install -r requirements.txt` completed for missing local test deps; `./.venv/bin/python -m pytest -q tests/test_chat_handler.py tests/test_pipeline.py` passed (20 passed); `npm run docs:refresh` passed; `npm run docs:check` passed; `npm run ctx:check -- --strict` passed; `npm run coord:check` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task added direct-source lead intake for pasted funding URLs in chat, updated pipeline result metadata, added chat/pipeline tests, updated Telegram UX docs, refreshed `docs/generated/*`, and updated `.agent-context/*`; broad prior branch changes remain)

### START

- Work ID: `W-20260314-2054-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (existing broad docs/code/data changes remain; this task improves context operations by adding a single latest-status runtime surface on top of checkpoint/brief/handoff)
- Task summary: add one human-readable status artifact that captures current objective, next step, and artifact pointers so resume does not depend on scattered files
- Owned files: `scripts/dev/`, `package.json`, `README.md`, `docs/AGENT_CONTEXT_PROTOCOL.md`, `CLAUDE.md`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`ctx:compact`, `ctx:restore -- --mode status`, docs/context/coord gates)

### FINISH

- Work ID: `W-20260314-2054-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `npm run ctx:compact -- --work-id "W-20260314-2054-VC_Grants-codex"` passed; `npm run ctx:status` passed; `npm run ctx:restore -- --mode list` passed; `npm run docs:refresh` passed; `npm run docs:check` passed; `npm run ctx:check -- --strict` passed; `npm run coord:check` passed; `npm run safe:status` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task added a first-class `.agent-context/status/` artifact, exposed `ctx:status`, updated restore/compact/package/doc routing, refreshed generated docs, and updated `.agent-context/*`; broad prior branch changes remain)

### START

- Work ID: `W-20260314-2102-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (existing broad docs/code/data changes remain; this task refactors the shared discovery orchestration boundary used by chat and search flows)
- Task summary: extract a shared discovery runtime so handlers stop depending on each other and duplicate pipeline/status orchestration less
- Owned files: `src/interface/`, `tests/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (focused discovery/chat/search tests plus docs/context/coord gates)

### FINISH

- Work ID: `W-20260314-2102-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `python3 -m py_compile src/interface/discovery_runtime.py src/interface/handlers/search_handler.py src/interface/handlers/chat_handler.py tests/test_discovery_runtime.py tests/test_search_handler.py` passed; `./.venv/bin/python -m pytest -q tests/test_discovery_runtime.py tests/test_search_handler.py tests/test_chat_handler.py tests/test_pipeline.py tests/test_telegram_app.py` passed (28 passed); `npm run docs:refresh` passed; `npm run docs:check` passed; `npm run ctx:check -- --strict` passed; `npm run coord:check` passed; `npm run ctx:compact -- --work-id "W-20260314-2102-VC_Grants-codex"` passed; `npm run ctx:status` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task introduced `src/interface/discovery_runtime.py`, slimmed `/search` into a thin wrapper, removed handler-to-handler coupling from chat lead intake, added focused runtime/search tests, refreshed generated docs, and updated `.agent-context/*`; broad prior branch changes remain)

### START

- Work ID: `W-20260314-2209-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (existing broad docs/code/data changes remain; this task extracts pipeline ingestion/parsing into a dedicated component for the second refactor pass)
- Task summary: split `FundingPipeline` so ingest/parsing lives behind a dedicated ingestor while pipeline keeps orchestration responsibility
- Owned files: `src/core/`, `src/search/`, `tests/`, `docs/product-specs/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (focused pipeline/ingestor tests plus docs/context/coord gates)

### FINISH

- Work ID: `W-20260314-2209-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `python3 -m py_compile src/core/opportunity_ingestor.py src/core/pipeline.py src/search/funding_orchestrator.py src/search/engines/reference_engine.py tests/test_opportunity_ingestor.py tests/test_pipeline.py` passed; `./.venv/bin/python -m pytest -q tests/test_opportunity_ingestor.py tests/test_pipeline.py tests/test_discovery_runtime.py tests/test_search_handler.py tests/test_chat_handler.py` passed (28 passed); `npm run docs:refresh` passed; `npm run safe:status` passed; `npm run docs:check` passed; `npm run ctx:check -- --strict` passed; `npm run coord:check` passed; `npm run ctx:compact -- --work-id "W-20260314-2209-VC_Grants-codex"` passed; `npm run ctx:status` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task introduced `src/core/opportunity_ingestor.py`, reduced `src/core/pipeline.py` to clearer discover/ingest/verify/match orchestration, moved funding orchestrator to the public ingest API, updated pipeline spec/reference docs, refreshed generated docs, and updated `.agent-context/*`; broad prior branch changes remain)

### START

- Work ID: `W-20260314-2221-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (existing broad docs/code/data changes remain; this task extracts shared verification execution so pipeline and funding orchestrator stop duplicating it)
- Task summary: add a shared verifier boundary for source collection, verification agent execution, and batch verification policy
- Owned files: `src/core/`, `src/search/funding_orchestrator.py`, `tests/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (focused verifier/pipeline/orchestrator tests plus docs/context/coord gates)

### FINISH

- Work ID: `W-20260314-2221-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `python3 -m py_compile src/core/opportunity_verifier.py src/core/pipeline.py src/search/funding_orchestrator.py tests/test_opportunity_verifier.py tests/search/test_funding_orchestrator.py tests/test_pipeline.py` passed; `./.venv/bin/python -m pytest -q tests/test_opportunity_verifier.py tests/search/test_funding_orchestrator.py tests/test_pipeline.py tests/test_opportunity_ingestor.py tests/test_discovery_runtime.py tests/test_search_handler.py tests/test_chat_handler.py` passed (36 passed); `npm run docs:refresh` passed; `npm run docs:check` passed; `npm run ctx:check -- --strict` passed; `npm run coord:check` passed; `npm run ctx:compact -- --work-id "W-20260314-2221-VC_Grants-codex"` passed; `npm run ctx:status` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task introduced `src/core/opportunity_verifier.py`, routed pipeline and funding orchestrator through one verification execution path, added focused verifier/orchestrator tests, updated pipeline spec wording, refreshed generated docs, and updated `.agent-context/*`; broad prior branch changes remain)

### START

- Work ID: `W-20260315-0255-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (existing broad docs/code/data changes remain; this task extracts shared matching orchestration and rankable filtering from pipeline/orchestrator callsites)
- Task summary: add a shared matcher boundary so pipeline and funding orchestrator stop duplicating rankable filtering and batch matching policy
- Owned files: `src/core/`, `src/search/funding_orchestrator.py`, `tests/`, `docs/product-specs/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (focused matcher/pipeline/orchestrator tests plus docs/context/coord gates)

### FINISH

- Work ID: `W-20260315-0255-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `python3 -m py_compile src/core/opportunity_matcher.py src/core/pipeline.py src/search/funding_orchestrator.py tests/test_opportunity_matcher.py tests/test_pipeline.py tests/search/test_funding_orchestrator.py` passed; `./.venv/bin/python -m pytest -q tests/test_opportunity_matcher.py tests/test_pipeline.py tests/search/test_funding_orchestrator.py tests/test_opportunity_verifier.py tests/test_opportunity_ingestor.py tests/test_discovery_runtime.py tests/test_search_handler.py tests/test_chat_handler.py` passed (40 passed); `npm run docs:refresh` passed; `npm run docs:check` passed; `npm run ctx:checkpoint -- --work-id "W-20260315-0255-VC_Grants-codex" ...` passed; `npm run ctx:compact -- --work-id "W-20260315-0255-VC_Grants-codex"` passed; `npm run ctx:status` passed; `npm run ctx:check -- --strict` passed; `npm run coord:check` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task introduced `src/core/opportunity_matcher.py`, routed pipeline and funding orchestrator through one matching execution path, centralized rankable filtering and ranked output assembly, added focused matcher/pipeline/orchestrator tests, refreshed generated docs, and updated `.agent-context/*`; broad prior branch changes remain)

### START

- Work ID: `W-20260315-0308-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (existing broad docs/code/data changes remain; this task redesigns funding autoresearch around structured round reflection and promoted policy artifacts)
- Task summary: adapt `karpathy/autoresearch` + `nanochat` round-result promotion ideas into the funding research loop so winning round signals persist as reusable search policy seeds
- Owned files: `scripts/run_research_loop.py`, `src/search/`, `tests/`, `funding_program.md`, `docs/design-docs/`, `docs/exec-plans/active/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (focused research-loop tests plus docs/context/coord gates)

### FINISH

- Work ID: `W-20260315-0308-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `python3 -m py_compile scripts/run_research_loop.py src/search/research_reflection.py tests/test_research_loop.py tests/search/test_research_reflection.py` passed; `./.venv/bin/python -m pytest -q tests/test_research_loop.py tests/test_research_handler.py tests/test_search_handler.py tests/test_discovery_runtime.py tests/search/test_funding_orchestrator.py tests/search/test_research_reflection.py` passed (42 passed); `npm run docs:refresh` passed; `node scripts/dev/refresh-context-retrieval.mjs` passed; `npm run docs:check` passed; `npm run ctx:checkpoint -- --work-id "W-20260315-0308-VC_Grants-codex" ...` passed; `npm run ctx:compact -- --work-id "W-20260315-0308-VC_Grants-codex"` passed; `npm run ctx:status` passed; `npm run ctx:check -- --strict` passed; `npm run coord:check` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task introduced `src/search/research_reflection.py`, upgraded the funding autoresearch runner from action-only carryover to structured reflection/promotion, added curated reflection config/data, updated autoresearch docs/program config, refreshed generated docs, and updated `.agent-context/*`; broad prior branch changes remain)

### START

- Work ID: `W-20260315-0329-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Base: `main`
- Working tree: dirty (broad pre-existing branch changes remain; this task threads promoted autoresearch reflection into user-facing funding/search runtime flows)
- Task summary: apply curated reflection seeds automatically in runtime funding/search paths so benchmark-learned search hints and bootstrap terms affect live user-facing outputs
- Owned files: `src/research/`, `src/interface/`, `tests/`, `docs/`, `docs/AGENT_WATCH_LOG.md`
- Validation snapshot: pending (`pytest` for research/search runtime plus docs/context/coord gates)

### FINISH

- Work ID: `W-20260315-0329-VC_Grants-codex`
- Branch: `codex/project-intent-summary`
- Commit: none
- Validation: `python3 -m py_compile src/research/runtime_reflection.py src/research/actionable_funding_service.py src/interface/handlers/research_handler.py src/interface/handlers/search_handler.py src/interface/discovery_runtime.py src/search/engines/reference_engine.py src/search/funding_orchestrator.py src/agents/discovery.py src/core/pipeline.py src/core/types.py tests/test_runtime_reflection.py tests/search/test_reference_engine.py tests/test_discovery_agent.py tests/test_actionable_funding_service.py tests/test_search_handler.py tests/test_discovery_runtime.py` passed; `./.venv/bin/python -m pytest -q tests/test_runtime_reflection.py tests/search/test_reference_engine.py tests/test_discovery_agent.py tests/test_actionable_funding_service.py tests/test_search_handler.py tests/test_discovery_runtime.py tests/test_research_handler.py tests/search/test_funding_orchestrator.py tests/test_pipeline.py tests/test_chat_handler.py tests/test_telegram_app.py tests/test_research_loop.py tests/search/test_research_reflection.py` passed (`70 passed`); `npm run docs:refresh` passed; `npm run docs:check` passed; `npm run ctx:compact -- --work-id "W-20260315-0329-VC_Grants-codex"` passed; `npm run ctx:check -- --strict` passed; `npm run coord:check` passed; `npm run safe:status` passed
- Push/Merge status: not attempted
- Final working tree: dirty (this task added runtime reflection resolution for funding/search flows, extended discovery with hint queries, biased fast/reference mode with reflection priority terms, added focused runtime tests, refreshed generated docs, and updated `.agent-context/*`; broad prior branch changes remain)
