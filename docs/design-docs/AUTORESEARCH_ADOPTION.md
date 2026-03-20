# Autoresearch Adoption

## Purpose

`karpathy/autoresearch`를 이 저장소에 그대로 이식하지 않는다.

대신 그 프로젝트의 핵심 운영 원칙만 Funding Intelligence Agent에 맞게 가져온다.

- 작은 변경 공간만 agent가 자동 개선한다
- 고정 benchmark로 성능을 측정한다
- 측정이 좋아질 때만 search policy를 승격한다

이 문서의 목표는 `Funding Intelligence discovery/search layer`에
`autoresearch-style self-improvement loop`를 적용하는 방법을 고정하는 것이다.

## Why We Need This

현재 문제는 검색 자체가 안 되는 것이 아니라, `어떻게 찾을지`가 계속 수작업이라는 점이다.

예:

- Nitro, Speedrun 같은 VC + ecosystem cohort를 어떤 쿼리로 찾을지
- X/Twitter에서 먼저 나온 발표를 어떤 규칙으로 candidate로 올릴지
- 어떤 domain/result를 authority 높게 볼지
- 어떤 extractor prompt가 funding program을 잘 잡는지
- 공식 program page 안에서 Typeform/Airtable/Google Form 같은 외부 apply endpoint를 어떻게 끝까지 따라갈지

이 영역은 코드의 truth model을 바꾸지 않으면서도 지속적으로 개선할 수 있다.

즉 `autoresearch`는 이 repo에서 다음으로 해석해야 한다.

- `model research loop`가 아니라
- `funding discovery research loop`

그리고 이 loop는 단발성 실험이 아니라 `목표 달성 전까지 계속 도는 운영 루프`여야 한다.

즉 기준은:

- "더 좋은 query를 한번 찾았다"가 아니라
- "우리 목표 profile이 원하는 수준의 opportunity quality를 안정적으로 받기 시작했다"

## Non-Goals

- verification truth를 LLM이 바꾸게 하지 않는다
- DB schema나 state model을 자동으로 mutate하지 않는다
- deadline, funding amount, apply_url을 추정 생성하게 하지 않는다
- output eligibility contract를 agent가 임의 변경하게 하지 않는다

## Goal-Driven Operation

이 설계의 핵심은 `goal-seeking loop`다.

loop는 단순히 검색 정책을 바꾸는 것이 아니라, 사전에 정의한 목표에 도달할 때까지
다음 행동을 계속 선택해야 한다.

### Example Goals

- HOOT 기준 top 10에 최소 5개 이상의 high-fit actionable opportunity 확보
- VC + ecosystem cohort recall을 핵심 프로그램 기준 80% 이상 유지
- social-first candidate discovery가 늘어나도 verified precision 90% 이상 유지
- official/apply link precision 95% 이상 유지

### Goal State vs Local Improvement

잘못된 기준:

- query 하나의 click-through가 올랐다
- candidate 수가 늘었다

올바른 기준:

- ranking 상위 결과가 실제 action list에 가까워졌는가
- profile별로 놓치면 안 되는 기회가 계속 상위에 잡히는가
- operator 개입 없이도 다음 탐색 행동을 이어갈 수 있는가

즉 `local search improvement`가 아니라 `goal-state convergence`를 봐야 한다.

## Program File

`karpathy/autoresearch`의 `program.md`에 대응하는 사람-편집 제어 파일을 이 repo에서는
루트의 `funding_program.md`로 둔다.

이 파일은 다음만 제어한다.

- 어떤 benchmark case를 우선 돌릴지
- continuous loop가 몇 cycle까지 갈지
- plateau를 몇 번 허용할지
- goal type별 seed action을 무엇으로 둘지

이 파일은 mutable search policy를 직접 담지 않는다.
대신 `runner가 어떤 recovery action 조합으로 계속 갈지`를 제어한다.

즉 program file의 역할은:

