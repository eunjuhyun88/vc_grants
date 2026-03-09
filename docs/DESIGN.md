# Design Authority — Funding Intelligence Agent

## Design Authority Stack

1. `docs/SYSTEM_INTENT.md` — 시스템 목적, 불변 원칙
2. `docs/design-docs/ARCHITECTURE.md` — 시스템 아키텍처
3. `docs/design-docs/DB_SCHEMA.md` — 데이터베이스 스키마
4. `docs/design-docs/AGENT_CONTRACTS.md` — 7 Agent I/O 계약
5. `docs/design-docs/OUTPUT_RULES.md` — Telegram 출력 규칙
6. `docs/design-docs/ENTITY_MODEL.md` — Entity 분류·Dedup 규칙
7. `docs/design-docs/PRIORITY_ALGORITHM.md` — 우선순위 계산 로직
8. `docs/exec-plans/active/*.md` — 진행 중 작업

## 핵심 설계 결정

### 1. 2-Layer Architecture
- **Fact Engine** (하단): Discovery → Entity Resolution → Verification → DB 저장
- **AI Agent Layer** (상단): Research, Matching, Briefing — Fact Engine 위에서 reasoning

### 2. Fact ≠ AI Reasoning 완전 분리
- DB 저장: deadline, status, apply_url, amount → source-backed facts만
- AI 생성: fit_score, why_fit, recommendation → 별도 테이블 (fit_recommendations)
- LLM은 DB facts를 기반으로만 reasoning. 상식/추측 생성 금지.

### 3. Entity 계층
```
Organization → Program → Opportunity → Application Endpoint → Observation
```
Program 없이 Opportunity 생성 불가. 모든 기회는 조직의 프로그램에 속함.

### 4. 명령 분류: Deterministic vs Reasoned
- Deterministic (LLM 금지): /grants, /cohorts, /funds, /all, /ranking, /changes, /brief
- Reasoned (LLM 허용, DB facts 기반만): /org, /fit, /research, /verify

### 5. Output Curation Pipeline
```
RAW DB → Eligibility Filter → Curated View → Sort/Rank → card_renderer → Telegram
```
verified + confidence ≥ 0.75 + source_tier ≤ 2 + apply_url 있음만 출력

### Anti-Patterns (금지)
- ❌ DB 0건일 때 LLM으로 보완 응답
- ❌ deadline 추측 생성
- ❌ 목록 명령에서 LLM 호출
- ❌ Program 없이 Opportunity 직접 생성
- ❌ Tier 4/5 소스만으로 verified 판정
