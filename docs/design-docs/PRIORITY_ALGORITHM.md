# Funding Intelligence Agent — Priority Algorithm

## Purpose

이 문서는 project-aware funding ranking의 canonical scoring contract를 정의한다.

목표:

1. 같은 opportunity라도 project profile에 따라 다른 우선순위를 줄 수 있어야 한다.
2. 단순 funding amount가 아니라 thesis fit과 실제 실행 가능성을 반영해야 한다.
3. deterministic list/ranking surface에서 반복 가능한 결과가 나와야 한다.

## Ranking Preconditions

ranking 대상은 아래 조건을 먼저 통과해야 한다.

- organization / program 이름 존재
- recruiting status가 `open`, `rolling`, `upcoming` 중 하나
- `closed` 아님
- verified level confidence threshold 충족
- apply URL 또는 official page 존재
- category sanity check 통과

즉 `priority_score`는 output eligibility를 통과한 후보를 정렬하는 데 사용한다.

## Base Formula

```text
priority_score =
  fit_score * 0.35 +
  urgency_score * 0.25 +
  actionability_score * 0.20 +
  expected_value_score * 0.10 +
  confidence_score * 0.10
```

모든 점수는 `0.0 - 1.0` 범위로 정규화한다.

## Fit Score

fit는 “우리 프로젝트와 얼마나 맞는가”를 본다.

```text
fit_score =
  sector_fit * 0.30 +
  stage_fit * 0.20 +
  thesis_fit * 0.25 +
  ecosystem_fit * 0.15 +
  geography_fit * 0.10
```

세부 기준:

- `sector_fit`: sector / subsector tag overlap
- `stage_fit`: 현재 stage가 해당 opportunity의 허용 단계와 맞는지
- `thesis_fit`: opportunity description과 org/program thesis가 프로젝트 narrative와 맞는지
- `ecosystem_fit`: target ecosystem과의 정합성
- `geography_fit`: geography restriction이 있을 때만 적용, 정보 없으면 `0.5` 중립

## Urgency Score

urgency는 `deadline_at`과 `recruiting_status`에서 계산한다.

| 조건 | 점수 |
|---|---|
| `D0-3` | `1.00` |
| `D4-7` | `0.85` |
| `D8-14` | `0.70` |
| `D15-30` | `0.50` |
| `rolling` | `0.35` |
| `upcoming` | `0.25` |
| `unknown` | `0.10` |
| `closed` | `0.00` |

## Actionability Score

actionability는 “지금 실제로 낼 수 있는가”를 본다.

```text
actionability_score =
  endpoint_readiness * 0.35 +
  status_readiness * 0.25 +
  requirement_fit * 0.20 +
  material_readiness * 0.20
```

구성:

- `endpoint_readiness`: verified application endpoint 존재 여부
- `status_readiness`: 현재 접수 가능한지, upcoming인지
- `requirement_fit`: stage / geography / ecosystem requirement 부합 여부
- `material_readiness`: 현재 프로젝트 단계상 제출 material 준비 가능성

`requirement_fit` 내부 분해 기준:

```text
requirement_fit =
  stage_requirement_fit * 0.35 +
  geography_requirement_fit * 0.15 +
  ecosystem_requirement_fit * 0.20 +
  traction_requirement_fit * 0.30
```

즉 TVL이나 transaction activity는 top-level factor를 하나 더 만드는 대신,
“그 grant가 실제로 요구하는 selection signal인가”를 본 뒤 `requirement_fit` 안에서만 반영한다.

예:

- HOOT가 MVP라면 grant / accelerator actionability는 높고, late-stage VC fund actionability는 낮을 수 있다.

## Grant-Specific Traction Rules

모든 grant가 높은 TVL이나 많은 트랜잭션을 요구하는 것은 아니다.

따라서 V1 ranking은 `grant family`와 `program_traits`에 따라 traction을 다르게 취급한다.

### Traction-Sensitive Grant Families

아래 계열은 onchain traction이 실제 selection signal일 수 있다.

- ecosystem growth grants
- liquidity / TVL bootstrapping programs
- consumer or usage incentive grants
- chain deployment/adoption campaigns
- mainnet activity, user growth, 거래량, TVL을 명시적으로 묻는 grants

### Traction-Insensitive Or Neutral Grant Families

아래 계열은 low TVL / low transactions라고 자동으로 불리하게 보면 안 된다.

- infra grants
- dev tooling grants
- public goods / open source grants
- research / R&D grants
- prelaunch builder grants
- security, education, documentation grants

### Traction Inputs

traction-sensitive grant에서 우선 보는 입력은 아래다.

- `tvl_usd`
- `transactions_30d`
- `active_wallets_30d`
- `volume_usd_30d`
- `protocol_fees_usd_30d`
- `integrations_count`
- `traction_stage`