- truth 변경이 아니라 search/runtime 목표 선언
- code 수정이 아니라 goal-seeking control
- human-readable strategy + machine-readable JSON config 동시 제공

## Round Reflection

`karpathy/autoresearch`가 작은 mutable surface만 계속 바꾸고,
`nanochat`가 자율 실험의 winning changes를 base 경로로 승격한 것처럼,
이 repo의 funding loop도 `cycle reflection -> promoted policy` 단계를 가져야 한다.

여기서 reflection은 단순 로그가 아니다.

- best attempt에서 실제로 먹힌 action 조합
- 다음 시도에 재사용할 search hints
- official/apply direct fetch에 다시 쓸 bootstrap terms
- goal/target scope와 연결된 case-local memory

이 값은 continuous run 동안 다음 cycle의 seed로 다시 주입되고,
필요하면 curated reflection file로 승격되어 다음 실행의 baseline이 된다.

## Runtime Adoption

reflection은 benchmark runner 안에서만 머물면 안 된다.

승격된 policy는 실제 user-facing runtime에도 자동으로 흘러가야 한다.

- `/funding_for_project`
  - goal type 기준 reflection seed를 자동 resolve해서 `FundingSearchOrchestrator.search_for_project()`의 `search_hints/bootstrap_terms`로 주입한다
- `/funding_map`
  - `funding_map` goal type reflection을 fast/reference path에도 반영해서 ecosystem coverage bias를 준다
- profile-backed `/search`
  - reflection `search_hints`는 discovery hint query로, `bootstrap_terms`는 reference bootstrap source selection bias로 재사용한다

즉 reflection artifact의 목적은 보고서 보관이 아니라
`다음 benchmark cycle`과 `현재 live runtime`을 동시에 개선하는 것이다.

## Desired Output Targets

`autoresearch`의 최종 목적은 검색 metric 개선 자체가 아니다.

이 loop가 실제로 채워야 하는 user-facing target은 아래 4개다.

1. `actionable funding list`
   - `/funding_for_project <project>`
2. `funding map`
   - `/funding_map <project>`
3. `org/program dossier`
   - `/org <name>`, `/program <name>`
4. `strategy memo`
   - profile-aware funding brief

즉 benchmark와 recovery logic은 결국 아래 질문에 답해야 한다.

- "지금 바로 낼 수 있는 funding list가 더 좋아졌는가"
- "우리 프로젝트에 맞는 ecosystem map이 더 선명해졌는가"
- "왜 맞는지, 뭘 해야 하는지 설명 가능한가"

실행 계획은 `docs/exec-plans/active/AUTORESEARCH_GOAL_CONVERGENCE.md`를 따른다.

## Fixed vs Mutable Surfaces

### Fixed Surfaces

이 영역은 `autoresearch loop`의 자동 수정 대상이 아니다.

- `Organization -> Program -> Opportunity` hierarchy
- verification source priority
- confidence lower-bound rules
- output eligibility rules
- Telegram deterministic commands
- DB schema / persistence contract

대표 파일:

- `src/core/types.py`
- `src/db/schema.sql`
- `src/db/entity_store.py`
- `src/db/queries.py`
- `src/agents/verification.py`
- `docs/design-docs/ENTITY_MODEL.md`
- `docs/design-docs/OUTPUT_RULES.md`
- `docs/design-docs/SOCIAL_DISCOVERY.md`

### Mutable Surfaces

이 영역만 `autoresearch loop`의 실험 대상으로 둔다.

- profile query templates
- discovery query refinement rules
- social/X query expansion rules
- result reranking heuristics
- extractor prompt variants
- apply-surface discovery heuristics
- source expansion graph rules
- ecosystem-specific discovery policy

대표 파일:

- `src/search/profile_query_planner.py`
- `src/search/discovery_query_refiner.py`
- `src/search/reranker.py`
- `src/search/extractor.py`
- `src/search/fetcher.py`
- `src/search/funding_orchestrator.py`
- `src/search/engines/social_engine.py`

