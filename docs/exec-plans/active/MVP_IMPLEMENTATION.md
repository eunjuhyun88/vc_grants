# Funding Intelligence Agent — V1 Implementation Plan

## Objective

Telegram 기반 `Funding Intelligence Agent`를 실제로 동작하는 V1으로 만든다.

V1의 의미는 다음과 같다.

- 사용자가 Telegram DM에서 profile을 등록할 수 있다
- 시스템이 funding opportunity를 수집하고 검증해서 DB에 저장할 수 있다
- 사용자가 `/grants`, `/cohorts`, `/funds`, `/all`, `/ranking`으로 verified opportunity를 조회할 수 있다
- 시스템이 중요한 신규 기회와 핵심 변경을 Telegram으로 알릴 수 있다

## Build Principles

1. 새로 다시 만들지 않고, 이미 있는 Python/SQLite/Telegram 구현을 기준으로 점진적으로 완성한다.
2. deterministic surface를 먼저 완성하고, reasoned surface는 나중에 올린다.
3. fact quality가 ranking sophistication보다 먼저다.
4. push alert는 discovery보다 늦게 붙여도 되지만, eligibility gate 없이는 절대 붙이지 않는다.
5. 각 phase는 “데모 가능한 상태”로 끝나야 한다.

## Out Of Scope For V1

- 웹 대시보드
- 자유 대화형 assistant
- 자동 지원서 작성/제출
- investor outreach automation
- team collaboration / RBAC

## Current Starting Point

이미 repo에 존재:

- `src/db/schema.sql`
- `src/db/entity_store.py`
- `src/agents/discovery.py`
- `src/agents/verification.py`
- `src/agents/matching.py`
- `src/core/pipeline.py`
- `src/interface/telegram_app.py`
- `src/interface/handlers/*`
- 기본 테스트 일부

즉, 이 계획은 greenfield가 아니라 “기존 초안을 V1로 고정하고 하드닝하는 계획”이다.

## Spec-Code Gap Snapshot

Canonical audit: `docs/exec-plans/active/SPEC_CODE_GAP_AUDIT.md`

Search auto-improvement track: `docs/design-docs/AUTORESEARCH_ADOPTION.md`

Next-step convergence plan: `docs/exec-plans/active/AUTORESEARCH_GOAL_CONVERGENCE.md`

현재 가장 큰 차이는 “문서는 Funding Intelligence Agent v1.1 계약까지 올라갔지만, 구현은 초기 MVP vocabulary와 ranking model에 머물러 있다”는 점이다.

Highest-risk gaps:

1. ranking은 5-factor skeleton까지 올라왔지만, grant-specific traction requirement가 아직 actionability/fit에 반영되지 않는다
2. `deadline`이 여전히 status enum에 남아 있어 canonical state model과 충돌한다
3. verification/output/eligibility가 한 축으로 섞여 있다
4. `/funds` 의미와 ranking help/copy surface가 Telegram contract와 아직 완전히 맞지 않는다
5. 새 search stack이 runtime discovery path에 아직 연결되지 않았다
6. discovery는 돌아가지만 goal metric이 미달일 때 다음 탐색 행동을 자동 선택하는 loop가 아직 없다

Migration principle:

- 문서를 구현에 맞춰 낮추지 않는다
- public contract부터 맞춘다
- state bridge를 먼저 넣고, scoring sophistication은 그 다음에 올린다
- search는 `goal met -> stop`, `goal unmet -> continue` 구조로 올린다
- autoresearch는 discovery quality만이 아니라 `actionable funding list`, `funding map`, `dossier`를 채우는 방향으로 수렴해야 한다

## Delivery Sequence

| Phase | Goal | Why now | Status |
|---|---|---|---|
| 0 | Canonical freeze and build baseline | 구현 중 판단 흔들림 방지 | planned |
| 1 | Persistence and type hardening | 모든 이후 단계의 data contract 기반 | partial |
| 2 | Telegram profile and deterministic query surface | 사용자가 실제로 만질 수 있는 첫 value | partial |
| 3 | Discovery ingestion quality | opportunity 공급원 확보 | partial |
| 4 | Verification and eligibility enforcement | 노이즈 제거, outbound trust 확보 | partial |
| 5 | Matching and ranking quality | personalized recommendation 핵심 | partial |
| 6 | Pipeline orchestration and operator loop | 수동/반자동 실행 가능 상태 확보 | partial |
| 7 | Monitoring and alert dispatch | 지속성 있는 agent behavior 완성 | planned |
| 8 | Daily brief and feedback loop | retention과 triage quality 개선 | planned |
| 9 | Deployment and production readiness | 실제 운영 전환 | planned |

