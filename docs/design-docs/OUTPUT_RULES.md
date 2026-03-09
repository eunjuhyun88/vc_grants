# Funding Intelligence Agent — Output Rules

## 핵심 원칙

1. 목록 명령 응답에서 LLM 호출 금지 — DB → formatter → output만
2. DB 0건 → "현재 DB에 데이터 없음" 고정 출력, LLM 보완 없음
3. 응답 시간 < 2초
4. 메시지당 최대 10개 항목

---

## Output Pipeline

```
RAW DB
  → [1] Eligibility Filter
  → [2] Curated View (SQL JOIN)
  → [3] Sort / Rank
  → [4] card_renderer.py
  → [5] Telegram
```

---

## [1] Eligibility Filter

출력 최소 기준 — 하나라도 미달 시 출력 제외:

| 조건 | 기준 |
|------|------|
| output_status | = 'verified' |
| confidence (grants/cohorts) | ≥ 0.75 |
| confidence (funds) | ≥ 0.70 |
| confidence (/all 명령) | ≥ 0.80 |
| source_tier | ≤ 2 |
| apply_url | IS NOT NULL |
| status | != 'closed' |

---

## [2] Curated View SQL 패턴

```sql
SELECT
  o.*,
  p.display_name AS program_name,
  p.category,
  org.display_name AS org_name,
  fr.fit_score,
  fr.priority_score,
  fr.why_fit,
  fr.next_action
FROM opportunities o
JOIN programs p ON o.program_id = p.id
JOIN organizations org ON p.org_id = org.id
LEFT JOIN fit_recommendations fr
  ON fr.opportunity_id = o.id
  AND fr.company_profile_id = :company_profile_id
WHERE
  o.output_status = 'verified'
  AND o.fact_confidence >= :min_confidence
  AND o.source_tier <= 2
  AND o.apply_url IS NOT NULL
  AND o.status != 'closed'
  AND p.category = :category    -- 명령별 필터
```

---

## [3] 정렬 기준

기본: `priority_score DESC`
priority_score 없을 때 fallback: `fact_confidence DESC, days_left ASC`

---

## Telegram 명령별 규칙

| 명령 | LLM | 데이터 소스 | 기본 정렬 | 최대 출력 |
|------|-----|------------|---------|---------|
| /grants | X | DB → filter → renderer | priority_score | 10 |
| /cohorts | X | DB → filter → renderer | priority_score | 10 |
| /funds | X | DB → filter → renderer | priority_score | 10 |
| /all | X | grants 5 + cohorts 5 + funds 5 | priority_score | 15 |
| /ranking | X | DB → batch_rank() | priority_score | 10 |
| /changes | X | change_events DB | detected_at DESC | 10 |
| /org [name] | O | organization_dossiers | - | 1 |
| /fit [name] | O | fit_recommendations + dossier | - | 1 |
| /research [name] | O | research_agent → dossier | - | 1 |
| /brief | X | card_renderer.render_daily_brief() | priority_score | 15 |
| /verify [url] | O | verification_agent | - | 1 |

**LLM 허용 명령 제약:**
- PROVIDED_FACTS(DB 데이터)만 사용
- 외부 상식·일반 지식 생성 금지
- "Techstars 마감일은 매년..." 식의 응답 금지

---

## Core Output DTO

```python
@dataclass
class OpportunityCard:
    # 필수
    organization: str
    program: str
    category: str           # 'grant' | 'accelerator' | 'vc_cohort' | 'ecosystem_builder'
    status: str
    deadline: str | None    # "2026-04-01" | "Rolling" | None
    days_left: int | None
    budget: str | None      # "$50K-$500K" | None
    apply_url: str          # 필수 (없으면 출력 제외)
    confidence: float

    # 선택 (fit 데이터 있을 때만)
    fit_score: float | None
    priority_score: float | None
    why_fit: str | None
    next_action: str | None
```

---

## card_renderer.py 함수 시그니처

| 함수 | 입력 | 출력 |
|------|------|------|
| render_opportunity_card(opp) | OpportunityCard | str (Telegram markdown) |
| render_ranked_list(opps) | list[OpportunityCard] | str |
| render_dossier_card(dossier) | dict | str |
| render_daily_brief(data) | dict | str |

**시그니처 변경 금지** (telegram_bot.py 직접 연결)

---

## 에러 응답 규칙

| 상황 | 응답 |
|------|------|
| DB 0건 | "현재 DB에 해당 카테고리 데이터 없음. /research로 수동 추가 가능." |
| eligibility 미달 전부 | "조건을 충족하는 verified 기회가 없음." |
| DB 연결 실패 | "DB 오류. 관리자에게 문의." |
| LLM 타임아웃 (/fit 등) | "분석 타임아웃. 잠시 후 재시도." |

일반 대화 fallback 응답 추가 금지.
