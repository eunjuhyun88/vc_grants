# Funding Intelligence Agent — Spec-Code Gap Audit

## Purpose

이 문서는 현재 구현과 canonical product/design docs 사이의 차이를 고정하고, 무엇을 어떤 순서로 맞출지 정리하는 active audit다.

Authority는 다음 문서다.

- `docs/product-specs/core.md`
- `docs/product-specs/PRD.md`
- `docs/design-docs/ARCHITECTURE.md`
- `docs/design-docs/ENTITY_MODEL.md`
- `docs/design-docs/PRIORITY_ALGORITHM.md`
- `docs/design-docs/TELEGRAM_COMMAND_SPEC.md`
- `docs/design-docs/TELEGRAM_UX.md`
- `docs/design-docs/OPERATIONS_MODEL.md`

Snapshot:

- Date: `2026-03-11`
- Branch: `codex/project-intent-summary`
- Intent: 문서를 현재 구현에 맞춰 낮추지 않고, 구현을 canonical contract로 끌어올린다

## Convergence Summary

| Surface | Canonical expectation | Current implementation | Status |
|---|---|---|---|
| Telegram profile flow | `/start`, `/register`, `/profile` stable | 구현됨 | mostly aligned |
| Deterministic list commands | `/grants`, `/cohorts`, `/funds`, `/all` with curated bucket semantics | 구현됨, but `/funds` meaning and copy drift 존재 | partial |
| Ranking surface | `/ranking` and intent-aware ranking aligned to scoring spec | 5-factor skeleton은 구현됐지만 fit/actionability decomposition과 grant traction 규칙이 아직 부족 | partial |
| Data/state vocabulary | recruiting status, verification state, eligibility, display bucket 분리 | legacy enum and field mixing 존재 | low alignment |
| Discovery/search | search stack connected, candidate ingest stable, anti-spam/filtering 적용 | 일부 구현됨, but new stack 미연결 및 runtime defects 존재 | partial |
| Verification | evidence-backed verification lifecycle + output gate | tier-based confidence는 있음, lifecycle/eligibility는 부족 | partial |
| Monitoring | status-based cadence + change events + suppression | 초기 구현 존재, legacy status mapping 남아 있음 | early partial |

## Gap Matrix

| Area | Canonical contract | Current implementation | Severity | Required change |
|---|---|---|---|---|
| Ranking formula | `priority = fit 0.35 + urgency 0.25 + actionability 0.20 + expected_value 0.10 + confidence 0.10` | `src/agents/matching.py` has the 5-factor skeleton, but sub-factor decomposition is still incomplete | high | Keep 5-factor skeleton and refine fit/actionability with canonical sub-signals |
| Ranking intents | `default`, `urgent`, `best_fit`, `biggest_check`, `ready_now` | handler now accepts canonical public names, but legacy alias policy/help surface is not fully settled | medium | Keep canonical public names and decide whether old names remain aliases or are removed |
| Fit score | sector + stage + thesis + ecosystem + geography | simple tag overlap only | high | Split fit into sub-factors and persist component scores |
| Grant traction sensitivity | traction-sensitive grants should consider TVL / tx / active wallets, while infra/public-goods grants should stay neutral | no program trait or project traction snapshot is used in ranking | high | Add program traits / selection signals and fold traction into `requirement_fit` only when relevant |
| Confidence score | source tier + source agreement + fact completeness + freshness | composite function exists, but evidence agreement/freshness inputs are still shallow and tied to current opportunity fields | medium | Preserve composite model and enrich the evidence inputs from verification/observation data |
| Urgency table | D4-7 `0.85`, D8-14 `0.70`, D15-30 `0.50`, rolling `0.35`, upcoming explicit | old values `0.8 / 0.6 / 0.4 / 0.3`, no proper upcoming handling | medium | Replace table and add tests for all status/date cases |
| Opportunity status model | `deadline` is a field, not a status | `OpportunityStatus.DEADLINE` exists in `src/core/types.py` | high | Deprecate legacy enum value and map old rows to `open` + `deadline_at` |
| Verification lifecycle | `candidate / pending_verification / review_required / verified / rejected / stale` | `OutputStatus = verified / pending / rejected` only | medium | Add richer internal state model without breaking outbound curated queries |
| Eligibility | project-level eligibility separate from recruiting status | no explicit eligibility axis | high | Add eligibility state/checks in verification and query layers |
| Category vs display bucket | `program_type`, `display_bucket`, `recruiting_status` separate | `/funds` handler currently means accelerator list | high | Define bucket mapping and align handler copy/query semantics |
| Telegram commands | v1 deterministic set plus documented strategy/detail commands in later phases | `/search` exists but is undocumented; `/urgent`, `/changes`, detail commands absent | medium | Decide which are v1, operator-only, or future; document and gate accordingly |
| Monitoring cadence | cadence by recruiting status and deadline freshness | `src/agents/monitoring.py` still contains legacy `"deadline"` status interval | medium | Normalize cadence against canonical status model |
| Search orchestration | discovery/search stack reachable from runtime | `search_provider=multi` exists, but discovery still uses legacy DDG + Tavily path | high | Wire configured provider into discovery pipeline |

