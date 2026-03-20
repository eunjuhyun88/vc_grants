# Funding Intelligence Agent — Source To DB Fill Spec

## Purpose

이 문서는 사용자가 제공한 spreadsheet/CSV 데이터가 Funding Intelligence Agent의
canonical entity model에 어떻게 채워져야 하는지 정의한다.

핵심 목표:

1. source file를 그대로 DB에 넣지 않고, 단계별로 정규화한다.
2. 각 row가 `Organization / Program / Opportunity / ApplicationEndpoint / Observation` 중
   어디까지 채워질 수 있는지 규칙으로 고정한다.
3. `바로 seed에 넣는 데이터`와 `review queue로 남기는 데이터`를 분리한다.

## Input Sources

현재 기준 입력 소스는 아래다.

| Source | 역할 | 주된 내용 | 기본 신뢰도 |
|---|---|---|---|
| `companies.csv` | grant registry source | folk grant/company rows | medium |
| `notes.csv` | operator note source | 보조 메모 | low |
| Excel `grants program` | grant source | grant name, amount, date note, link | medium |
| Excel `accelerators` 계열 시트 | cohort/program source | accelerator, VC cohort, builder-like rows | medium |
| Excel `Web3 VC` | fund registry source | active VC/fund registry | medium |

중요:

- 이 소스들은 `official verified facts`가 아니다.
- 이 소스에서 들어온 값은 기본적으로 `seed candidate fact`다.
- outbound surface에 바로 나가는 verified fact는 verification 단계에서만 승격된다.
- 이 소스만으로는 grant selection signal인 `TVL`, `30d transactions`, `active_wallets`, `integrations`를 채울 수 없다.

## Metric Enrichment Boundary

현재 사용자가 준 funding list 파일은 `funding source registry`를 만드는 데는 유용하지만,
grant ranking용 traction metric까지 직접 채워주지는 못한다.

즉 아래 둘은 별도 레이어로 분리해야 한다.

### 1. Program Trait Enrichment

grant/program 쪽에서 후속으로 채워야 하는 것:

- `program_traits`
- `selection_signals`

예:

- `traction_sensitive`
- `usage_sensitive`
- `liquidity_sensitive`
- `public_goods_friendly`
- `prelaunch_friendly`
- `infra_friendly`

이 값은 현재 spreadsheet/CSV만으로 안전하게 추론하면 안 되고,
official grant page나 operator review로 보강해야 한다.

### 2. Project Traction Snapshot

프로젝트 쪽에서 별도로 받아야 하는 것:

- `traction_stage`
- `tvl_usd`
- `transactions_30d`
- `active_wallets_30d`
- `volume_usd_30d`
- `protocol_fees_usd_30d`
- `integrations_count`

이 값은 funding list source에서 오는 데이터가 아니라,
operator input 또는 별도 metrics enrichment pipeline에서 와야 한다.

## Canonical Fill Layers

```text
User files
  -> raw extraction
  -> normalized rows
  -> resolved curated rows
  -> canonical seed_raw.json
  -> DB entity fill
  -> verification promotion
```

현재 repo 기준 파일 경로:

1. raw user files
2. `output/spreadsheet/funding_sources_normalized.csv`
3. `output/spreadsheet/funding_sources_resolved.csv`
4. `data/seed_raw.json`
5. SQLite DB (`organizations`, `programs`, `opportunities`, `application_endpoints`, `observations`)

## Fill Policy

### Rule 1. Review-required row는 기본 seed에 넣지 않는다

`review_required=yes` row는 기본 `seed_raw.json` 생성에서 제외한다.

현재 holdout queue:

- `Base | BaseCamp Awards`
- `Conviction | Embed`
- `First Round Capital | First Round`
- `Immutable | Immutable zkEVM Grants`
- `Interchain Foundation | Interchain Foundation Grants`
- `Iterative Incubator | Iterative Incubator (AI dev tools)`

### Rule 2. Seed row는 verified fact가 아니다

seed ingest 기본값:

- `output_status = pending`
- `source_tier = 3`
- `fact_confidence = 0.60`

즉, seed는 registry bootstrap 목적이다. outbound eligibility는 verification이 결정한다.

### Rule 3. Program 중심으로 채우고 Opportunity는 현재 MVP bridge로 유지한다

이상적인 모델:

- open intake가 명확할 때만 `Opportunity` 생성

현재 MVP bridge:

- seed row마다 대표 `Opportunity` 1개를 허용
- 단, `apply_url`이 없으면 outbound curated surface에서 제외
- 같은 `program + canonical url`은 재적재 시 update만 하고 duplicate 생성 금지

## Source-To-Entity Mapping

### 1. Organization

채움 규칙:

- `display_name` <- `organization`
- `normalized_name` <- normalized `organization`
- `domain` <- `program_url`, `website`, `apply_url` 중 first valid domain
- `org_type` <- `program_type/category` 기반 추론
- `website_url` <- `program_url` 또는 `website`
- `sector_tags` <- source row `sector_tags`

조직 생성 기준:

- same domain -> same organization
- no domain이면 same normalized organization -> same organization

### 2. Program

채움 규칙:

- `display_name` <- `program`
- `normalized_name` <- normalized `program`
- `category` <- `program_type -> category` mapping
- `program_url` <- `website` 또는 `program_url`
- `description` <- first non-empty description

프로그램 생성 기준:

