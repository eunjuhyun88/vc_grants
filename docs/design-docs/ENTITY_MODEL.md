# Funding Intelligence Agent — Entity Model

## Purpose

이 문서는 Funding Intelligence Agent의 canonical data vocabulary를 정의한다.

핵심 목표:

1. `Organization -> Program -> Opportunity` 계층을 고정한다.
2. program type, display bucket, recruiting status, verification state를 분리한다.
3. dedup과 output curation이 같은 모델 위에서 동작하게 만든다.

## Core Object Graph

```text
Organization
  -> Program
      -> Opportunity
          -> ApplicationEndpoint
          -> Observation

CompanyProfile
  -> ProjectProfile

Opportunity + CompanyProfile
  -> MatchResult
```

## State Axes

아래 축은 서로 다른 의미를 가진다.

### 1. Recruiting Status

현재 모집 상태다.

- `open`
- `rolling`
- `upcoming`
- `closed`
- `unknown`

`deadline`은 status가 아니다. `deadline_at`과 `days_left`는 별도 필드다.

### 2. Verification State

우리가 그 opportunity를 얼마나 신뢰하는지의 상태다.

- `candidate`
- `pending_verification`
- `verified`
- `review_required`
- `rejected`
- `stale`

참고:

- 현재 SQLite MVP는 `output_status` 필드에 이 축 일부를 압축 저장할 수 있다.
- 장기적으로는 `verification_state`를 별도 필드로 명시하는 것이 맞다.

### 3. Project Eligibility

특정 프로젝트가 실제로 지원 가능한가에 대한 판단이다.

- `eligible`
- `conditional`
- `ineligible`
- `unknown`

이 값은 opportunity의 전역 fact가 아니라 `Opportunity x ProjectProfile` 관계에서 계산된다.

## Core Entities

### Organization

프로그램 운영 주체.

주요 필드:

- `id`
- `name`
- `org_type`
- `official_domain`
- `official_website`
- `description`
- `thesis_summary`
- `focus_areas`
- `active_status`

`org_type`:

- `vc`
- `foundation`
- `ecosystem`
- `accelerator_operator`
- `hybrid`

### Program

조직이 반복적으로 운영하는 프로그램.

주요 필드:

- `id`
- `organization_id`
- `program_name`
- `program_type`
- `official_page`
- `description`
- `recurring_model`
- `program_traits`
- `selection_signals`

`program_type`:

- `grant`
- `accelerator`
- `vc_cohort`
- `builder_program`
- `residency`
- `fund`
- `hackathon_pipeline`

`recurring_model`:

- `rolling`
- `batch`
- `seasonal`
- `unknown`

`program_traits`는 hybrid 성격을 보존하는 보조 태그다.

예:

- `ecosystem_backed`
- `token_incentive`
- `cohort_based`
- `investor_network`
- `traction_sensitive`
- `usage_sensitive`
- `liquidity_sensitive`
- `public_goods_friendly`
- `prelaunch_friendly`
- `infra_friendly`

`selection_signals`는 해당 program이 실제 selection에서 강하게 보는 입력을 표현한다.

예:

- `tvl`
- `transactions`
- `active_wallets`
- `integrations`
- `open_source`
- `technical_milestones`
- `research_quality`

### Opportunity

특정 시점의 실제 지원 창구.

주요 필드:

- `id`
- `program_id`
- `cohort_label`
- `recruiting_status`
- `deadline_at`
- `deadline_text`
- `opens_at`
- `days_left`
- `official_page`
- `apply_url`
- `funding_amount_text`
- `cohort_start`
- `cohort_duration`
- `discovered_at`
- `last_verified_at`
- `verification_state`
- `confidence`

규칙:

- Program 없이 Opportunity 생성 금지
- deadline 변경은 기존 opportunity update가 기본이다
- 새로운 cohort label 또는 실제 intake window가 생긴 경우에만 새 opportunity를 만든다

### ApplicationEndpoint

실제 제출 경로.

주요 필드:

- `opportunity_id`
- `endpoint_type`
- `url`
- `email`
- `is_primary`
- `verification_status`

`endpoint_type`:

- `official_portal`
- `typeform`
- `airtable`
- `google_form`
- `email`
- `other`

### Observation

근거 데이터.

주요 필드:

- `subject_type`
- `subject_id`
- `source_url`
- `source_type`
- `source_tier`
- `snippet`
- `fact_type`
- `observed_at`
- `confidence`

Observation은 fact provenance의 기본 단위다.

### CompanyProfile

매칭 기준이 되는 회사/프로젝트 정보.

필수 필드:

- `company_name`
- `project_name`
- `sector_tags`
- `subsector_tags`
- `stage`
- `geography`
- `funding_goal`
- `product_summary`
- `technology_summary`
- `target_ecosystems`

선택 필드:

- `traction_stage`
- `tvl_usd`
- `transactions_30d`
- `active_wallets_30d`
- `volume_usd_30d`
- `protocol_fees_usd_30d`
- `integrations_count`
- `traction_updated_at`

중요:

- 이 traction snapshot은 모든 ranking에서 항상 필요한 것이 아니다.
- `traction_sensitive`, `usage_sensitive`, `liquidity_sensitive` trait를 가진 grant/program에서만 강하게 사용한다.
- infra/public-goods/prelaunch grant에는 기본 neutral 처리 가능해야 한다.

## Display Mapping

사용자 출력 버킷은 program type과 별도다.

`display_bucket`:

- `grants`
- `cohorts`
- `funds`

기본 매핑:

| program_type | primary_display_bucket | notes |
|---|---|---|
| `grant` | `grants` | 직접적 funding support |
| `accelerator` | `cohorts` | cohort / batch 기반 |
| `vc_cohort` | `cohorts` | 필요 시 `funds` 태그 동시 노출 가능 |
| `builder_program` | `grants` | cohort 구조가 명시적이면 `cohorts` 승격 가능 |
| `residency` | `cohorts` | time-bound intake로 간주 |
| `fund` | `funds` | generic VC open form 포함 |
| `hackathon_pipeline` | `cohorts` | direct funding path일 때만 outbound 고려 |

중요한 점:

- hybrid 성격은 `program_traits`로 보존한다
- `/grants`, `/cohorts`, `/funds`는 primary display bucket을 기준으로 deterministic하게 동작한다

## Dedup Rules

### Organization

우선순위:

1. `official_domain`
2. `normalized_name`
3. alias map

### Program

우선순위:

1. `organization_id + normalized_program_name`
2. `official_page`

금지:

- deadline 변경을 이유로 새 program 생성
- social mention만으로 새 program 확정

### Opportunity

우선순위:

1. `program_id + cohort_label`
2. `apply_url`
3. `deadline_at + opens_at + label fingerprint`

금지:

- form 링크 하나만 다르다고 새 opportunity 생성
- cohort label이 같고 상태만 바뀌었다고 새 opportunity 생성

## Fact Versus Reasoning

### Facts

- recruiting status
- deadline
- apply URL
- funding amount text
- recurring model
- source tier
- verification timestamps

### Reasoning

- fit score
- actionability score
- expected value score
- priority score
- why fit
- next action
- project eligibility

Fact는 source-backed observation에서 오고, reasoning은 match layer에서 계산된다.
