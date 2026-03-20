# Funding Intelligence Agent — Requirements Specification (PRD v1.1)

> [core.md](core.md)가 현재 active Telegram surface behavior를 정의한다.
> 이 문서는 제품 문제, v1 범위, success criteria, stable product principles를 정의한다.
> 상세 데이터 계약은 `docs/design-docs/ENTITY_MODEL.md`, 스코어링은 `docs/design-docs/PRIORITY_ALGORITHM.md`, 명령 계약은 `docs/design-docs/TELEGRAM_COMMAND_SPEC.md`를 따른다.

## 1. Problem

온체인, AI, 크립토 인프라 스타트업은 VC, grants, accelerator, ecosystem builder program을 찾기 위해 여전히 수동 탐색을 반복한다.

주요 문제:

1. funding 정보가 여러 공식 사이트, ecosystem hub, announcement post에 분산되어 있다.
2. grant, cohort, VC-backed accelerator, builder incentive가 한 체계 안에서 관리되지 않는다.
3. 지금 실제로 지원 가능한지, rolling인지, batch가 열렸는지 확인 비용이 높다.
4. 같은 기회가 여러 이름과 URL로 중복 발견된다.
5. generic funding보다 thesis-fit funding이 더 중요한데, 프로젝트 기준 우선순위 판단이 없다.

즉 사용자는 단순 링크 모음이 아니라 아래 흐름을 자동화해 주는 시스템이 필요하다.

`발견 -> 검증 -> 정규화 -> 프로젝트 매칭 -> 우선순위 판단 -> 지속 모니터링`

## 2. Users And Validation Context

### Primary User

- AI / crypto / infra startup founder
- Web3 product builder
- ecosystem BD / strategy operator
- funding / partnership researcher

### Job To Be Done

When funding opportunities keep changing across many official sites and ecosystem pages, I want one system that continuously shows only verified, relevant opportunities for my project, so that I spend time deciding and applying instead of manually hunting and validating.

### Seed Validation Profile

- 현재 대표 seed profile은 `HOOT`다.
- HOOT는 `AI infra`, `decentralized AI`, `crypto infra`, `distributed compute` 성격을 가진다.
- 다만 `Nitro가 우선`, `Speedrun이 우선` 같은 project-specific strategy는 제품 전체 contract가 아니라 operator input이다.

즉 `HOOT`는 seed validation account이지만, 특정 프로젝트의 우선순위 리스트가 곧 전 제품의 전역 요구사항은 아니다.

## 3. Product Definition

한 줄 정의:

> Funding Intelligence Agent는 VC, grants, accelerators, ecosystem builder programs를 지속적으로 스캔하고, 현재 지원 가능한 기회를 검증한 뒤, 특정 프로젝트에 맞는 funding을 우선순위까지 계산해 추천하는 Telegram-first intelligence system이다.

이 시스템은 아래 둘을 결합한다.

- `Funding Intelligence Agent`
- `Submission Opportunity Tracking System`

이 시스템은 아래가 아니다.

- 단순 grant 링크 모음
- raw crawler 결과 표시기
- generic chat assistant
- 자동 지원서 제출 봇

## 4. Product Goals

이 시스템의 제품 목표는 5개다.

1. Funding opportunity 자동 발견
2. 현재 지원 가능 상태 추적
3. 프로젝트 기준 매칭
4. 우선순위 추천
5. 지속적인 상태/링크/마감 변경 업데이트

## 5. V1 Scope

### Must Have

- `Organization -> Program -> Opportunity` 중심 데이터 모델
- discovery candidate 수집
- status / deadline / apply URL / funding note 검증
- deterministic Telegram pull commands
- project-aware ranking
- output eligibility filtering
- change detection 기반 alertable event 생성
- seed database 초기 구축

### Should Have

- daily brief
- change feed
- lightweight feedback state (`ignored`, `track`, `applied`)
- project intent별 ranking weight 변경

### Won't Have In V1

- web dashboard
- generic chat fallback
- 자동 지원서 제출
- investor outreach automation
- 모든 조직에 대한 deep research dossier
- full CRM / collaboration / RBAC

## 6. Stable Product Principles

### 6.1 Opportunity, Not Page, Is The Core Object

중심 객체는 URL이 아니라 아래 계층이다.

`Organization -> Program -> Opportunity`

예:

- Organization = `Monad`
- Program = `Nitro Accelerator`
- Opportunity = `Nitro Accelerator Spring 2026`

### 6.2 Facts And Reasoning Must Be Separated

검증 기반 facts:

- recruiting status
- deadline
- apply URL
- funding amount text
- cohort start
- recurring model

AI reasoning:

- why it fits
- which funding narrative is strongest
- why priority is high
- whether grant / accelerator / VC path is strategically better

### 6.3 Raw Data Must Not Be Shown Directly