- unique `(org_id, normalized_name)`
- 같은 program이 legacy category로 들어와도 새 seed가 더 정확하면 category를 update한다

### 3. Opportunity

seed row에서 채우는 필드:

- `program_id`
- `status` <- `status_note + date_note` 기반 추론
- `deadline_at` <- 기본 null, explicit ISO date only
- `budget_note` <- `funding_range` 또는 `max_amount`
- `budget_amount` <- parse 가능한 최대 금액
- `apply_url` <- explicit `apply_url` only
- `fact_confidence` <- 0.60 default
- `source_tier` <- 3 default
- `source_chain` <- `website`, `program_url`, `apply_url`

상태 추론 기준:

- `rolling` 키워드 -> `rolling`
- `open`, `active`, `진행중`, `활성`, `accepting` -> `open`
- `upcoming`, `coming soon`, `opens` -> `upcoming`
- `closed`, `ended`, `expired`, `마감`, `종료` -> `closed`
- 없으면 `unknown`

### 4. ApplicationEndpoint

생성 조건:

- explicit `apply_url`가 있을 때만 생성

endpoint type 추론:

- `typeform` host -> `typeform`
- `airtable` host -> `airtable`
- `docs.google.com/forms` -> `google_form`
- 기타 공식 domain -> `official_portal`

`website`만 있고 `apply_url`가 없으면 endpoint row는 만들지 않는다.

### 5. Observation

목표 모델:

- user dataset row도 최소 1개의 provenance observation을 남긴다

seed observation 초안:

- `source_url` <- `website` 또는 `apply_url`
- `source_type` <- `user_dataset`
- `source_tier` <- 3
- `observed_data` <- `{source, status_note, date_note, funding_range, max_amount, review_notes}`
- `confidence` <- 0.60

주의:

- 현재 code path는 seed ingest 시 observation을 아직 채우지 않는다.
- 이 문서는 다음 구현에서 반드시 추가해야 할 canonical target이다.

## Program Type Mapping

| Input `program_type` | Program `category` | OrgType | Default outbound behavior |
|---|---|---|---|
| `grant` | `grant` | `foundation` | verify 후 `/grants` |
| `accelerator` | `accelerator` | `accelerator` | verify 후 `/cohorts` |
| `vc_cohort` | `vc_cohort` | `vc` | verify 후 `/cohorts` |
| `vc_fund` | `fund` | `vc` | registry-first, `/funds` only if actionable |
| `fund` | `fund` | `vc` | registry-first |
| `builder_program` | `builder_program` | `ecosystem` | verify 후 `/grants` 기본 |
| `residency` | `residency` | `accelerator` | verify 후 `/cohorts` |
| `hackathon_pipeline` | `hackathon_pipeline` | `ecosystem` | verify 후 `/cohorts` |

## What To Fill From The User’s Current Data

### Wave 1. Immediate seed import

현재 바로 넣는 대상:

- `output/spreadsheet/funding_sources_resolved.csv` 중 `review_required=no`
- 현재 clean count: `368`

세부 구성:

- grants: `183`
- accelerators: `84`
- vc_cohort: `1`
- funds: `100`

### Wave 2. Manual review holdout

현재 기본 seed에서 제외:

- remaining review `6`

이 row들은 official page나 canonical naming이 확정된 뒤에만 seed 승격한다.

### Wave 3. Quality hardening backlog

현재 non-blocking quality audit:

- total audit rows: `88`
- `missing_apply_url_for_cohort`: `63`
- `org_equals_program`: `36`
- `org_slug_like`: `12`
- `org_all_lowercase`: `4`
- `org_trailing_dot`: `1`

이건 seed 차단 사유가 아니라 후속 정리 backlog다.

## Current DB Fill Strategy

현재 DB를 채울 때의 실제 동작 기준:

1. curated CSV -> `data/seed_raw.json`
2. `python3 -m src.core.pipeline --seed`
3. seed row는 `Organization -> Program -> Opportunity`를 upsert-like ingest
4. 동일 `program + canonical url`은 새 opportunity를 만들지 않고 update
5. legacy `vc_cohort` fund rows는 새 seed가 `fund`면 program category를 교정

## What Should Not Be Filled Yet

아래는 source가 있다고 바로 DB fact로 채우면 안 된다.

- 추정 deadline
- 추정 apply_url
- 추정 funding amount
- social mention만 있는 opportunity
- canonical program name이 확정되지 않은 row
- grant page 근거 없이 추정한 `traction_sensitive` / `public_goods_friendly` trait
- funding list source만 보고 추정한 project TVL / transaction metrics

## Recommended Next Implementation Tasks

1. seed ingest 시 `observations` 생성 추가
2. `fund` rows 중 `apply_url` 없는 것은 long-term에 `Program only`로 유지하는 registry mode 추가
3. `review_queue_remaining.csv` 6건을 operator review UI 또는 CSV workflow로 승격
4. `final_quality_audit.csv`의 `missing_apply_url_for_cohort` 63건부터 우선 보강
5. seed import 후 summary report를 자동 생성해서 row counts, category mix, unresolved count를 매번 남기기
6. core grants/programs에 대해 `program_traits`와 `selection_signals`를 공식 페이지 기준으로 수동/반자동 backfill
7. project profile에 traction snapshot 입력 경로를 추가하고, traction-sensitive grant ranking에서만 사용