## Runtime Architecture

```text
CompanyProfile
  -> FundingSearchOrchestrator
       -> Seed round
          - web search
          - social search
          - reference engine
          - official/apply bootstrap sources
       -> DiscoveryEvaluator
       -> DiscoveryQueryRefiner
       -> additional web rounds
       -> ingest
       -> verification later promotes truth
       -> matching / ranking
```

`autoresearch adoption`은 이 구조를 바꾸지 않는다.

대신 아래 두 레이어를 추가한다.

1. `evaluation harness`
2. `policy experimentation loop`

그리고 runtime은 quota/rate-limit 상황에서도 완전히 멈추지 않아야 한다.

- broad web engine이 quota에 걸리면 해당 session에서 cooldown 처리한다
- reference registry에서 official/apply URL을 직접 bootstrap fetch 한다
- LLM planner/extractor가 rate limit에 걸리면 deterministic template fallback으로 계속 진행한다
- continuous run은 `recommended_actions`만 carry하지 말고 structured reflection artifact를 carry해야 한다

## Evaluation Harness

`autoresearch`를 붙이려면 먼저 benchmark가 있어야 한다.

이 repo에서 benchmark는 `funding discovery quality`를 측정해야 한다.

### Benchmark Inputs

- representative project profiles
  - HOOT
  - StockClaw
  - MoltVC
- target opportunity sets
  - grants
  - accelerators
  - VC + ecosystem cohort
  - builder programs

### Benchmark Cases

최소 케이스:

1. `HOOT -> top opportunities`
   - Nitro / Speedrun / Alliance / Ethereum ESP / Chainlink BUILD 축 recall
2. `VC + ecosystem cohort discovery`
   - 이름을 직접 모르는 상태에서 cohort candidate를 찾는가
3. `rolling grant handling`
   - rolling vs dated deadline을 구분하는가
4. `social-first candidate discovery`
   - X/Twitter에서 먼저 나온 발표를 candidate로 올리는가
5. `official-link precision`
   - 최종 추천에서 apply_url/official page 품질이 유지되는가

### Benchmark Metrics

필수 metric:

- top-10 precision
- important-program recall
- official/apply link precision
- hallucinated deadline rate
- stale status rate
- candidate-to-verified promotion rate
- social-source hit rate

### Goal Metrics

benchmark 외에 실제 운영 루프는 아래 `goal metrics`를 지속 추적해야 한다.

- actionable_top10_count
- high_fit_verified_count
- missing_anchor_count
- stale_top10_count
- social_candidate_to_verified_ratio
- profile_specific_recall

이 값이 목표 threshold에 도달하지 못하면 loop는 계속 돌아야 한다.

## Continuous Runtime

runner는 single pass benchmark에서 끝나지 않는다.

`scripts/run_research_loop.py --continuous --program-file funding_program.md`
형태로 실행하면 아래 순서로 cycle을 반복한다.

1. current carryover action으로 benchmark 실행
2. case별 goal metric 계산
3. failed metric 기반 recovery action 생성
4. program file의 seed action과 합쳐 다음 cycle carryover 구성
5. goal met / strategy exhausted / plateau / manual stop 중 하나가 나올 때까지 반복

compact 결과는 `output/research-evals/results.tsv`에 append-only로 남긴다.

### Hard Safety Metrics

다음은 항상 0 또는 매우 낮아야 한다.

- fabricated deadline count
- fabricated funding amount count
- social-only verified outputs
- phishing-like official-domain mistakes

## Experiment Loop

이 loop는 `one-shot compare`가 아니라 `goal not met -> next action` 구조로 동작한다.

### Step 1. Baseline Run

현재 canonical search policy로 benchmark를 실행한다.

산출물:

- case별 ranked outputs
- source traces
- metrics summary