## Phase 0 — Canonical Freeze And Build Baseline

### Goal

구현 전에 흔들리면 안 되는 V1 경계를 고정한다.

### Build Tasks

1. `docs/product-specs/core.md`, `docs/product-specs/PRD.md`, `docs/design-docs/ARCHITECTURE.md`, `docs/design-docs/OPERATIONS_MODEL.md`를 V1 authority로 사용한다.
2. README / context-kit / design index의 surface 설명이 Telegram-first 기준으로 정렬되어 있는지 확인한다.
3. operator 기준 실행 명령을 하나로 정리한다.

### Deliverables

- canonical product docs aligned
- active execution plan aligned
- generated docs refreshed

### Exit Criteria

- 구현자가 “무엇이 V1이고 무엇이 아닌지” 문서만 보고 판단할 수 있다
- `docs:check`와 `ctx:check -- --strict`를 통과한다

## Phase 1 — Persistence And Type Hardening

### Goal

DB schema와 shared types를 V1 contract로 안정화한다.

### Build Tasks

1. `src/core/types.py`에서 recruiting status, verification state, eligibility, display bucket vocabulary를 분리한다.
2. `OpportunityStatus.DEADLINE`을 deprecated bridge로 처리하고, `deadline_at` 중심 해석으로 전환한다.
3. `src/db/schema.sql`에서 V1 필수 테이블과 필드를 lock하고, score component와 traction snapshot 확장 여지를 남긴다.
4. company/project profile에 optional traction snapshot (`tvl_usd`, `transactions_30d`, `active_wallets_30d`, `integrations_count`, `traction_stage`) 입력 경로를 설계한다.
5. `src/db/entity_store.py`의 CRUD와 curated read path를 idempotent하게 정리한다.
6. profile, opportunities, observations, fit_recommendations, change_events path를 테스트로 고정한다.
7. user-provided spreadsheet/CSV seed data는 `docs/design-docs/DATA_FILL_SPEC.md`를 따라 entity별로 채운다.

### Files

- `src/core/types.py`
- `src/db/schema.sql`
- `src/db/entity_store.py`
- `src/db/queries.py`
- `tests/test_entity_store.py`

### Design Decisions

- `Organization -> Program -> Opportunity` hierarchy 유지
- facts와 reasoning은 저장 위치를 분리
- apply URL이 없으면 outbound surface에서 제외

### Exit Criteria

- 임시 DB에서 schema init이 안정적으로 된다
- CRUD + curated view 테스트가 통과한다
- sample profile 1개와 verified opportunity 1개를 코드만으로 seed할 수 있다

## Phase 2 — Telegram Profile And Deterministic Query Surface

### Goal

사용자가 Telegram에서 들어와 profile을 만들고 verified list를 읽을 수 있게 한다.

### Build Tasks

1. `/start`, `/register`, `/profile` flow를 안정화한다.
2. `/grants`, `/cohorts`, `/funds`, `/all`이 curated view만 사용하도록 고정한다.
3. `/funds`의 의미를 canonical display bucket과 맞추고, 잘못된 accelerator copy를 제거한다.
4. `/ranking` intent 이름을 canonical contract로 맞추고, legacy alias를 한시적으로 유지한다.
5. undocumented Telegram commands의 상태를 정한다: v1, operator-only, or future.
6. `/funding`, `/funding_for_project`, `/funding_map`가 shared actionable funding service를 타게 만들어 handler drift를 없앤다.
7. 자연어 auto-register는 generic project/company label을 저장하지 않게 하고, known project signature가 있으면 runtime profile repair를 거친다.
7. empty state와 error state를 canonical copy와 맞춘다.
8. MarkdownV2 escaping, card layout, max item limits를 테스트한다.

### Files

- `src/interface/telegram_app.py`
- `src/interface/handlers/profile_handler.py`
- `src/interface/handlers/list_handler.py`
- `src/interface/card_renderer.py`
- `tests/test_card_renderer.py`

### Exit Criteria

