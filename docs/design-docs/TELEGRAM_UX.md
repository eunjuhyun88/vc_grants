# Funding Intelligence Agent — Telegram UX

## Purpose

이 문서는 Telegram을 `Funding Intelligence Agent`의 primary user interface로 사용할 때의 명령 UX, 대화 흐름, push 알림 규칙, empty/error state를 정의한다.

명령별 canonical contract와 active/planned lifecycle은 `TELEGRAM_COMMAND_SPEC.md`를 따른다. 이 문서는 interaction pattern과 message behavior에 집중한다.

원칙:

1. Telegram은 inbox이자 control surface다
2. deterministic 목록 응답은 LLM 없이 빠르게 끝나야 한다
3. reasoned 응답도 facts 밖으로 추측하지 않는다
4. command-first UX를 유지하되, 제한된 자연어 router는 허용한다

## Channel Scope

### V1 Scope

- Telegram DM first
- 1 Telegram user = 1 active company profile
- 1 company profile = 여러 프로젝트 허용
- 한국어 우선 copy, source facts는 원문 보존 가능

### Out Of Scope For V1

- 그룹 채팅 운영
- 다중 사용자 shared workspace
- 텔레그램 외 웹 대시보드
- 자유 잡담형 agent

## Interaction Model

### 1. Setup

- `/start`
  - 제품 설명
  - 현재 profile이 있으면 현재 프로젝트와 바로 실행할 명령을 함께 안내
  - profile이 없으면 `/setup_hoot`와 `/register` 두 경로를 같이 안내

- `/setup_hoot`
  - HOOT 기본 프로필을 1-click seed한다
  - broken/generic profile이 있으면 canonical HOOT profile로 교체한다

- `/register`
  - multi-step conversation
  - 수집 항목: 회사/프로젝트 이름, stage, sector tags, 주요 프로젝트 이름, 프로젝트 tags
  - 마지막 단계에서 confirm 필요
  - 기존 profile이 있으면 overwrite/update flow로 동작
  - generic 이름(`infra`, `null`, `project` 등)은 저장 금지
  - 자연어 auto-register는 프로젝트 identity가 explicit하거나 known signature로 inferable할 때만 저장한다
  - 기존 profile이 있으면 generic 추출값으로 덮어쓰지 않고 project/tags를 merge한다

- `/profile`
  - 현재 저장된 company profile 표시
  - active projects와 tags를 함께 보여준다

- `/reset_profile confirm`
  - 저장된 profile을 명시적으로 삭제한다
  - accidental reset 방지를 위해 `confirm` 인자 없이는 실행하지 않는다

### 2. Pull Queries

- `/grants`
- `/cohorts`
- `/funds`
- `/all`
- `/ranking [intent]`

제한된 자연어 입력도 아래 command surface로 라우팅될 수 있다.

예:

- `펀딩 추천해줘` -> `/funding`
- `더 찾아줘` -> `/discover`
- `이 링크 지원 가능한지 봐줘 https://...` -> direct-source intake + verify
- `HOOT 기준 지금 낼 수 있는 것 정리해줘` -> `/funding_for_project HOOT`
- `HOOT funding map 보여줘` -> `/funding_map HOOT`
- `Monad 어떤 곳이야 정리해줘` -> `/org Monad`

규칙:

- DB curated view 기반만 사용
- deterministic path에서는 LLM 금지
- 각 응답은 title, 총 건수, 카드 리스트, apply URL을 포함한다
- 기본 최대 노출은 10건, `/all`만 15건 허용

### 3. Push Surfaces

- 신규 고우선순위 opportunity alert
- deadline/status/apply_url 변경 alert
- 일일 brief/digest

push는 사용자가 명시적으로 명령하지 않았더라도 agent system이 proactive하게 보내는 surface다.

## Command Taxonomy

| Command | 목적 | 응답 방식 | V1 상태 |
|---|---|---|---|
| `/start` | 봇 소개 | deterministic | active |
| `/setup_hoot` | HOOT 기본 세팅 | deterministic | active |
| `/register` | profile 등록/갱신 | conversational | active |
| `/profile` | profile 조회 | deterministic | active |
| `/reset_profile confirm` | profile 초기화 | deterministic | active |
| `/grants` | grant 목록 | deterministic | active |
| `/cohorts` | cohort 목록 | deterministic | active |
| `/funds` | accelerator 목록 | deterministic | active |
| `/all` | 전체 목록 | deterministic | active |
| `/ranking [intent]` | 개인화 순위 | deterministic scoring | active |
| `/changes` | change feed | deterministic | planned |
| `/brief` | daily digest 조회 | deterministic | planned |
| `/funding_for_project [project] [intent]` | 프로젝트 액션 리스트 | reasoned, DB-backed | active |
| `/funding_map [project]` | 프로젝트별 funding landscape | reasoned, DB-backed | active |
| `/org [name]` | 조직 dossier | reasoned, DB-backed | active |
| `/fit [name]` | 특정 기회 fit 설명 | reasoned, DB-backed | phase 2 |
| `/research [name]` | dossier 수집/조회 | reasoned, DB-backed | phase 2 |
| `/verify [url]` | 수동 검증 | reasoned + verification | phase 2 |

