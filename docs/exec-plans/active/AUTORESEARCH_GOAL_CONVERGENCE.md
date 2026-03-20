# Autoresearch Goal Convergence Plan

## Objective

`autoresearch`를 단순한 search-policy auto-improvement에서 멈추지 않고,
사용자가 실제로 원하는 `project-aware funding strategy output`까지 수렴하도록 설계한다.

이 계획의 기준 출력은 아래 4개다.

1. `actionable funding list`
   - 예: `/funding_for_project HOOT`
   - 요구 결과: 지금 실제로 낼 수 있는 top funding, 링크, 상태, deadline, why-fit, next action
2. `funding map`
   - 예: `/funding_map HOOT`
   - 요구 결과: 어떤 ecosystem/VC/cohort 축을 먼저 봐야 하는지 tiered map
3. `org/program dossier`
   - 예: `/org Monad`, `/program Speedrun`
   - 요구 결과: official facts + partner/mentor/ecosystem/selection signal 요약
4. `strategy memo`
   - 예: HOOT funding brief
   - 요구 결과: grant -> accelerator -> VC 순서, 왜 지금 이 순서인지, 제출 narrative까지 제안

즉 성공 기준은 `더 많은 후보 발견`이 아니라
`검색 결과가 위 4개 surface를 안정적으로 채워주는 상태`다.

## Why This Is Needed

현재 autoresearch loop는 다음에는 강하다.

- anchor recovery
- official/apply bootstrap
- quota-aware continuation
- benchmark-driven query adaptation

하지만 사용자가 원하는 최종 결과와는 아직 거리가 있다.

현재는 주로 `찾기`에 최적화되어 있고, 사용자는 `정리된 판단`을 원한다.

현재 사용자 목표:

- Claude/ChatGPT 수준의 서술형 funding list
- 프로젝트별 funding strategy
- VC + ecosystem + cohort까지 포함한 thesis-aware 추천
- official facts만 사용한 clean output

따라서 다음 단계는 `search loop`를 멈추는 것이 아니라,
그 loop가 채워야 할 `user-facing goal contract`를 명확히 고정하는 일이다.

## Non-Goals

- verification truth를 LLM이 생성하지 않는다
- deadline, funding amount, apply_url을 추측 생성하지 않는다
- Telegram deterministic list surface를 free-form assistant로 바꾸지 않는다
- DB schema 자체를 autoresearch가 임의 변경하게 하지 않는다

## Goal Hierarchy

### G0. Search Completeness

질문:

- 핵심 anchor를 찾는가
- official/apply path를 붙이는가
- quota가 걸려도 완전히 멈추지 않는가

대표 metric:

- anchor recall
- official/apply link precision
- hallucinated fact rate

### G1. Actionable Pool Quality

질문:

- 검증 가능한 high-fit opportunity가 top results에 충분히 모이는가
- rolling grant만 쌓이지 않고 cohort/builder program도 함께 들어오는가
- profile별로 바로 지원 가능한 결과가 상위에 모이는가

대표 metric:

- actionable_top10_count
- high_fit_verified_count
- missing_anchor_count
- cohort_or_builder_in_top10_count

### G2. Strategy Output Readiness

질문:

- `/funding_for_project`가 사람 손 없이 읽을 만한 action list를 만드는가
- `/funding_map`이 ecosystem 우선순위를 설명하는가
- `/org`와 `/program`이 research-grade dossier를 만드는가

대표 metric:

- output_ready_top10_count
- funding_map_coverage
- dossier_fact_completeness
- why_fit_coverage
- next_action_coverage

### G3. Continuous Operation

질문:

- 목표 미달이면 loop가 스스로 다음 행동을 이어가는가
- 특정 profile에서 성능이 무너지면 recovery mode로 전환하는가
- operator가 개입하지 않아도 threshold에 도달할 때까지 계속 탐색하는가

대표 metric:

- auto_continue_count
- successful_goal_recovery_count
- plateau_without_regression_count

## Current Gap Snapshot

| Desired state | Current state | Main blocker |
| --- | --- | --- |
| HOOT용 top funding list가 clean prose로 나온다 | benchmark는 top10 recall 중심 | strategy/dossier layer 부재 |
| funding map이 ecosystem tier를 보여준다 | anchor recovery 중심 | ecosystem graph와 map renderer 부재 |
| `/org` dossier가 investor/ecosystem context까지 묶는다 | official/program facts 위주 | partner/mentor/portfolio research path 부족 |
| goal unmet 시 계속 돈다 | search hints와 deep retry까지만 구현 | output-oriented goal evaluator 부족 |
| "우리한테 지금 왜 맞는지"를 보여준다 | fit/ranking은 있으나 설명 surface 약함 | explanation template와 dossier inputs 부족 |