- Telegram bot local run에서 register -> profile -> list path가 동작한다
- list path에서 LLM/network search 호출이 없다
- DB 0건 / eligibility 0건 / DB 오류 응답이 deterministic하다

## Phase 3 — Discovery Ingestion Quality

### Goal

raw internet data를 usable candidate로 가져오는 경로를 안정화한다.

### Build Tasks

1. category별 query template를 유지하되 source filtering 기준을 명확히 한다.
2. fetch 단계에서 page text와 candidate links를 안정적으로 추출한다.
3. parse result를 `Organization / Program / Opportunity` ingest input 형태로 정규화한다.
4. 중복 URL과 obvious spam source를 early filter 한다.
5. raw candidate를 수동 검토 가능한 로그로 남긴다.

### Files

- `src/agents/discovery.py`
- `src/core/pipeline.py`
- new tests around discovery parsing / ingestion

### Exit Criteria

- seed query 3개에서 candidate opportunity를 반복 가능하게 추출한다
- ingest 시 duplicate org/program이 폭발적으로 늘지 않는다
- discovery failure가 pipeline 전체를 깨지 않는다

## Phase 4 — Verification And Eligibility Enforcement

### Goal

outbound trust를 만드는 단계다. verified quality가 여기서 결정된다.

### Build Tasks

1. source tier 판정 규칙을 정리하고 테스트한다.
2. verification lifecycle을 `candidate / pending_verification / review_required / verified / rejected / stale` 방향으로 확장하되 outbound gating과 분리한다.
3. evidence 저장과 opportunity update를 idempotent하게 만든다.
4. eligibility filter를 query layer와 output layer 양쪽에서 강제한다.
5. `deadline`, `apply_url`, `status` 추측 생성 금지를 테스트로 고정한다.
6. social-only source와 low-confidence source는 verified output으로 승격되지 않게 고정한다.
7. external form URL 단독으로는 verified/actionable 승격이 되지 않게 하고, verified endpoint set을 기회마다 재동기화한다.
8. generic funding/build URL만으로 `open`을 추정하지 않고, explicit current-window evidence가 있을 때만 actionable status로 승격한다.
9. Telegram polling runtime에는 single-instance guard를 넣어 duplicate bot process로 인한 live drift와 polling conflict를 막는다.

### Files

- `src/agents/verification.py`
- `src/db/queries.py`
- `src/interface/handlers/list_handler.py`
- `tests/test_pipeline.py`
- new verification tests

### Exit Criteria

- tier 1-2 source 없이 verified로 나가지 않는다
- invalid apply URL / closed status / low confidence가 outbound list에서 제거된다
- active endpoint가 없는 기회는 outbound list와 ranking에서 제거된다
- verification 후 observation records가 남는다

## Phase 5 — Matching And Ranking Quality

### Goal

기회 목록이 아니라 “내게 중요한 순서”를 보여준다.

### Build Tasks

1. 5-factor skeleton을 먼저 구현한다: fit, urgency, actionability, expected value, confidence.
2. profile tags + project tags + org/program tags의 fit 계산을 sector/stage/thesis/ecosystem/geography로 분해한다.
3. traction-sensitive grant에서만 TVL / transactions / active wallets / integrations를 `requirement_fit`에 반영하고, infra/public-goods/prelaunch grant는 neutral 처리한다.
4. core grants/programs에 `program_traits` / `selection_signals` backfill 경로를 설계한다.
5. confidence를 tier/agreement/completeness/freshness 조합으로 바꾼다.
6. urgency table을 canonical 값으로 교체하고 upcoming handling을 넣는다.
7. `/ranking [intent]` path를 canonical intent names로 정렬한다.
8. why_fit / next_action을 V1에서는 template-driven 또는 deterministic 문구로 유지한다.
9. ranking 결과 persistence 전략을 정한다.

### Files

- `src/agents/matching.py`
- `src/interface/handlers/ranking_handler.py`
- `tests/test_matching.py`

### Exit Criteria

- 동일 입력에 대해 ranking 결과가 반복 가능하다
- intent별 가중치 차이가 실제 결과 차이로 드러난다
- traction-sensitive grant와 public-goods grant가 같은 프로젝트 metric에 대해 서로 다른 ranking behavior를 보인다
- profile이 없는 사용자는 deterministic error를 받는다

