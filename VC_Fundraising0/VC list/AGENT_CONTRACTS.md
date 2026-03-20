# Funding Intelligence Agent — Agent Contracts

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-03-08 | 초기 작성 (7 agents) |

---

## 실행 계층 구조

```
Fact Layer       → Discovery Agent, Verification Agent
Intelligence     → Research Agent, Matching Agent
Operations       → Monitoring Agent, Briefing Agent
Cross-cutting    → Entity Resolution Agent
```

실행 모델: event-driven orchestration (scheduler.py — Phase 6)

---

## Agent 1: Discovery Agent
**파일:** `l1_discovery_agent.py`  
**상태:** ✅ 구현됨

### Input
```python
{
  "query": str,              # 검색 쿼리
  "category": str,           # 'grants' | 'cohorts' | 'funds'
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
**파일:** `entity_resolution.py`  
**상태:** ❌ Phase 4 미구현

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
**파일:** `verification_agent.py`  
**상태:** ✅ 구현됨

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
**파일:** `research_agent.py`  
**상태:** ✅ 구현됨

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
**파일:** `matching_agent.py`  
**상태:** ✅ (persist=True 미구현 — Phase 2)

### Input
```python
{
  "opportunity_id": str,
  "company_profile_id": str,
  "persist": bool            # True면 fit_recommendations에 저장
}
```

### Output → fit_recommendations (persist=True 시)
```python
{
  "opportunity_id": str,
  "project_name": str,
  "fit_score": float,        # 0.0~1.0
  "priority_score": float,   # 가중 합산
  "why_fit": str,            # PROVIDED_FACTS 기반
  "next_action": str,
  "urgency_score": float,
  "actionability": float,
  "expected_value": float,
  "confidence_score": float
}
```

### Priority Score 계산
```
priority_score =
  fit_score        * 0.35 +
  urgency_score    * 0.25 +
  actionability    * 0.20 +
  expected_value   * 0.10 +
  confidence_score * 0.10
```

urgency_score 기준:
- D0-3: 1.0 / D4-7: 0.85 / D8-14: 0.70
- D15-30: 0.50 / rolling: 0.35 / unknown: 0.10 / closed: 0.00

### batch_rank() (Phase 2)
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
**파일:** `monitoring_agent.py`  
**상태:** ✅ 코드 있음 / 트리거 없음 (Phase 3)

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
- 변화 감지 시 change_events DB 저장 (Phase 3에서 구현)
- deadline 변경 → 기존 opportunity UPDATE, 새 row 생성 금지
- /changes 명령과 연결 필요

---

## Agent 7: Briefing Agent
**파일:** `telegram_bot.py` 내 `/brief` 핸들러  
**상태:** 🐛 LLM 자유생성 버그 (Phase 5에서 수정)

### Input
```python
{
  "date": str,           # 'today' | ISO date
  "project_filter": str  # 'HOOT' | None
}
```

### Output (수정 후)
```python
# card_renderer.render_daily_brief() 호출
{
  "top_opportunities": list[dict],   # priority 상위 5개
  "new_today": list[dict],           # 오늘 추가된 것
  "deadline_soon": list[dict],       # D-7 이내
  "changes": list[dict]              # change_events 오늘 것
}
```

### 수정 방향 (Phase 5)
- `briefing_agent.generate()` → `card_renderer.render_daily_brief(db_data)` 교체
- LLM 호출 완전 제거
- DB에서 직접 데이터 조회 후 renderer 통과
