# Funding Intelligence Agent — Architecture

## 시스템 개요

사용자가 자신의 프로젝트를 등록하면, 해당 프로필에 맞는 펀딩 기회(VC·Grant·Accelerator·Ecosystem)를 자동 수집·검증·정규화·우선순위 산출하고 Telegram으로 지속 팔로업하는 AI agent 시스템. 범용 — 특정 회사 전용이 아님.

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
│  11 tables — schema: DB_SCHEMA.md                   │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│               OUTPUT INTERFACE (Telegram)            │
│  card_renderer.py → formatted output                │
│  Telegram은 delivery일 뿐, 핵심은 AI Agent System    │
└─────────────────────────────────────────────────────┘
```

---

## 3-Layer Agent 분류

| Layer | Agents | 역할 |
|-------|--------|------|
| Fact Layer | Discovery, Verification | 수집·검증·DB 저장 |
| Intelligence Layer | Research, Matching | 조직 이해, fit 분석 |
| Operations Layer | Monitoring, Briefing | 변화 감지, 요약 생성 |
| Cross-cutting | Entity Resolution | dedup·merge·alias 관리 |

---

## Entity 계층 구조

```
Organization
  └── Program (grant, accelerator, vc_cohort, ecosystem_builder)
        └── Opportunity (open | rolling | deadline | upcoming | closed | unknown)
              ├── Application Endpoint (form | email | typeform | airtable)
              └── Observation (검증 증거, source_tier 1~5)
```

**규칙:** Program 없이 Opportunity 생성 불가.

---

## 데이터 흐름

```
외부 소스
  → Discovery Agent (search + fetch + parse)
  → Entity Resolution (dedup + canonicalize)
  → Verification Agent (fact check + confidence + source_tier)
  → DB (entity_store.py)
  → Matching Agent (fit_score + priority_score)
  → fit_recommendations (DB)
  → Telegram 명령 (/grants /cohorts /funds)
      → Eligibility Filter (verified, confidence ≥ 0.75, tier ≤ 2)
      → card_renderer.py
      → 사용자
```

---

## 파일 구조 (계획)

```
src/
  agents/
    discovery_agent.py        # Fact Layer: 펀딩 기회 탐색
    entity_resolution.py      # Cross-cutting: dedup·merge
    verification_agent.py     # Fact Layer: 사실 검증
    research_agent.py         # Intelligence: 조직 dossier
    matching_agent.py         # Intelligence: fit 분석
    monitoring_agent.py       # Operations: 변화 감지
    briefing_agent.py         # Operations: 일일 브리핑
  db/
    entity_store.py           # DB 접근 레이어 (11 tables)
    schema.sql                # DDL
    migrations/               # schema 변경 이력
  interface/
    telegram_app.py           # 명령 라우터
    card_renderer.py          # Telegram 출력 포맷터
    handlers/                 # 명령별 핸들러
  core/
    types.py                  # 공유 타입 정의
    config.py                 # 설정
    scheduler.py              # 스케줄러 (Phase 후반)
data/
  funding.db                  # SQLite DB
  seed/                       # 초기 데이터 (company_profile, etc.)
```

---

## 의존성 방향 (절대 위반 금지)

```
types → db/entity_store → agents → interface
interface에서 entity_store 직접 import: 허용 (deterministic 명령용)
agent에서 다른 agent 직접 호출: 금지 (orchestrator 통해서만)
```

---

## 실행 모델

Event-driven orchestration (scheduler.py):

```
[Scheduled] Discovery sweep
  → Entity Resolution → Verification → DB
  → Matching (batch_rank) → fit_recommendations

[Scheduled] Monitoring check
  → change_events → (notification trigger)

[On-demand] /research, /verify
  → 개별 agent 호출
```

---

## 배포

- 현재: 로컬 실행 (개발)
- 예정: Railway
- DB: SQLite → Postgres (사용량 증가 시)
- Telegram Interface: python-telegram-bot library