### Program Trait Gate

아래 trait가 있을 때만 `traction_requirement_fit`를 강하게 반영한다.

- `traction_sensitive`
- `usage_sensitive`
- `liquidity_sensitive`

아래 trait가 있으면 low onchain traction을 기본 패널티로 사용하지 않는다.

- `public_goods_friendly`
- `prelaunch_friendly`
- `infra_friendly`

### Traction Requirement Fit

```text
traction_requirement_fit =
  threshold_fit if explicit thresholds exist
  else stage_bucket_fit for traction-sensitive grants
  else 0.50 neutral
```

기본 stage bucket:

| traction_stage | 점수 |
|---|---|
| `prelaunch` | `0.20` |
| `early_usage` | `0.45` |
| `growing` | `0.70` |
| `established` | `0.90` |
| unknown | `0.30` for traction-sensitive grants / `0.50` neutral otherwise |

threshold-based scoring 예:

- grant가 `TVL >= $1M` 또는 `30d tx >= 100k`를 명시하면 threshold 충족률로 계산
- 복수 threshold가 있으면 min 또는 weighted minimum으로 보수적으로 계산

중요한 규칙:

- explicit threshold가 없는데 TVL이 높다는 이유만으로 public-goods grant를 올려치지 않는다
- traction data가 비어 있다고 infra/public-goods grant를 자동으로 내리지 않는다
- traction은 “grant selection probability”를 높이거나 낮추는 신호이지, 모든 grant의 보편 기준이 아니다

## Expected Value Score

expected value는 돈과 전략 가치를 같이 본다.

```text
expected_value_score =
  money_value * 0.60 +
  strategic_value * 0.40
```

### Money Value

| 조건 | 점수 |
|---|---|
| `$500K+` | `1.00` |
| `$200K-$500K` | `0.80` |
| `$50K-$200K` | `0.60` |
| `$10K-$50K` | `0.40` |
| `<$10K` | `0.20` |
| 금액 미공개 | `0.30` |

### Strategic Value

다음 신호를 반영한다.

- ecosystem credibility
- follow-on 가능성
- investor intro / network value
- builder distribution advantage
- chain / ecosystem strategic alignment
- large-chain or high-activity ecosystem exposure when the program is an ecosystem growth grant

## Confidence Score

confidence는 단순 source tier만이 아니라 evidence quality를 종합한다.

```text
confidence_score =
  source_quality * 0.35 +
  evidence_agreement * 0.25 +
  field_completeness * 0.20 +
  verification_freshness * 0.20
```

### Source Quality

| best_source_tier | 점수 |
|---|---|
| `1` | `1.00` |
| `2` | `0.80` |
| `3` | `0.50` |
| `4` | `0.25` |
| `5` | `0.10` |

### Evidence Agreement

- 공식 또는 파트너 source 2개 이상 합치면 높음
- 서로 충돌하는 fact가 있으면 낮춤

### Field Completeness

다음 핵심 필드의 충족률을 본다.

- recruiting status
- apply URL
- deadline or rolling signal
- program type
- funding amount text

### Verification Freshness

| last_verified_at | 점수 |
|---|---|
| `<= 24h` | `1.00` |
| `<= 7d` | `0.80` |
| `<= 30d` | `0.50` |
| `> 30d` | `0.20` |

## Intent-Aware Weights

같은 후보라도 사용자 의도에 따라 가중치를 바꾼다.

| intent | fit | urgency | actionability | expected_value | confidence |
|---|---|---|---|---|---|
| `default` | 0.35 | 0.25 | 0.20 | 0.10 | 0.10 |
| `urgent` | 0.20 | 0.45 | 0.15 | 0.10 | 0.10 |
| `biggest_check` | 0.20 | 0.10 | 0.15 | 0.45 | 0.10 |
| `ready_now` | 0.25 | 0.15 | 0.35 | 0.10 | 0.15 |
| `best_fit` | 0.50 | 0.15 | 0.15 | 0.10 | 0.10 |

## Why-Fit And Next-Action Rules

V1에서는 `why_fit`과 `next_action`도 deterministic 또는 template-driven이 원칙이다.

예:

- `why_fit`: `"Monad ecosystem + crypto infra thesis + early-stage builder cohort 구조라 HOOT와 fit 높음"`
- `next_action`: `"이번 주 내 application form 확인 후 infra narrative 기준으로 draft 준비"`

목록 명령에서 자유 생성형 설명은 사용하지 않는다.

## Non-Goals

- LLM이 deadline을 추정해서 urgency를 보정하는 것
- “느낌상 중요해 보인다” 같은 비결정적 랭킹
- output-eligible이 아닌 candidate를 점수로 밀어 올려 출력하는 것