## Message Design Rules

### Deterministic List Responses

- 2초 이내를 목표로 한다
- `organization`, `program`, `category`, `status`, `deadline`, `budget`, `confidence`, `apply_url`를 중심으로 보여준다
- fit data가 있으면 `fit_score`, `priority_score`, `why_fit`, `next_action`을 함께 보여준다
- 메시지 자체는 concise하게 유지하고, 행동은 apply URL click으로 이어지게 한다
- `unknown` status, `confidence < 0.75`, generic homepage, stale exact deadline은 user-facing actionable surface에서 제외한다
- apply link가 있더라도 그 링크의 실제 내용이 현재 program/application surface를 확인하지 못하면 제외한다
- generic funding/build/support URL만으로 `open`으로 간주하지 않는다

### Reasoned Responses

- dossier, fit explanation, verify 결과는 명시적으로 호출된 경우만 보여준다
- 자연어 router가 reasoned command로 변환하더라도 결과는 동일한 DB-backed contract를 따라야 한다
- 근거 facts가 불충분하면 “insufficient evidence” 성격의 응답을 해야지 상식으로 채우면 안 된다
- project/org research 응답은 가능한 경우 실제 program/cohort 한줄 설명과 `공식 링크`, `지원 링크`를 함께 노출한다
- 날짜가 이미 지난 exact deadline은 stale로 간주하고 사용자 출력에서 숨기는 것이 아니라 actionable eligibility에서 제외한다
- 기존에 잘못 저장된 generic profile이라도 known project signature가 있으면 runtime에서 repaired profile로 조회한다
- direct apply surface라도 current intake/window evidence가 없으면 actionable 결과에서 제외한다
- Telegram polling runtime은 single-instance guard를 사용해 중복 bot process로 인한 `getUpdates` conflict를 막는다

## Notification Design

### Alert Types

1. `new_high_priority`
   - verified 완료
   - apply_url 존재
   - priority_score 상위권 또는 fit/urgency가 높은 경우

2. `deadline_changed`
   - deadline이 새로 생기거나 단축된 경우

3. `status_changed`
   - open/rolling/closed 등 상태가 바뀐 경우

4. `daily_brief`
   - top opportunities
   - new today
   - deadline soon
   - today changes

### Push Policy

- 즉시 alert는 중요한 신규 opportunity와 critical change만 보낸다
- noise를 줄이기 위해 동일 opportunity의 중복 알림은 suppress 한다
- 일일 brief는 별도 배치로 보낸다
- social-discovered alert는 `verified + actionable + apply_url + current deadline/window`를 통과한 것만 보낸다
- social alert 메시지는 `공식 링크`, `지원 링크`, `소셜 근거`, `감시 계정`, `monitoring round`를 함께 포함한다
- runtime에서는 background dispatch loop가 pending social alert를 주기적으로 DM으로 전송한다

### Quiet Hours

- 기본 quiet hours `[가정]`: 22:00-08:00 user local time
- 예외: `D-3` 이하 deadline change는 quiet hours를 무시하고 보낼 수 있다
- timezone 수집 전에는 project default timezone을 사용한다

## Empty States

- profile 없음: `/register` 유도
- DB 0건: “현재 DB에 데이터 없음”
- eligibility 미달: “조건을 충족하는 verified 기회가 없음”
- ranking 결과 없음: “현재 매칭 가능한 기회가 없음”

empty state는 사용자가 다음에 무엇을 해야 하는지 한 문장으로 안내해야 한다.

## Error States

- Telegram token/config 오류: 관리자 수정 필요 메시지
- DB 오류: deterministic한 고정 문구
- LLM timeout: 재시도 유도
- verification/research 실패: 실패 사실과 재실행 가능성을 명시

오류 응답에 일반 대화 fallback을 섞지 않는다.

## Interaction Components

### V1

- slash commands
- 텍스트 응답
- MarkdownV2 formatting
- inline link 중심 CTA

### Later

- inline keyboard
- suppress / ignore / applied quick actions
- alert preference controls

## UX Non-Goals

- “채팅으로 뭐든 물어보면 답하는 assistant”를 만드는 것
- 화려한 conversational persona를 만드는 것
- Telegram을 mini-CRM으로 바꾸는 것

## Open Validation Questions

- founder/operator가 진짜로 DM-first surface를 선호하는지
- instant alerts와 daily digest의 균형이 어느 정도여야 noise가 낮은지
- `/ranking` intent 분류가 사용자에게 직관적인지