## Runtime Defects Found During Audit

These are not just spec drift. They are implementation issues that block convergence.

1. `src/search/__init__.py` exports `SearchOrchestrator`, but no `src/search/orchestrator.py` exists.
2. `src/agents/discovery.py` does not actually consume the new `src/search/` stack even when config defaults to `search_provider=multi`.
3. DuckDuckGo HTML scraping path is brittle and can return bot-challenge HTML instead of results.
4. Official-domain detection currently relies on substring matching, which can over-trust phishing-style domains.
5. Search fetch/apply-link extraction currently drops relative URLs, which can hide legitimate official application endpoints.

## Recommended Migration Order

### Wave 1 — Public Contract Alignment

Goal: 사용자에게 보이는 계약부터 문서와 맞춘다.

- align `/funds` semantics and copy with canonical bucket model
- align `/ranking` intent names with alias bridge for old names
- decide `/search` status: operator-only or remove from Telegram surface
- update help text and handler validation strings

### Wave 2 — State Model Bridge

Goal: enum/field 혼선을 제거한다.

- deprecate `OpportunityStatus.DEADLINE`
- split recruiting status from verification/output state
- introduce eligibility as a distinct internal dimension
- expand type vocabulary without breaking existing rows

### Wave 3 — Ranking Skeleton Migration

Goal: scoring contract를 먼저 구조적으로 맞춘다.

- add `actionability_score` to types, storage, and output DTOs
- move to 5-factor weights
- support new intent presets
- keep deterministic `why_fit` / `next_action` generation

### Wave 4 — Score Decomposition

Goal: “왜 이 순위인가”를 구성 요소별로 설명 가능하게 만든다.

- split fit into sector/stage/thesis/ecosystem/geography
- split confidence into tier/agreement/completeness/freshness
- replace urgency table with canonical values
- add component-level tests

### Wave 5 — Verification And Eligibility Hardening

Goal: output quality를 문서 수준으로 끌어올린다.

- introduce candidate/review/stale states
- add project eligibility checks
- keep social-only and low-confidence items out of outbound surfaces
- persist richer evidence for review and monitoring

### Wave 6 — Discovery/Monitoring Hardening

Goal: 지금 있는 수집/추적 경로를 실제 운영 가능한 수준으로 만든다.

- connect `src/search/` runtime path end-to-end
- remove brittle DDG-only assumptions
- harden domain trust and relative apply-link extraction
- normalize monitoring cadence and change events to canonical status terms

## What To Fix Now

These are the next improvements that should happen before broader feature expansion.

1. ranking intent names and `/funds` bucket semantics
2. `DEADLINE` status deprecation bridge
3. grant-specific traction sensitivity for ranking and profile data
4. discovery/search wiring defects that currently make the new search stack unreachable

## What Can Wait

These should happen after the public contract and ranking skeleton are stable.

1. full detail commands (`/org`, `/program`, `/opportunity`, `/fit`)
2. daily brief expansion
3. dashboard/API surfaces
4. richer operator review tooling