### Step 2. Candidate Policy Change

agent는 아래 중 하나만 바꿀 수 있다.

- query planner variant
- social query expansion variant
- reranker weight variant
- extractor prompt variant
- domain allow/block adjustments

한 번에 여러 축을 같이 바꾸지 않는다.

### Step 3. Re-run Benchmark

같은 benchmark를 다시 실행한다.

### Step 4. Promotion Decision

다음을 만족할 때만 policy 승격:

- important-program recall 유지 또는 개선
- hallucinated fact metric 악화 없음
- official-link precision 악화 없음
- top-10 precision 개선 또는 동일

### Step 5. Archive Trial

각 실험은 결과와 함께 저장한다.

### Step 6. Goal Check

promotion 여부와 별개로, 현재 profile 목표가 달성되었는지 검사한다.

예:

- HOOT top 10에 핵심 anchor가 충분한가
- rolling grant만 많은 것이 아니라 actionable cohort도 들어왔는가
- social에서 찾은 후보가 verification으로 이어졌는가

### Step 7. Next Action Selection

목표 미달이면 다음 행동을 고른다.

- query expansion
- ecosystem-specific exploration
- social account watchlist 확대
- reranker variant 교체
- extractor variant 교체
- seeded registry expansion

quota나 rate-limit이 걸렸을 때도 다음 행동은 남아 있어야 한다.

- broad search cooldown 후 reference bootstrap 비중 확대
- anchor/program registry 보강
- official domain direct fetch 유지
- planner/refiner의 template fallback 사용

즉 루프는 `improvement found -> stop`이 아니라
`goal met -> stop`, `goal unmet -> continue`가 기본이다.

## Stop Conditions

다음 중 하나를 만족할 때만 자동 loop를 멈춘다.

1. 목표 metric이 threshold를 만족한다
2. 정해진 search budget/time budget을 초과했다
3. 최근 N회 반복에서 goal metric 개선이 없다
4. safety metric이 악화되어 rollback이 필요하다

운영 기본값:

- `goal_met` 전까지는 계속
- `stall_threshold` 도달 시 현재 best policy 유지 후 human review

## Required Artifacts

### 1. Benchmark Spec

경로 제안:

- `eval/funding_benchmark.yaml`

포함 내용:

- profile fixtures
- benchmark cases
- expected anchors
- metric thresholds

현재 구현 기준:

- 파일은 YAML 경로를 유지하되, repo 기본 의존성만으로 로드할 수 있도록 `JSON-compatible YAML` 형식을 허용한다

### 2. Runner

경로 제안:

- `scripts/run_research_loop.py`

역할:

- baseline 정책 실행
- variant 정책 실행
- metrics 비교
- 실험 로그 저장
- goal check 실행
- goal unmet 시 next action 선택
- stop reason 기록

현재 구현 기준:

- 각 케이스/시도는 fresh temporary SQLite DB에서 실행한다
- production/local main DB truth는 runner가 직접 수정하지 않는다
- `max_runs`는 soft budget이다. 목표가 아직 unmet이고 progress가 남아 있으면 runner는 `max_total_runs` 안에서 계속 시도한다
- goal unmet 시 runner는 다음 시도에서 `mode`를 승격하고, policy action을 `search_hints`로 변환해 seed discovery query에 실제 주입한다
- deep case의 첫 시도는 benchmark anchor를 `bootstrap_terms`로도 사용해서 official/apply page direct fetch를 먼저 시도할 수 있다
- discovery 결과는 rank 전에 verification pass를 거쳐 confidence/source tier/endpoint 상태를 갱신한다
- 기본 실행은 `improvement found -> stop`이 아니라 `goal_met`, `plateau_reached`, `max_runs_reached` 중 하나가 될 때까지 계속된다

### 3. Trial Logs

경로 제안:

- `.agent-context/research-runs/`
- 또는 `output/research-evals/`

필수 필드:

