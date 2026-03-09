# Funding Intelligence Agent — Priority Algorithm

## Priority Score 공식 (PRD 기준)

```
priority_score =
  fit_score        * 0.35 +
  urgency_score    * 0.35 +
  expected_value   * 0.15 +
  confidence       * 0.15
```

모든 값은 0.0 ~ 1.0 범위.
4개 요소. actionability는 별도 factor가 아니라 confidence에 반영.

---

## 각 점수 산출 기준

### fit_score (0.0 ~ 1.0)
Matching Agent가 **등록된 company_profile**과 opportunity를 비교하여 산출.
사용자별 프로필이 다르므로 같은 opportunity라도 fit_score가 다름.

```
High fit (≥ 0.75):
  - sector_tags 2개 이상 overlap
  - 프로필의 핵심 섹터 명시적 지원
  - 프로필의 stage 허용

Medium fit (0.50 ~ 0.74):
  - 일반적 지원 + 관련 섹터 언급
  - 단계 제한 없음

Low fit (< 0.50):
  - 프로필과 무관한 섹터 특화
  - 프로필 stage보다 높은 단계 요구
  - 프로필과 무관한 체인/생태계 exclusive
```

### urgency_score (0.0 ~ 1.0)
deadline_at 기반 자동 계산.

| 조건 | 점수 |
|------|------|
| D0-3 (3일 이내) | 1.0 |
| D4-7 | 0.8 |
| D8-14 | 0.6 |
| D15-30 | 0.4 |
| rolling | 0.3 |
| unknown | 0.1 |
| closed | 0.0 |

### expected_value (0.0 ~ 1.0)
예상 가치 정규화.

| 조건 | 점수 |
|------|------|
| $500K+ | 1.00 |
| $200K-$500K | 0.80 |
| $50K-$200K | 0.60 |
| $10K-$50K | 0.40 |
| < $10K | 0.20 |
| 금액 미공개 | 0.30 |

### confidence_score (0.0 ~ 1.0)
fact_confidence 값 그대로 사용.

---

## Intent-aware Ranking

기본 가중치 외에 사용자 의도별 다른 프로필 적용:

| intent | fit | urgency | expected_value | confidence |
|--------|-----|---------|----------------|------------|
| default | 0.35 | 0.35 | 0.15 | 0.15 |
| urgent | 0.15 | 0.55 | 0.15 | 0.15 |
| highest_money | 0.20 | 0.15 | 0.50 | 0.15 |
| best_ecosystem_match | 0.55 | 0.20 | 0.10 | 0.15 |

---

## batch_rank() 동작

```python
def batch_rank(
    company_profile_id: str,
    category: str | None = None,
    top_n: int = 10,
    intent: str = "default"
) -> list[dict]:
    """
    1. Eligibility filter 통과한 opportunity 전체 조회
    2. 각 opportunity에 대해 fit_score 계산 (없으면 matching_agent 호출)
    3. urgency_score, expected_value, confidence 계산
    4. intent별 가중치로 priority_score 산출
    5. priority_score DESC 정렬
    6. 상위 top_n 반환
    """
```

---

## Eligibility Filter (출력 전 필수)

priority_score가 아무리 높아도 아래 조건 미달 시 출력 제외:

1. `output_status = 'verified'`
2. `fact_confidence >= 0.75` (funds는 0.70)
3. `source_tier <= 2`
4. `apply_url IS NOT NULL`
5. `status != 'closed'`
