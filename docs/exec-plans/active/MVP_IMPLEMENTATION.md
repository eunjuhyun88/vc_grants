# MVP Implementation Plan — Funding Intelligence Agent

## MVP 목표

최소한의 동작하는 파이프라인: **Discovery → Verification → DB → Telegram 출력**
Matching Agent는 간단한 형태로 포함. 나머지 agent는 Phase 2+.

---

## Phase 구조

| Phase | 핵심 산출물 | 의존성 |
|-------|-----------|--------|
| Phase 1 | DB 스키마 + entity_store + seed data | 없음 |
| Phase 2 | Discovery Agent + Verification Agent | Phase 1 |
| Phase 3 | Matching Agent (basic) | Phase 1 |
| Phase 4 | Output Interface (Telegram) + card_renderer | Phase 1 |
| Phase 5 | 파이프라인 통합 + E2E 테스트 | Phase 2-4 |
| Phase 6 | Entity Resolution Agent | Phase 5 |
| Phase 7 | Research Agent + Dossier | Phase 5 |
| Phase 8 | Monitoring Agent + Scheduler | Phase 5 |
| Phase 9 | Briefing Agent | Phase 7-8 |

---

## Phase 1: DB Foundation

### 산출물
- `src/db/schema.sql` — DDL (organizations, programs, opportunities, application_endpoints, observations, company_profiles)
- `src/db/entity_store.py` — CRUD 함수
- `src/core/types.py` — dataclass 정의 (OpportunityCard 등)
- `data/seed/hoot_profile.json` — HOOT company profile 초기 데이터

### 완료 기준
- [x] SQLite DB 생성 + 테이블 6개 생성
- [x] entity_store.py: create/read/update 함수 동작
- [x] HOOT company profile seed 데이터 입력

### 파일 목록
```
src/
  core/
    __init__.py
    types.py             # OpportunityCard, 공유 타입
    config.py            # DB 경로, API 키 등
  db/
    __init__.py
    schema.sql           # DDL
    entity_store.py      # DB 접근 레이어
data/
  funding.db             # SQLite DB (생성됨)
  seed/
    hoot_profile.json    # 초기 데이터
```

---

## Phase 2: Discovery + Verification

### 산출물
- `src/agents/discovery_agent.py` — 웹 검색 + fetch + parse
- `src/agents/verification_agent.py` — 사실 검증 + confidence 계산

### 완료 기준
- [ ] Discovery Agent: query 입력 → raw_opportunities 목록 반환
- [ ] Verification Agent: opportunity_id → verified/pending/rejected 판정
- [ ] Observation 테이블에 검증 증거 저장
- [ ] Source tier 1-2만 verified 허용

---

## Phase 3: Matching Agent (Basic)

### 산출물
- `src/agents/matching_agent.py` — fit_score + priority_score 계산

### 완료 기준
- [ ] HOOT profile 기반 fit_score 계산
- [ ] priority_score 공식 적용
- [ ] batch_rank() 동작 (상위 N개 반환)

---

## Phase 4: Output Interface (Telegram)

### 산출물
- `src/interface/telegram_app.py` — 명령 라우터
- `src/interface/card_renderer.py` — Telegram 출력 포맷터
- `src/interface/handlers/` — 명령별 핸들러

### 완료 기준
- [ ] /grants — DB 조회 → eligibility filter → 출력
- [ ] /cohorts — 동일
- [ ] /funds — 동일
- [ ] /all — grants 5 + cohorts 5 + funds 5
- [ ] DB 0건 → "데이터 없음" 고정 출력 (LLM 호출 없음)
- [ ] card_renderer 4개 함수 동작

---

## Phase 5: Pipeline Integration

### 산출물
- `src/core/pipeline.py` — Discovery → (Entity Resolution 생략) → Verification → DB → Matching
- 테스트 코드

### 완료 기준
- [ ] E2E: 검색 쿼리 → DB 저장 → Telegram 출력
- [ ] 수동 트리거: `python -m src.core.pipeline --query "AI grants"`
- [ ] 에러 복구: 실패 시 partial 결과 유지

---

## Phase 6+: 확장

| Phase | 내용 |
|-------|------|
| 6 | Entity Resolution Agent (dedup + merge) |
| 7 | Research Agent (org dossier) + /org, /research 명령 |
| 8 | Monitoring Agent + Scheduler + /changes 명령 |
| 9 | Briefing Agent + /brief 명령 |
| 10 | Railway 배포 + Postgres 전환 |

---

## 기술 결정

| 항목 | 선택 | 이유 |
|------|------|------|
| DB | SQLite | 1인 개발, 로컬 우선, Postgres 전환 용이 |
| LLM | Claude API (Haiku/Sonnet) | 비용 효율 + 한국어 지원 |
| Web Search | Tavily / SerpAPI | agent 검색용 |
| Telegram | python-telegram-bot | async 지원, 가장 널리 사용 |
| Python | 3.11+ | match 문법, asyncio |

---

## 다음 작업

Phase 1부터 시작:
1. `src/core/types.py` 작성
2. `src/db/schema.sql` 작성
3. `src/db/entity_store.py` 작성
4. seed data 입력
