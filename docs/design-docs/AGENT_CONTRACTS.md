# Funding Intelligence Agent — Agent Contracts

## 실행 계층 구조

```
Fact Layer       → Discovery Agent, Verification Agent
Intelligence     → Research Agent, Matching Agent
Operations       → Monitoring Agent, Briefing Agent
Cross-cutting    → Entity Resolution Agent
```

실행 모델: event-driven orchestration (scheduler.py)

---

## Agent 1: Discovery Agent

**역할:** 펀딩 기회 탐색 및 원본 데이터 수집
**Phase:** MVP (Phase 1)

### Input
```python
{
  "query": str,              # 검색 쿼리
  "category": str,           # 'grant' | 'accelerator' | 'vc_cohort' | 'ecosystem_builder'
  "sources": list[str]       # 대상 URL 목록 (optional)
}
```

### Output
```python
{
  "raw_opportunities": list[dict],  # 정제 전 원본 데이터
  "source_urls": list[str],
  "fetched_at": str                 # ISO timestamp
}
```

### 제약
- LLM 사용 허용 (fetch + parse 목적)
- deadline 추측 생성 금지 — 없으면 null
- output은 DB 저장 전 Entity Resolution으로 전달

---

## Agent 2: Entity Resolution Agent

**역할:** dedup·merge·alias 관리
**Phase:** Phase 2

### Input
```python
{
  "raw_entity": dict,        # Discovery에서 넘어온 원본
  "entity_type": str         # 'organization' | 'program' | 'opportunity'
}
```

### Output
```python
{
  "action": str,             # 'create' | 'merge' | 'review_queue'
  "matched_id": str,         # 기존 entity ID (merge 시)
  "confidence": float,       # 0.0~1.0
  "canonical": dict          # 정규화된 entity 데이터
}
```

### 제약
- confidence ≥ 0.85 → auto merge
- confidence < 0.85 → review_queue, 강제 merge 금지
- URL normalization 필수: query string 제거, trailing slash 제거, http→https

---

## Agent 3: Verification Agent

**역할:** 사실 검증 및 confidence 계산
**Phase:** MVP (Phase 1)

### Input
```python
{
  "opportunity_id": str,
  "sources": list[str]       # 검증할 소스 URL 목록
}
```

### Output
```python
{
  "opportunity_id": str,
  "output_status": str,      # 'verified' | 'pending' | 'rejected'
  "fact_confidence": float,
  "source_tier": int,        # 1~5
  "evidence": list[dict],    # observation 목록
  "verified_at": str
}
```

### 재검증 주기
| 상태 | 주기 |
|------|------|
| deadline ≤ 14일 | 6h |
| status = unknown | 12h |
| open / rolling | 24h |
| closed | 72h |

### 제약
- Tier 4/5 소스만 있으면 output_status = 'pending' (verified 불가)
- deadline 추측 보간 금지 — 검증 불가 시 null 유지

---

## Agent 4: Research Agent

**역할:** 조직 dossier 수집
**Phase:** Phase 2

### Input
```python
{
  "org_id": str,
  "depth": str               # 'basic' | 'full'
}
```

### Output → organization_dossiers
```python
{
  "org_id": str,
  "portfolio_count": int,
  "avg_check_size": str,
  "focus_areas": list[str],
  "decision_makers": list[dict],
  "raw_intel": dict,
  "confidence": float,
  "fetched_at": str
}
```

### 제약
- LLM 허용 (PROVIDED_FACTS 기반)
- 공식 사이트·Crunchbase·LinkedIn 기반
- 추측 데이터에 confidence < 0.7 마킹

---

## Agent 5: Matching Agent

**역할:** fit score 계산 및 우선순위 산출
**Phase:** MVP (Phase 1, persist=Phase 2)

### Input
```python
{
  "opportunity_id": str,
  "company_profile_id": str,
  "persist": bool            # True면 fit_recommendations에 저장
}
```

### Output → fit_recommendations
```python
{
  "opportunity_id": str,
  "project_name": str,
  "fit_score": float,        # 0.0~1.0
  "priority_score": float,   # 4-factor 가중 합산
  "why_fit": str,            # PROVIDED_FACTS 기반
  "next_action": str,
  "urgency_score": float,
  "expected_value": float,
  "confidence": float
}
```

### Priority Score 계산 (PRD 기준 4-factor)
```
priority_score =
  fit_score      * 0.35 +
  urgency_score  * 0.35 +
  expected_value * 0.15 +
  confidence     * 0.15
```

urgency_score 기준:
- D0-3: 1.0 / D4-7: 0.8 / D8-14: 0.6
- D15-30: 0.4 / rolling: 0.3 / unknown: 0.1 / closed: 0.0

### batch_rank()
```python
def batch_rank(
  company_profile_id: str,
  category: str = None,      # None이면 전체
  top_n: int = 10
) -> list[dict]:
  # 전체 opportunity 대상 priority_score 계산 후 상위 N개 반환
```

---

## Agent 6: Monitoring Agent

**역할:** 변화 감지 및 알림
**Phase:** Phase 3

### Input
```python
{
  "opportunity_ids": list[str],   # None이면 전체
  "check_type": str              # 'deadline' | 'status' | 'all'
}
```

### Output → change_events
```python
{
  "entity_type": str,    # 'opportunity' | 'program'
  "entity_id": str,
  "change_type": str,    # 'deadline_updated' | 'status_changed' | 'new_opportunity' | 'closed'
  "old_value": dict,
  "new_value": dict,
  "detected_at": str
}
```

### 제약
- 변화 감지 시 change_events DB 저장
- deadline 변경 → 기존 opportunity UPDATE, 새 row 생성 금지

---

## Agent 7: Briefing Agent

**역할:** 일일 브리핑 생성
**Phase:** Phase 3

### Input
```python
{
  "date": str,           # 'today' | ISO date
  "project_filter": str  # 'HOOT' | None
}
```

### Output
```python
{
  "top_opportunities": list[dict],   # priority 상위 5개
  "new_today": list[dict],           # 오늘 추가된 것
  "deadline_soon": list[dict],       # D-7 이내
  "changes": list[dict]              # change_events 오늘 것
}
```

### 제약
- LLM 호출 완전 제거
- DB에서 직접 데이터 조회 후 card_renderer 통과
- `card_renderer.render_daily_brief(db_data)` 사용