## Phase 6 — Pipeline Orchestration And Operator Loop

### Goal

개발자/운영자가 V1을 반복 실행할 수 있게 한다.

### Build Tasks

1. `src/core/pipeline.py`를 discovery -> ingest -> verification -> matching orchestration 진입점으로 고정한다.
2. seed query / category / profile 옵션을 CLI로 정리한다.
3. partial failure reporting을 사람이 읽기 쉬운 결과로 남긴다.
4. sample runbook을 문서화한다.
5. E2E smoke test를 만든다.

### Files

- `src/core/pipeline.py`
- `tests/test_pipeline.py`
- optional runbook docs

### Exit Criteria

- `python -m src.core.pipeline ...` 한 번으로 후보 수집부터 ranking persistence까지 실행된다
- 실패가 있어도 성공한 결과는 남는다
- operator가 최소한 수동 일일 운영을 할 수 있다

## Phase 7 — Monitoring And Alert Dispatch

### Goal

이 단계부터 agent가 “계속 추적하는 시스템”이 된다.

### Build Tasks

1. `change_events` 생성 기준을 구현한다.
2. re-verification cadence를 canonical recruiting status 기준으로 적용한다.
3. immediate alert gate와 suppression rule을 구현한다.
4. Telegram push format을 정의한다.
5. quiet hours / duplicate suppression / applied/ignored suppression을 붙인다.

### Files

- new monitoring agent module
- `src/db/entity_store.py`
- Telegram notifier path
- tests for alert gating

### Exit Criteria

- deadline/status/apply_url/funding change가 change event로 기록된다
- alertable event만 Telegram으로 나간다
- 동일 change가 반복 발송되지 않는다

## Phase 8 — Daily Brief And Feedback Loop

### Goal

사용자가 매번 수동 조회하지 않아도 된다.

### Build Tasks

1. `/brief`와 scheduled daily brief를 구현한다.
2. urgent / new / top / changed 섹션을 고정한다.
3. `ignored`, `track`, `applied` 같은 lightweight feedback state를 도입한다.
4. feedback이 ranking/alert suppression에 반영되게 한다.

### Exit Criteria

- 하루 1회 digest가 생성된다
- 사용자의 관심 상태가 후속 alert에 반영된다

## Phase 9 — Deployment And Production Readiness

### Goal

로컬 데모를 실제 운영 가능한 시스템으로 끌어올린다.

### Build Tasks

1. env/config 정리
2. Railway 또는 동등 배포 환경 구성
3. persistent DB 운영 전략 확정
4. logging / metrics / basic health checks 추가
5. recovery runbook 작성

### Exit Criteria

- bot restart 후 state가 유지된다
- 배포 환경에서 scheduled runs가 가능하다
- 운영자가 장애 시 복구 절차를 문서로 따라갈 수 있다

## Build Order Inside Each Phase

각 phase는 아래 순서로 진행한다.

1. contract 정리
2. 저장 구조 정리
3. deterministic path 구현
4. tests 작성
5. runbook / operator command 정리

즉, “UI 먼저”가 아니라 “contract -> persistence -> behavior -> validation” 순서다.

## Recommended Immediate Next Sprint

다음 스프린트는 Phase 1-2를 끝내는 데 집중한다.

### Sprint Goal

“Telegram에서 profile을 등록하고 verified funding list를 안정적으로 읽을 수 있는 상태”

### Sprint Scope

1. persistence/type 하드닝
2. curated view 정리
3. `/register`, `/profile`, `/grants`, `/cohorts`, `/funds`, `/all` 안정화
4. card renderer와 empty/error state 테스트 고정

### Explicitly Not In This Sprint

- monitoring push
- `/brief`
- `/org`, `/research`
- deployment

## Validation Gates Per Phase

- unit tests for changed modules
- one end-to-end smoke path
- `npm run docs:check`
- `npm run ctx:check -- --strict`

## Success Condition For V1

V1은 다음이 동시에 되면 완료로 본다.

1. Telegram 사용자가 profile을 등록할 수 있다
2. 시스템이 verified opportunity를 안정적으로 보여준다
3. ranking이 프로젝트 기준으로 작동한다
4. 중요한 신규 기회와 변화가 Telegram으로 전달된다
5. 운영자가 수동 intervention으로도 시스템을 유지할 수 있다
