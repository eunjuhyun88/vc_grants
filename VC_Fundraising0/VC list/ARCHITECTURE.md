# Funding Intelligence Agent — Architecture

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-03-08 | 초기 작성 |

---

## 시스템 개요

Web3/AI 스타트업(Holo Studio)의 펀딩 기회(VC·Grant·Cohort)를 자동 수집·검증·정규화·우선순위 산출하고 Telegram으로 제공하는 AI agent 시스템.

---

## 2-Layer Architecture

```
┌─────────────────────────────────────────────────────┐
│                  AI AGENT LAYER                     │
│  조직 이해 / fit 판단 / ask 추천 / priority 산출      │
│  Research Agent  Matching Agent  Briefing Agent     │
└─────────────────────────┬───────────────────────────┘
                          │ structured facts only
┌─────────────────────────▼───────────────────────────┐
│                  FACT ENGINE                        │
│  search / fetch / parsing / deadline extraction     │
│  canonicalization / dedup / evidence 저장           │
│  Discovery Agent  Verification Agent  Monitoring    │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│                  DATABASE (SQLite)                  │
│  11 tables — schema: docs/DB_SCHEMA.md              │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│               TELEGRAM BOT INTERFACE                │
│  card_renderer.py → formatted output                │
│  output rules: docs/OUTPUT_RULES.md                 │
└─────────────────────────────────────────────────────┘
```

---

## 3-Layer Agent 분류

| Layer | Agents | 역할 |
|-------|--------|------|
| Fact Layer | Discovery, Verification | 수집·검증·DB 저장 |
| Intelligence Layer | Research, Matching | 조직 이해, fit 분석 |
| Operations Layer | Monitoring, Briefing | 변화 감지, 요약 생성 |

---

## 7 Agents 개요

| Agent | 파일 | 상태 | 핵심 역할 |
|-------|------|------|-----------|
| Discovery | l1_discovery_agent.py | ✅ | 펀딩 기회 탐색 및 ingest |
| Entity Resolution | entity_resolution.py | ❌ 미구현 | dedup·merge·alias 관리 |
| Verification | verification_agent.py | ✅ | 사실 검증·confidence 계산 |
| Research | research_agent.py | ✅ | 조직 dossier 수집 |
| Matching | matching_agent.py | ✅ (persist 미구현) | fit score 계산 |
| Monitoring | monitoring_agent.py | ✅ (트리거 없음) | 변화 감지·알림 |
| Briefing | (telegram_bot 내) | 🐛 LLM 자유생성 | 일일 브리핑 생성 |

**상세 I/O 계약: docs/AGENT_CONTRACTS.md**

---

## 실행 모델

Event-driven orchestration:
- Discovery → Entity Resolution → Verification → (DB 저장)
- Matching → (fit_recommendations 저장)
- Monitoring → (change_events 저장) → Briefing

스케줄러: scheduler.py (Phase 6, 미구현)

---

## Entity 계층 구조

```
Organization
  └── Program (종류: accelerator_cohort, grant_round, ecosystem_program, fellowship, open_fund, scout)
        └── Opportunity (status: open | rolling | deadline | upcoming | closed | unknown)
              └── Application Endpoint
                    └── Observation (검증 증거)
```

**규칙:** Program 없이 Opportunity 생성 불가.

---

## 데이터 흐름

```
외부 소스
  → Discovery Agent (search + fetch)
  → Entity Resolution (dedup + canonicalize)
  → Verification Agent (fact check + confidence)
  → DB (entity_store.py)
  → Matching Agent (fit score)
  → fit_recommendations (DB)
  → Telegram /grants /cohorts /funds
      → Eligibility Filter
      → card_renderer.py
      → 사용자
```

---

## 주요 파일 목록

| 파일 | 역할 |
|------|------|
| entity_store.py | DB 접근 레이어 (11 tables) |
| card_renderer.py | Telegram 출력 포맷터 |
| telegram_bot.py | 명령 라우터 |
| l1_discovery_agent.py | 탐색 agent |
| verification_agent.py | 검증 agent |
| matching_agent.py | fit 분석 agent |
| monitoring_agent.py | 변화 감지 agent |
| research_agent.py | 조직 조사 agent |
| entity_resolution.py | (Phase 4, 미구현) |
| scheduler.py | (Phase 6, 미구현) |

---

## 배포

- 현재: 로컬 실행
- 예정: Railway
- DB: SQLite → Postgres 전환 예정
