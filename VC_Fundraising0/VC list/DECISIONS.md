# Funding Intelligence Agent — Design Decisions

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-03-08 | 초기 작성 (세션 기록 기반) |

---

> 이 문서는 "왜 이렇게 설계했는가"를 기록한다.  
> 새 기능 추가 전 반드시 확인. 기존 결정을 뒤집을 경우 여기에 이유를 기록.

---

## ADR-001: 목록 명령에서 LLM 호출 금지
**날짜:** 2026-03-08  
**상태:** 확정

**문제:** `/grants` 입력 시 "Techstars 마감일은 매년 1월..." 같은 LLM 일반 상식 응답이 출력됨.  
**원인:** 목록 조회 명령이 LLM 자유생성 경로를 타고 있었음. DB 데이터가 system prompt에 주입 안됨.  
**결정:** `/grants /cohorts /funds /all /ranking /changes`는 LLM 호출 완전 제거. DB → formatter → output만.  
**예외:** `/org /fit /research`는 LLM 허용하되 PROVIDED_FACTS(DB 데이터)만 사용.  
**반영:** telegram_bot.py Phase 5 수정 예정.

---

## ADR-002: Opportunity는 Program 없이 생성 불가
**날짜:** 2026-03-08  
**상태:** 확정

**문제:** apply form URL만 보고 Opportunity를 직접 생성하는 경우 발생.  
**결정:** `program_id NOT NULL` 강제. Program이 없으면 먼저 Program을 생성해야 함.  
**이유:** Organization → Program → Opportunity 계층 없이는 dedup·분류·fit 계산이 불가능.

---

## ADR-003: deadline은 추측 생성 금지, null 허용
**날짜:** 2026-03-08  
**상태:** 확정

**문제:** verified source 없는 deadline을 LLM이 추론해서 생성하는 경우 있었음.  
**결정:** verified source 없으면 `deadline_at = null`. rolling grant도 null이 정상값.  
**이유:** 잘못된 deadline은 urgency_score를 오염시켜 잘못된 우선순위 계산으로 이어짐.

---

## ADR-004: deadline 변경 시 기존 record UPDATE (새 row 금지)
**날짜:** 2026-03-08  
**상태:** 확정

**문제:** 동일 기회의 deadline이 연장될 때 새 Opportunity row를 생성하는 경우 있었음.  
**결정:** 기존 record UPDATE. change_events에 변경 이력 기록.  
**이유:** 새 row 생성 시 dedup 실패, 중복 출력, fit_recommendations 연결 끊김.

---

## ADR-005: Tier 4/5 소스 단독으로 verified 불가
**날짜:** 2026-03-08  
**상태:** 확정

**결정:** SNS(Tier 5), 집계 사이트(Tier 4) 단독 소스 → `output_status = 'pending'` 유지, verified 불가.  
**이유:** Twitter 발 정보의 deadline 오류율이 높음. Tier 1/2 교차 확인 없이 출력 시 신뢰도 저하.

---

## ADR-006: auto merge confidence 기준 0.85
**날짜:** 2026-03-08  
**상태:** 확정

**결정:** confidence ≥ 0.85 → auto merge. 미만 → review_queue.  
**이유:** 0.85 미만에서 false positive merge 발생 시 Organization/Program 데이터 오염. 보수적 기준 채택.

---

## ADR-007: /all 명령은 grants 5 + cohorts 5 + funds 5 (총 15개)
**날짜:** 2026-03-08  
**상태:** 확정

**결정:** 카테고리별 균등 5개씩. confidence 기준은 ≥ 0.80 (다른 명령보다 엄격).  
**이유:** /all은 포트폴리오 전체 개요용. 한 카테고리가 나머지를 압도하면 편향 발생.

---

## ADR-008: BriefingAgent → card_renderer 교체
**날짜:** 2026-03-08  
**상태:** 확정 (Phase 5 미구현)

**문제:** BriefingAgent가 LLM 자유생성으로 daily brief를 만들어 내용 신뢰 불가.  
**결정:** `briefing_agent.generate()` → `card_renderer.render_daily_brief(db_data)` 교체.  
**이유:** DB 기반 데이터만 사용해야 일관된 브리핑 보장.

---

## ADR-009: Priority Score 가중치 결정
**날짜:** 2026-03-08  
**상태:** 확정

```
fit_score        * 0.35   (가장 중요 — 우리 회사와 관련 없는 기회는 상위 불필요)
urgency_score    * 0.25   (마감 임박한 것 우선)
actionability    * 0.20   (지금 바로 지원 가능한지)
expected_value   * 0.10   (금액/가치)
confidence_score * 0.10   (데이터 신뢰도)
```

**이유:** 높은 금액이라도 우리 fit이 낮거나 지원 불가하면 실질 가치 없음. fit + urgency 중심.

---

## ADR-010: 2-layer 아키텍처 (Fact Engine + AI Agent Layer)
**날짜:** 2026-03-08  
**상태:** 확정

**결정:** Fact Layer는 수집·검증·DB 저장만. Intelligence Layer는 DB 데이터만 참조해서 분석.  
**이유:** AI Layer가 raw web 데이터를 직접 보면 hallucination 위험. Fact Layer가 이미 검증한 데이터만 통과시켜야 신뢰도 유지.