## Target Runtime Architecture

```text
User intent + CompanyProfile
  ->
Goal Router
  ->
Autoresearch Loop
  ->
Discovery / Reference / Social / Bootstrap
  ->
Verification
  ->
Curated Opportunity Pool
  ->
Dossier Builder
  ->
Strategy Composer
  ->
Telegram Output / Reports
```

핵심은 `Goal Router`, `Dossier Builder`, `Strategy Composer` 3개를 추가하는 것이다.

그리고 runtime 제어는 루트 `funding_program.md`에서 한다.

- active cases
- continuous cycle budget
- plateau tolerance
- goal-type seed actions

이렇게 두면 code change 없이도 `어떤 목표를 먼저 수렴시킬지`를 사람이 바꿀 수 있다.

### 1. Goal Router

역할:

- 요청 surface별 성공 조건을 선택한다
- search mode를 profile/intent/output별로 바꾼다
- goal unmet일 때 어떤 recovery action을 우선할지 고른다

예:

- `/funding_for_project HOOT` -> actionable list goal
- `/funding_map HOOT` -> ecosystem coverage goal
- `/org Monad` -> dossier completeness goal

추천 구현 위치:

- `src/search/research_goal_router.py`
- 또는 `scripts/run_research_loop.py` 내부 selector를 분리

현재는 `src/search/research_goal_router.py` + `scripts/run_research_loop.py` 조합으로 운용한다.

### 1.1. Round Reflection / Promotion

goal router만으로는 부족하다.
continuous loop는 각 cycle의 best run을 `reflection artifact`로 압축해서
다음 cycle의 seed로 다시 넣어야 한다.

reflection에 들어갈 최소값:

- promoted actions
- winning search hints
- winning bootstrap terms
- case target scope (`goal_type`, `target_entities`, `target_ecosystems`)

이 구조가 있어야 `round 1에서 먹힌 것`이 round 2의 baseline으로 승격된다.
즉 `nanochat`의 round-result promotion과 같은 역할을 funding search layer에서 수행한다.

### 2. Dossier Builder

역할:

- organization/program/opportunity에 대한 research-ready context를 묶는다

필수 입력:

- official facts
- partner ecosystem
- mentor/investor mentions
- portfolio analogs
- selection signals
- program traits

추천 구현 위치:

- `src/research/dossier_builder.py`
- `src/research/dossier_types.py`

### 3. Strategy Composer

역할:

- verified facts + ranking + dossier를 바탕으로
  user-facing prose output을 만든다

제약:

- 없는 사실 생성 금지
- deadline/amount/apply_url 생성 금지
- why-fit과 next-action은 template-driven 또는 fact-backed LLM reasoning만 허용

추천 구현 위치:

- `src/research/strategy_composer.py`
- `src/interface/handlers/funding_handler.py`

## Search And Research Surfaces To Improve

### A. Anchor Registry Expansion

현재 curated priority registry는 핵심 cohort 일부만 강하게 잡고 있다.

다음 단계:

- ecosystem builder programs 추가
- mentor/investor-linked cohort 추가
- project-to-ecosystem analog rows 추가

필요 파일:

- `data/curated_priority_programs.json`
- 신규 `data/curated_ecosystem_graph.json`

### B. Ecosystem Graph Expansion

단일 프로그램 발견이 아니라 `ecosystem graph`를 따라 확장해야 한다.

노드 예시:

- organization
- program
- ecosystem
- partner
- mentor/investor
- portfolio analog
- social handle

엣지 예시:

- `Monad -> Nitro Accelerator`
- `Nitro Accelerator -> Paradigm mentor`
- `Chainlink -> BUILD`
- `Bittensor -> AI subnet ecosystem`

이 그래프는 unknown program discovery와 dossier building 둘 다에 필요하다.

### C. Query Family Expansion

현재 query adaptation은 broad hint 주입까지는 된다.

다음 단계:

- `cohort discovery family`
- `builder program family`
- `ecosystem funding family`
- `portfolio analog family`
- `mentor/investor page family`

예:

- `"<ecosystem> builder program apply"`
- `"<org> accelerator cohort investor mentor"`
- `"<program> demo day partners"`
- `"<similar project> funded by"`

### D. Social-To-Official Bridge

X/Twitter는 finding source로만 쓰고 있지만,
다음 단계는 social candidate를 official truth로 더 빠르게 연결하는 것이다.

필요 동작:

- tweet -> official domain 후보 추정
- tweet -> program/org alias 추정
- tweet -> ecosystem operator account 확장