모든 발견 데이터가 사용자 출력으로 가면 안 된다.

`discover -> verify -> curate -> output`

### 6.4 Program Type, Display Bucket, And State Must Be Separate

아래는 서로 다른 축이다.

- `program_type`
- `display_bucket`
- `recruiting_status`
- `verification_state`
- `project_eligibility`

특히 `deadline`은 상태가 아니라 필드다.

### 6.5 Thesis-Fit Funding Comes Before Generic Funding

특히 HOOT 같은 프로젝트는 generic seed form보다 아래가 먼저다.

- ecosystem grants
- builder programs
- AI / Web3 accelerators
- infra thesis funds

## 7. Opportunity Families

제품 언어 차원의 핵심 family는 4개다.

1. Grants
2. Accelerators
3. VC Cohorts / VC + Ecosystem Accelerators
4. Ecosystem Builder Programs

세부 type, display mapping, hybrid 처리 규칙은 `docs/design-docs/ENTITY_MODEL.md`를 따른다.

## 8. Core User Flow

1. 사용자가 Telegram에서 `/start`와 `/register`로 company profile을 등록한다.
2. 시스템이 profile 기반 discovery sweep을 수행한다.
3. raw candidate가 `Organization / Program / Opportunity` 구조로 정규화된다.
4. verification이 source tier, status, deadline, apply URL을 검증한다.
5. matching이 fit, urgency, actionability, expected value, confidence를 계산한다.
6. output curation이 eligible opportunity만 `/grants`, `/cohorts`, `/funds`, `/all`, `/ranking`에 노출한다.
7. monitoring이 change event를 감지하고 alertable event를 push 한다.

## 9. Output Curation Requirements

### 9.1 Raw And Output Must Be Separated

사용자에게 보이는 것은 `output-eligible` 데이터만이다.

예시 lifecycle:

- raw
- candidate
- pending verification
- verified
- output eligible

### 9.2 Base Output Eligibility

기본 출력 조건:

- organization name 존재
- program name 존재
- recruiting status가 `open`, `rolling`, `upcoming`, `closed` 중 하나로 정규화됨
- `closed`가 아님
- apply URL 또는 공식 program page 존재
- confidence threshold 이상
- category sanity check 통과

### 9.3 Project Eligibility Must Be Considered

단순히 `open`이라고 해서 사용자에게 보여주면 안 된다.

최소한 아래 eligibility 신호가 반영돼야 한다.

- geography requirement
- stage requirement
- ecosystem requirement
- entity requirement
- open-source / builder requirement
- current material readiness

즉 `recruiting_status`와 `project_eligibility`는 별도다.

## 10. Seed Data And Operator Inputs

### V1 Seed Database

V1은 최소 `50-100`개 수준의 core funding program seed를 확보해야 한다.

포함 범위:

- core grants
- core accelerators
- core VC cohorts
- core ecosystem builder programs

### Operator Inputs

아래는 제품 전역 contract가 아니라 운영 입력이다.

- HOOT 기준 priority program list
- 특정 체인 / ecosystem 집중 스캔 리스트
- seed source registry

이 목록은 canonical product contract에서 분리해 관리한다.

## 11. Success Criteria And Initial Metrics

아래는 초기 운영 기준의 `[initial target]`이다. 운영 데이터가 생기면 조정한다.

### Product Success Criteria

- 실제로 지원 가능한 프로그램이 자동으로 보인다
- 마감이 가까운 것부터 우선순위가 올라온다
- HOOT 같은 특정 프로젝트 기준으로 thesis-fit funding이 generic 리스트보다 위에 온다
- grants / cohorts / funds가 섞이지 않고 출력 버킷이 안정적이다
- apply URL, status, deadline이 실제 action list로 쓸 만하다

### Initial Metrics

- `Top 10 precision >= 0.70` `[initial target]`
- `false positive rate <= 0.15` `[initial target]`
- `median discovery -> verified lead time < 24h` `[initial target]`
- `alert click-through rate >= 0.25` `[initial target]`
- `weekly active projects with >=1 verified opportunity >= 0.60` `[initial target]`

## 12. Open Questions

- project eligibility를 V1에서 어느 수준까지 자동화할 것인가
- builder program의 default display bucket을 `grants`로 둘지 `cohorts`로 둘지
- `unknown deadline` opportunity를 어느 정도까지 outbound surface에 허용할 것인가

## 13. Deep Links

- `docs/product-specs/core.md`
- `docs/design-docs/ENTITY_MODEL.md`
- `docs/design-docs/PRIORITY_ALGORITHM.md`
- `docs/design-docs/TELEGRAM_COMMAND_SPEC.md`
- `docs/design-docs/OPERATIONS_MODEL.md`
- `docs/design-docs/OUTPUT_RULES.md`
- `docs/exec-plans/active/MVP_IMPLEMENTATION.md`
