# Funding Intelligence Agent — Telegram Command Spec

## Purpose

이 문서는 Telegram command surface의 canonical command contract를 정의한다.

원칙:

1. command-first UX를 유지한다
2. list commands는 deterministic하다
3. reasoned/detail commands는 명시적으로 호출될 때만 동작한다
4. v1에 꼭 필요한 명령과 후속 명령을 구분한다

## V1 Active Commands

| Command | Purpose | Mode | Input | Output |
|---|---|---|---|---|
| `/start` | 제품 소개와 기본 경로 안내 | deterministic | none | onboarding text |
| `/setup_hoot` | HOOT 기본 프로필 즉시 적용 | deterministic | none | seeded HOOT profile confirmation |
| `/register` | company / project profile 등록 | conversational | step-by-step answers | saved profile confirmation |
| `/profile` | 현재 profile 조회 | deterministic | none | profile summary |
| `/reset_profile confirm` | 현재 profile 초기화 | deterministic | explicit `confirm` | profile deleted confirmation |
| `/grants` | grants bucket 조회 | deterministic | optional paging later | ranked grant cards |
| `/cohorts` | cohorts bucket 조회 | deterministic | optional paging later | ranked cohort cards |
| `/funds` | funds bucket 조회 | deterministic | optional paging later | ranked fund cards |
| `/all` | 전체 bucket 조회 | deterministic | none | mixed top cards |
| `/ranking [intent]` | intent-aware 우선순위 조회 | deterministic scoring | `default`, `urgent`, `biggest_check`, `ready_now`, `best_fit` | ranked cards |
| `/funding_for_project [project] [intent]` | 특정 프로젝트 기준 actionable funding view | fast reference + ranking | `project?`, optional intent suffix | project-focused funding cards |
| `/funding_map [project]` | project별 funding landscape 요약 | research-backed fast lookup | `project?` | ecosystem-tier map + linked opportunities |
| `/org <name>` | 조직 dossier 조회 | DB + curated graph | organization name | org dossier + tracked opportunities |

## M2 Planned Commands

| Command | Purpose | Notes |
|---|---|---|
| `/changes` | 최근 변경 이벤트 피드 | monitoring 이후 |
| `/brief` | 일일 digest 조회 | briefing 이후 |
| `/urgent` | 마감 임박 opportunity 조회 | ranking preset으로 구현 가능 |
| `/rolling_high_fit` | rolling이지만 fit 높은 목록 조회 | ranking preset으로 구현 가능 |

## Later Commands

| Command | Purpose | Notes |
|---|---|---|
| `/priority <project>` | 특정 프로젝트 priority 전용 view | `/ranking` 확장형 |
| `/program <name>` | 프로그램 상세 정보 | entity lookup 안정화 후 |
| `/opportunity <name>` | 단일 opportunity 상세 정보 | canonical naming 필요 |
| `/fit <name>` | fit explanation | deterministic facts + reasoned explanation |
| `/research <name>` | research dossier 조회/수집 | research agent 필요 |
| `/verify <url>` | 수동 verification | operator / advanced mode |

## Deterministic Command Rules

다음 명령은 LLM 없이 끝나야 한다.

- `/profile`
- `/grants`
- `/cohorts`
- `/funds`
- `/all`
- `/ranking`
- `/changes`
- `/brief`
- `/urgent`
- `/rolling_high_fit`

실행 경로:

`DB / curated view -> eligibility filter -> renderer -> Telegram`

deterministic surface 공통 규칙:

- past exact deadline row는 검색/랭킹/list 단계에서 제외
- 즉, "안 보이게 숨김"이 아니라 current/actionable eligibility에서 탈락
- `status in (open, rolling, upcoming)` 이 아닌 row는 제외
- `fact_confidence < 0.75` row는 제외
- generic VC/fund homepage처럼 링크는 있지만 현재 application surface가 확인되지 않은 row는 제외
- link existence만으로는 부족하고, link content가 현재 program/opportunity를 확인해야 한다

## Response Contract

### List Commands

기본 포함 필드:

- organization
- program
- category or display bucket
- recruiting status
- deadline text
- funding amount text
- apply URL or official page
- confidence

actionable outbound surface 추가 규칙:

- `apply_url` 필수
- `status != unknown`
- `confidence >= 0.75`
- generic homepage 금지
- closed/stale form 금지

fit 데이터가 있으면 추가:

- fit score
- priority score
- why fit
- next action

research-backed surface에서는 추가:

- 짧은 program / cohort 설명
- deadline / rolling 상태 텍스트
- official program URL
- external apply URL
- past exact deadlines는 actionable/output eligibility에서 제외

### Empty States

| Situation | Response |
|---|---|
| profile 없음 | `/register` 유도 |
| DB 0건 | 현재 DB에 데이터 없음 |
| eligibility 미달 | 조건을 충족하는 verified 기회가 없음 |
| ranking 결과 없음 | 현재 매칭 가능한 기회가 없음 |

### Error States

| Situation | Response |
|---|---|
| Telegram config 오류 | 관리자 수정 필요 |
| DB 오류 | deterministic fixed error |
| research/verification 실패 | 실패 사실과 재실행 가능성 안내 |

## Non-Goals

- Telegram을 자유 대화형 assistant로 운영하는 것
- v1에서 모든 strategy/detail command를 한 번에 여는 것
- raw candidate를 바로 조회하게 하는 것