### E. Recovery Modes

goal 미달 상황별로 recovery mode를 분리해야 한다.

1. `anchor_recovery`
   - 핵심 cohort/program이 top results에서 사라졌을 때
2. `actionability_recovery`
   - high-fit지만 apply path나 fresh status가 부족할 때
3. `ecosystem_coverage_recovery`
   - funding map에서 특정 ecosystem 축이 비었을 때
4. `dossier_recovery`
   - org/program dossier completeness가 낮을 때

## Benchmark Expansion

현재 benchmark는 discovery quality를 잘 보기 시작했지만, output goal은 아직 약하다.

다음 케이스를 추가해야 한다.

### 1. `hoot_actionable_strategy`

목표:

- HOOT 기준 top 10 action list를 만드는가

통과 조건 예시:

- `output_ready_top10_count >= 5`
- `cohort_or_builder_in_top10_count >= 3`
- `why_fit_coverage >= 0.8`
- `next_action_coverage >= 0.8`

### 2. `hoot_funding_map`

목표:

- HOOT 기준 ecosystem tier map을 채우는가

통과 조건 예시:

- `tier1_ecosystem_count >= 4`
- `tier2_ecosystem_count >= 4`
- `ecosystem_strategy_coverage >= 0.8`

### 3. `org_dossier_monad`

목표:

- Monad 기준 Nitro/Momentum/Mach/Residency 계열 dossier가 fact-backed로 모이는가

통과 조건 예시:

- `program_count >= 2`
- `fact_completeness >= 0.8`
- `official_source_ratio >= 0.8`

### 4. `vc_ecosystem_cohort_recall`

목표:

- Nitro, Speedrun, Alliance, Outlier, Binance Labs 같은 cohort를 놓치지 않는가

통과 조건 예시:

- `matched_anchor_count >= 4`
- `official_link_precision >= 0.95`

### 5. `social_to_official_bridge`

목표:

- social-first candidate가 official verification까지 이어지는가

통과 조건 예시:

- `social_candidate_to_verified_ratio >= 0.25`
- `social_only_verified_count == 0`

## Execution Phases

### Phase A. Goal Contract Lock

산출물:

- goal hierarchy 문서화
- output-ready benchmark cases 추가
- stop condition을 output goal 기준으로 보강

### Phase B. Registry And Graph Hardening

산출물:

- curated priority registry 확장
- curated ecosystem graph 신설
- recovery mode별 anchor set 정의

### Phase C. Policy Memory And Recovery Logic

산출물:

- case별 best-known policy 저장
- recovery mode selector 추가
- plateau/stall 이후 다음 행동 선택 강화

### Phase D. Dossier Builder

산출물:

- org/program/opportunity dossier builder
- partner/mentor/portfolio analog expansion
- dossier completeness scoring

### Phase E. Strategy Composer

산출물:

- actionable list renderer
- funding map renderer
- why-fit / next-action generator

### Phase F. Continuous Runtime

산출물:

- always-on goal checks
- profile-specific recovery schedule
- operator review report

## Immediate Implementation Batch

다음 배치는 이 순서가 맞다.

1. `eval/funding_benchmark.yaml`에 `hoot_actionable_strategy`, `hoot_funding_map`, `org_dossier_monad` 추가
2. `scripts/run_research_loop.py`에 `goal_type`과 `recovery_mode` 개념 추가
3. `data/curated_priority_programs.json` 확장과 `data/curated_ecosystem_graph.json` 신설
4. `src/search` 아래에 `research_goal_router.py` 추가
5. `src/research` 아래에 `dossier_builder.py`, `strategy_composer.py` 추가
6. `/funding_for_project`와 `/funding_map` output contract 초안 구현

## Done Condition

다음 조건이 만족되면 autoresearch가 사용자 목표 쪽으로 제대로 가기 시작했다고 본다.

1. HOOT 기준 `/funding_for_project`가 `verified` 기반 top 10을 안정적으로 만든다
2. 결과 안에 cohort/builder/grant가 전략적으로 섞여 있다
3. 각 결과에 `why it fits`와 `next action`이 fact-backed로 붙는다
4. `/funding_map HOOT`가 ecosystem tier를 명확히 보여준다
5. `/org Monad` 같은 org dossier가 official facts와 research context를 함께 보여준다
6. goal 미달 시 loop가 `stop`하지 않고 recovery mode를 선택해 계속 돈다

## One-Line Rule

다음 단계의 autoresearch는 `더 잘 찾는 검색기`가 아니라,
`사용자에게 바로 쓸 수 있는 funding strategy output을 만들기 위해 끝까지 수렴하는 research system`이어야 한다.
