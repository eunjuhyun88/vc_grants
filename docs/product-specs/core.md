# Surface Spec: core

- Status: active
- Canonical route entry: `/`
- Surface ID: `core`

## Purpose
`core`는 Telegram 기반 `Funding Intelligence Agent`의 사용자 표면이다.

이 surface의 목적은 사용자가 자신의 회사/프로젝트 프로필을 등록하면, 그 프로필에 맞는 VC·Grant·Accelerator·Ecosystem 기회를 지속적으로 찾아서 검증하고 우선순위를 계산해, Telegram 안에서 바로 조회하고 추적하게 만드는 것이다.

한 줄 정의:

> 초기 단계 founder/operator가 펀딩 기회를 직접 뒤지지 않아도, Telegram에서 검증된 기회를 받고 우선순위까지 확인할 수 있게 하는 개인화된 funding intelligence surface.

## Persona And Problem

### Primary Persona

- Seed persona: 펀딩 라운드나 grant/accelerator 지원을 병행하는 초기 단계 founder 또는 operator
- Seed account: HOOT와 같은 AI/Web3/infra 프로젝트 팀

### Job To Be Done

When funding opportunities keep changing across many sites and ecosystems, I want one Telegram surface that remembers my project profile and continuously surfaces verified, relevant opportunities, so that I spend time applying and deciding, not hunting and validating.

### Current Alternatives

- 북마크, 스프레드시트, 텔레그램 채널, 트위터/X, 수동 검색
- 개인 비서식 리서치 또는 ad-hoc 검색

### Why Current Alternatives Fail

- 정보가 분산되어 있고 stale 되기 쉽다
- apply URL, deadline, status가 검증되지 않은 채 섞인다
- 내 프로젝트 기준의 fit 우선순위가 없다
- 한 번 찾고 끝나며 변화 감지가 없다

### Evidence Status

- 현재 canonical docs 기준 확정된 seed user는 HOOT다
- production telemetry나 다수 고객 인터뷰 증거는 아직 없다
- 따라서 일반화된 persona 범위는 현재 `[가정]`이며, 운영 시작 후 검증이 필요하다

## Core User Flow

1. 사용자가 `/start`로 봇을 시작하고 `/register`로 회사명, 단계, 섹터, 핵심 프로젝트를 등록한다.
2. 시스템은 등록된 프로필을 기준으로 discovery sweep을 수행하고 raw opportunity를 수집한다.
3. verification이 source tier, apply URL, deadline/status를 검증하고 verified/pending 상태를 결정한다.
4. matching이 profile 기준 fit score와 priority score를 계산한다.
5. 사용자는 `/grants`, `/cohorts`, `/funds`, `/all`, `/ranking`으로 현재 추천 목록을 본다.
6. 시스템은 신규 고우선순위 기회, deadline/status 변화, 일일 digest를 Telegram으로 push 한다.
7. 사용자는 apply URL로 이동해 실제 지원을 진행하고, 이후 `/profile` 또는 후속 피드백 명령으로 관심 상태를 갱신한다.

## Must Have

- Telegram DM에서의 profile registration and retrieval
- Deterministic list commands: `/grants`, `/cohorts`, `/funds`, `/all`
- Personalized ranking via `/ranking`
- Fact-backed eligibility filtering before any outbound list or alert
- Verified opportunity push alerts for meaningful changes
- Daily or periodic summary surface
- `Fact != AI reasoning` 분리

## Should Have

- `/changes`와 `/brief`로 change feed와 digest 제공
- 사용자의 관심 상태를 반영할 lightweight feedback loop (`ignore`, `track`, `applied`)
- Project-level ranking explanation과 next action 문구
- Timezone-aware alert scheduling

## Won't Have In V1

- Web dashboard
- 자유 대화형 assistant fallback
- 지원서 자동 작성/자동 제출
- CRM, investor outreach, deck generation
- Team-wide permission model과 고급 협업 기능

## Non-Goals

