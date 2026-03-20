# Funding Intelligence Agent — Operations Model

## Purpose

이 문서는 discovery, verification, ranking, monitoring, alert dispatch가 어떤 cadence와 gating rule로 운영되어야 하는지 정의한다.

목표는 두 가지다.

1. verified opportunity만 사용자에게 노출한다
2. stale/noisy alert 때문에 Telegram inbox가 신뢰를 잃지 않게 한다

## Operating Principles

1. fact collection과 user-facing output을 분리한다
2. partial failure가 나도 기존 verified data는 유지한다
3. outbound alert는 eligibility와 noise gate를 모두 통과해야 한다
4. 애매한 dedup/verification은 review queue로 보내고 자동 확정하지 않는다

## Run Types

### 1. Discovery Sweep

목적:

- active company profile에 relevant한 funding opportunities를 찾는다

입력:

- profile sector tags
- project tags
- category-specific search queries
- optional seed source list

출력:

- raw opportunity candidates

기본 cadence `[가정]`:

- category별 12h
- 수동 강제 실행 시 즉시

### 2. Ingest And Canonicalization

목적:

- raw candidate를 `Organization -> Program -> Opportunity` 구조에 맞게 저장한다

규칙:

- Program 없이 Opportunity 생성 금지
- org domain dedup 우선, normalized name dedup 폴백
- URL normalize 후 source chain에 저장

### 3. Verification

목적:

- source tier와 reachable evidence로 verified/pending 상태를 결정한다

verified 최소 조건:

- best source tier <= 2
- fact confidence threshold 충족
- apply_url 존재

reverification cadence:

- deadline <= 14일: 6h
- status = unknown: 12h
- open or rolling: 24h
- closed: 72h

### 4. Ranking Refresh

목적:

- verified opportunity에 대해 fit_score와 priority_score를 최신 상태로 유지한다

trigger:

- 신규 verified opportunity 생성 후
- profile 업데이트 후
- deadline/status/budget 등 priority 영향 필드 변경 후
- 일일 batch refresh

### 5. Monitoring And Change Detection

목적:

- 이미 저장된 opportunity의 중요한 변화 감지
- social monitoring provenance 중 verified actionable alert 후보 집계

watch fields:

- deadline
- status
- apply_url
- budget/funding note

change detection 결과는 `change_events`에 저장하고, user-facing alert 여부는 별도 gate로 판단한다.

social discovery provenance는 `social_monitoring_events`에 저장한다.
이 테이블은

- 어떤 round에서 찾았는지
- 어떤 X/Twitter source URL에서 시작했는지
- 현재 pending / verified / rejected 중 어디인지
- 이미 outbound alert를 보냈는지

를 추적하는 운영 surface다.

## Opportunity Lifecycle

```text
discovered_raw
  -> ingested
  -> pending_verification
  -> verified
  -> ranked
  -> alertable
  -> tracked / stale / closed / rejected
```

### State Rules

- `pending_verification`은 사용자 목록의 기본 결과에 포함하지 않는다
- `verified`여도 apply_url이 없으면 기본 outbound surface에서 제외한다
- `closed`는 목록에서 제외하지만 기록은 유지한다
- `rejected`는 provenance를 남기고 재노출하지 않는다

## Alert Gating

### Base Eligibility

- `output_status = verified`
- confidence threshold 충족
- `source_tier <= 2`
- `apply_url is not null`
- `status != closed`

### Immediate Alert Gate

base eligibility에 더해 아래 중 하나:

- 신규 opportunity이면서 `priority_score`가 project 상위권
- deadline이 새로 생겼고 `days_left <= 14`
- deadline이 단축되어 urgency가 상승
- status가 `open/rolling`에서 `closed` 또는 그 반대로 의미 있게 변경
- social monitoring provenance가 `verified`로 승격되었고 아직 `notified = false`

현재 runtime에서는 Telegram bot background dispatch loop가

- `SOCIAL_ALERT_POLL_SECONDS` 간격으로
- `SOCIAL_ALERT_BATCH_SIZE`만큼
- `list_social_alert_candidates()`를 조회하고
- 전송 성공한 event만 `notified = true`

로 마킹한다.

### Suppression Rules

- 동일 opportunity 동일 change type 중복 발송 금지
- 동일 social source URL / social event 중복 발송 금지
- quiet hours 중 비긴급 alert suppress
- 이미 `applied` 또는 `ignored` 처리된 opportunity는 기본적으로 신규 alert 제외

## Human-In-The-Loop

### Review Queue Needed For

- dedup confidence < 0.85
- conflicting source evidence
- high-value opportunity인데 verification이 pending 상태로 오래 남는 경우
- apply_url 또는 deadline이 반복적으로 불안정한 경우

### Manual Actions

- approve / reject candidate
- merge duplicate entities
- mark ignored
- mark applied
- force reverify

manual action은 audit trail이 남아야 한다.

## Failure Handling

### Discovery Failure

- search/fetch 실패가 나도 기존 verified list는 유지
- 부분 성공 결과는 저장
- 동일 source 반복 실패 시 backoff

### Verification Failure

- verified를 바로 null로 지우지 않는다
- 새 검증 실패는 stale 또는 pending 재검토 상태로 이동
- evidence 없이 deadline을 추측해 채우지 않는다

### Delivery Failure

- Telegram 전송 실패는 retry queue로 보낸다
- retry가 끝나도 실패하면 opportunity state를 롤백하지 않는다
- social alert는 한 cycle에서 전송 실패해도 `notified` 처리하지 않는다
- recipient가 한 명도 없으면 dispatch는 skip되고 event는 pending 상태를 유지한다

## Service-Level Targets

- deterministic list query: < 2s
- change detection to alert dispatch: < 30m target
- daily brief generation: scheduled window 내 1회

이 수치는 운영 시작 후 실제 workload를 보고 조정한다.

## Observability

필수 운영 지표:

- discovery run success rate
- verification success rate
- verified to pending regression count
- alert sent count by type
- alert suppression count
- duplicate merge review backlog
- median time from discovery to verified
- median time from verified to first user click

## V1 Boundary

V1에서 반드시 필요한 운영 모델:

- discovery sweep
- verification cadence
- ranking refresh
- immediate alert gate
- daily brief batch

V1에서 미룰 수 있는 것:

- advanced team permissions
- auto remediation for broken sources
- reinforcement learning style personalization
- SLA-aware multi-tenant load balancing