- run_id
- policy_variant
- benchmark_case
- retrieved candidates
- verified outputs
- metrics
- promotion decision
- goal_state
- stop_reason

## Policy File Boundaries

### Query Planner

`src/search/profile_query_planner.py`

개선 대상:

- sector keyword expansion
- ecosystem-specific templates
- VC + ecosystem cohort discovery queries
- similar-project-based discovery queries

### Social Search

`src/search/engines/social_engine.py`

개선 대상:

- X/Twitter query variants
- seeded account watchlists
- influencer/program/operator account expansion
- tweet-to-candidate heuristics

고정 규칙:

- social은 candidate only
- verified promotion은 official source 필요

### Reranker

`src/search/reranker.py`

개선 대상:

- domain authority weighting
- engine agreement weighting
- ecosystem-specific authority boosts

고정 규칙:

- official domain spoofing은 항상 방지

### Extractor

`src/search/extractor.py`

개선 대상:

- page prompt wording
- per-page extraction structure
- contradiction handling

고정 규칙:

- 없는 deadline/funding/apply_url 생성 금지

## Funding-Specific Search Modes

`autoresearch`를 이 repo에 맞게 쓰려면 mode를 분리해야 한다.

### Mode A. Known Program Hardening

이미 아는 핵심 프로그램의 상태 추적 정확도 개선.

예:

- Nitro
- Speedrun
- Alliance

목표:

- apply_url precision
- deadline freshness

### Mode B. Unknown Program Discovery

이름도 모르는 새로운 VC + ecosystem cohort를 찾는 모드.

목표:

- recall
- social-first discovery
- partner/mentor page expansion

### Mode C. Project-Aware Ranking Input Discovery

특정 profile에 더 잘 맞는 ecosystem을 찾는 모드.

예: HOOT면 decentralized AI / AI infra / crypto infra 편향.

목표:

- ecosystem coverage
- thesis-fit opportunity density

### Mode D. Goal Recovery

특정 profile의 goal metric이 무너졌을 때 회복하는 모드.

예:

- HOOT 상위 결과에서 Nitro/Speedrun 계열이 사라짐
- social 후보는 많은데 verified 승격이 안 됨
- rolling grant 편향만 남고 actionable cohort가 부족함

목표:

- missing anchors 복구
- actionability recovery
- profile-specific recall 회복

## Recommended Implementation Sequence

### Phase 1. Harness First

- benchmark spec 작성
- baseline runner 작성
- current policy metrics 저장

### Phase 2. Query Policy Isolation

- planner/refiner/reranker/extractor를 독립 policy unit으로 분리
- 실험 가능한 config surface 정의

### Phase 3. Social Discovery Improvement Loop

- seeded X account support
- ecosystem operator account expansion
- tweet quality scoring

### Phase 4. Promotion Rules

- benchmark pass 시 policy 승격
- fail 시 auto reject

### Phase 5. Goal Loop Runtime

- goal metric state 저장
- goal unmet 시 next action selector 구현
- stop reason / stall reason 기록

### Phase 6. Operator UX

- `/discover` 결과에 `why found` / `source mix` 표시
- operator가 benchmark 결과를 볼 수 있는 report 추가

## What Success Looks Like

성공 기준:

- Nitro/Speedrun/Alliance 같은 핵심 프로그램 recall이 유지된다
- 아직 이름을 모르는 cohort도 candidate로 더 자주 발견된다
- social-first 발견이 늘어나도 verified precision은 떨어지지 않는다
- ranking input pool이 HOOT 같은 profile에 더 thesis-aligned해진다
- 목표 threshold를 만족할 때까지 agent가 다음 탐색 행동을 스스로 고른다
- 그 결과가 actionable funding list / funding map / dossier surface를 실제로 채운다

## One-Line Rule

이 repo에서 `autoresearch`는 `search strategy auto-improvement layer`이지,
`fact truth mutation layer`가 아니다.