- “모든 투자 데이터를 한 번에 다 보여주는 데이터베이스”가 되는 것
- 비검증 opportunity를 많이 보여줘서 탐색량을 늘리는 것
- Telegram 안에서 모든 행동을 끝내는 것
- 일반적인 시장 리서치 챗봇이 되는 것

## Success Metrics

### North Star

- `주간 활성 프로젝트당 Telegram에서 열어본 verified opportunity 수`

이유:

- 이 제품의 핵심 가치는 “검증된 기회를 적시에 보여주고 실제 검토 행동으로 이어지게 하는 것”이다.

### Input Metrics

- 등록된 프로젝트 중 최소 1개 verified opportunity를 받은 비율
- Top 10 ranked opportunities의 수동 평가 precision
- source publish 또는 발견 후 Telegram alert까지 걸린 시간
- false positive rate: “지원 불가/부정확”로 판정된 outbound opportunity 비율
- 알림 후 apply URL click-through rate

## Done Means

- 신규 사용자가 Telegram DM에서 프로필을 등록하고 조회할 수 있다
- 시스템이 verified + apply_url 존재 + source tier 기준을 만족하는 기회만 목록/알림에 노출한다
- 사용자가 `/ranking`에서 프로젝트 맞춤 우선순위를 볼 수 있다
- 신규 기회 또는 핵심 변경이 있을 때 push 알림이 발생한다
- deterministic command path에서 LLM이 실행되지 않는다
- DB가 비어 있거나 eligibility 미달일 때도 고정된 명확한 응답을 준다

## Context Contracts

### User-Facing Commands

- `/start`
- `/register`
- `/profile`
- `/grants`
- `/cohorts`
- `/funds`
- `/all`
- `/ranking`
- `/funding_for_project`
- `/funding_map`
- `/org`
- planned: `/changes`, `/brief`, `/urgent`, `/rolling_high_fit`, `/priority`, `/program`, `/opportunity`, `/fit`, `/research`, `/verify`

### Boundaries

- Telegram은 primary interface지만 authority는 DB facts다
- List and alert output은 eligibility filter를 반드시 통과해야 한다
- Reasoned output도 DB-backed facts 밖으로 추측을 확장하면 안 된다
- Browser/web UI를 전제로 한 설계를 여기의 핵심 surface로 간주하지 않는다

### Routes
- `/` — repo-local canonical surface anchor only; production user interface is Telegram DM/commands

### Stores
- none

### APIs
- none

## Milestones

### M1: Queryable Telegram MVP

- 사용자가 등록된 profile을 기반으로 `/grants`, `/cohorts`, `/funds`, `/all`, `/ranking`을 Telegram에서 조회할 수 있다
- 포함: profile registration, discovery/verification/matching pipeline, deterministic list output
- 제외: monitoring push, briefing, research commands

### M2: Alerting And Monitoring

- 사용자가 신규 고우선순위 opportunity와 중요한 change event를 Telegram push로 받는다
- 포함: monitoring cadence, change detection, alert gating, `/changes`, `/brief`
- 제외: team collaboration, feedback learning loop

### M3: Human Feedback Loop

- 사용자가 관심 없음/추적/지원 완료 상태를 기록하고 추천/알림에 반영할 수 있다
- 포함: lightweight action model, suppression rules, state persistence
- 제외: full application CRM

## Deep Links
- `docs/DESIGN.md`
- `docs/ENGINEERING.md`
- `docs/SYSTEM_INTENT.md`
- `docs/design-docs/ENTITY_MODEL.md`
- `docs/design-docs/PRIORITY_ALGORITHM.md`
- `docs/design-docs/TELEGRAM_UX.md`
- `docs/design-docs/TELEGRAM_COMMAND_SPEC.md`
- `docs/design-docs/OUTPUT_RULES.md`
- `docs/design-docs/OPERATIONS_MODEL.md`
- `docs/design-docs/AGENT_CONTRACTS.md`
- `docs/exec-plans/active/MVP_IMPLEMENTATION.md`
