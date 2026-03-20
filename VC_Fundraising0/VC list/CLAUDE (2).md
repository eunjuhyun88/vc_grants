# Funding Intelligence Agent — CLAUDE.md

> Claude Code가 이 파일을 자동 로드함. 모든 세션은 여기서 시작.
> 이 파일을 프로젝트 루트(~/Downloads/문서/VC_Fundraising/VC list/)에 배치할 것.

---

## Project Identity

Web3/AI 스타트업(Holo Studio Co., Ltd.)을 위한 VC·Grant·Cohort 기회 스캐너.
- **인터페이스:** Telegram bot
- **언어:** Python
- **DB:** SQLite (→ Postgres 예정)
- **배포:** Railway 예정
- **목적:** 펀딩 기회를 자동 수집·검증·정규화하고, 회사 fit 분석 및 우선순위 랭킹 제공

---

## Architecture (빠른 참조)

| 문서 | 위치 | 내용 |
|------|------|------|
| 전체 구조 | docs/ARCHITECTURE.md | 2-layer 구조, 11 table DB |
| Agent I/O 계약 | docs/AGENT_CONTRACTS.md | 7개 agent 입출력 계약 |
| DB 스키마 | docs/DB_SCHEMA.md | 11 table 정의 + 변경 이력 |
| Output 규칙 | docs/OUTPUT_RULES.md | curation pipeline + eligibility filter |
| 설계 결정 로그 | docs/DECISIONS.md | 주요 설계 결정 이유 기록 |
| HOOT 펀딩 목록 | docs/HOOT_FUNDING_LIST.md | priority score 순 top 10 + accelerators |

---

## Critical Rules — 위반 금지

### [RULE-01] Telegram 명령 응답 방식

| 명령 | LLM 허용 | 처리 방식 |
|------|----------|-----------|
| /grants /cohorts /funds /all /ranking /changes | ❌ 금지 | DB → formatter → output만 |
| /org /fit /research | ✅ 허용 | PROVIDED_FACTS만 사용. 외부 상식 생성 금지 |
| DB 0건 | ❌ 금지 | "현재 DB에 데이터 없음" 고정 출력. LLM 보완 없음 |

**위반 패턴 예시 (절대 하지 말 것):**
```python
# ❌ 잘못된 코드 — /grants에서 LLM 호출
response = llm.complete(f"Techstars 마감일은...")

# ✅ 올바른 코드
results = entity_store.get_opportunities(category='grants')
return card_renderer.render_ranked_list(results)
```

### [RULE-02] Entity 생성 규칙

- Opportunity는 반드시 Program이 존재해야 생성 가능 (Program 없이 Opportunity 생성 금지)
- deadline은 verified source 없으면 `null`. 추측·보간 금지
- rolling grant: `status=rolling`, `deadline_at=null`로 생성 (null이라고 삭제 금지)
- batch/season 구분: Program이 아니라 Opportunity로 생성

**Entity 계층:**
```
Organization → Program → Opportunity → Application Endpoint
```

### [RULE-03] Dedup & Canonicalization

- URL normalization: query string 제거, trailing slash 제거, http→https
- confidence ≥ 0.85 → auto merge
- confidence < 0.85 → review queue 이동 (강제 merge 금지)
- 같은 기회의 deadline 변경 → 새 Opportunity 생성 금지. 기존 record update
- 동일 도메인 Organization → domain 기준 dedup (alias 등록)

### [RULE-04] Output Eligibility Filter

출력 최소 기준 — 미달 항목은 출력하지 않음:

| 조건 | 기준 |
|------|------|
| output_status | = 'verified' |
| confidence (grants/cohorts) | ≥ 0.75 |
| confidence (funds) | ≥ 0.70 |
| confidence (/all) | ≥ 0.80 |
| source_tier | ≤ 2 (공식사이트/ecosystem portal만) |
| apply_url | IS NOT NULL |
| status | != 'closed' |

source_tier 정의:
- Tier 1: 공식 사이트 (confidence weight 0.95)
- Tier 2: ecosystem portal, docs (0.90)
- Tier 3: 블로그/뉴스 (0.80) — 보조 근거만
- Tier 4/5: SNS/aggregator — 단독 소스로 사용 금지

### [RULE-05] 재검증 주기 (monitoring_agent)

| 상태 | 주기 |
|------|------|
| deadline ≤ 14일 | 6h |
| status = unknown | 12h |
| open / rolling | 24h |
| closed | 72h |

---

## Priority Score 계산

```
priority_score =
  fit_score        * 0.35 +
  urgency_score    * 0.25 +
  actionability    * 0.20 +
  expected_value   * 0.10 +
  confidence_score * 0.10
```

urgency_score: D0-3=1.0 / D4-7=0.85 / D8-14=0.70 / D15-30=0.50 / rolling=0.35 / unknown=0.10 / closed=0.00

---

## Current Implementation State

### ✅ 완료된 파일

| 파일 | 상태 | 비고 |
|------|------|------|
| entity_store.py | ✅ | 8 tables, 3-step dedup, URL/name normalization |
| l1_discovery_agent.py | ✅ | |
| twitter_intel_agent.py | ✅ | |
| verification_agent.py | ✅ | |
| research_agent.py | ✅ | |
| matching_agent.py | ✅ | persist=True 미구현 |
| monitoring_agent.py | ✅ | 코드 있으나 트리거 없음 |
| card_renderer.py | ✅ | render_opportunity_card, render_dossier_card, render_ranked_list, render_daily_brief |
| telegram_bot.py | ✅ (부분) | LLM 자유생성 버그 있음 — Phase 5에서 수정 |

### ❌ 미완료 (Phase 순서)

- [ ] **Phase 1** — entity_store.py: `fit_recommendations` + `change_events` + `organization_aliases` 테이블 추가, 6개 신규 메서드
- [ ] **Phase 2** — matching_agent.py: `evaluate(persist=True)` + `batch_rank()` 추가
- [ ] **Phase 3** — monitoring_agent.py: change_events DB 저장 + /changes 연결
- [ ] **Phase 4** — entity_resolution.py 신규 생성 (resolve + merge + alias)
- [ ] **Phase 5** — telegram_bot.py: LLM 자유생성 제거, fit 출력 추가, BriefingAgent → card_renderer 교체
- [ ] **Phase 6** — scheduler.py + deploy.sh

### 🐛 알려진 버그

1. **/grants 등 목록 명령이 LLM 자유생성 경로를 탐** — Phase 5 수정 전까지 해당 명령 결과 신뢰 불가
2. **BriefingAgent LLM 자유생성** — card_renderer.render_daily_brief()로 교체 필요
3. **MonitoringAgent 미실행** — 코드 있으나 scheduler 없어 트리거 안됨
4. **fit_recommendations 미저장** — MatchingAgent 결과가 DB에 안 들어감

---

## Do Not Touch

| 대상 | 이유 |
|------|------|
| card_renderer.py render_* 함수 시그니처 | telegram_bot.py와 직접 연결됨. 변경 시 bot 전체 깨짐 |
| entity_store.py dedup 로직 | docs/DB_SCHEMA.md 확인 후에만 수정 |
| telegram_bot.py general chat fallback | 추가 금지. RULE-01 위반 |
| opportunity.deadline 필드 | 추측값 삽입 금지. null 허용 |

---

## Company Context (fit 판단 기준)

**회사:** Holo Studio Co., Ltd. (Korea, seed stage, AI+crypto)

**프로젝트 우선순위:**
1. HOOT — 분산 AI 인프라, 개인 데이터 기반 소형모델 학습
2. StockClaw — 크립토 트레이딩 AI
3. MoltVC — VC due diligence 자동화
4. PlayArts — AI 콘텐츠 검증/크리에이터 수익화
5. ClawGene — C. elegans 뇌 시뮬레이터 (Base blockchain)

**HOOT 섹터 태그:** `ai_infra`, `decentralized_ai`, `crypto_infra`, `distributed_compute`, `personal_model_training`

**상세 펀딩 목록:** docs/HOOT_FUNDING_LIST.md

---

## Agent 정체성 파일 (SOUL / AGENTS)

7개 agent는 각자 고유한 정체성 파일을 가진다.  
Simon 구조의 SOUL.md + AGENTS.md를 각 agent 디렉토리에 배치.

### 디렉토리 구조

```
agents/
├── discovery/
│   ├── SOUL.md       ← 이 agent가 누구인지, 역할, 말투
│   └── AGENTS.md     ← TIER 1 행동 규칙 (7개 이내) + TIER 2 레퍼런스
├── entity_resolution/
│   ├── SOUL.md
│   └── AGENTS.md
├── verification/
│   ├── SOUL.md
│   └── AGENTS.md
├── research/
│   ├── SOUL.md
│   └── AGENTS.md
├── matching/
│   ├── SOUL.md
│   └── AGENTS.md
├── monitoring/
│   ├── SOUL.md
│   └── AGENTS.md
└── briefing/
    ├── SOUL.md
    └── AGENTS.md
```

### SOUL.md 포맷 (agent별)

```markdown
# [Agent Name] — SOUL.md

## 정체성
나는 [agent 이름]이고, Funding Intelligence Agent 시스템의 [역할]을 담당한다.

## 핵심 역할
[한 문장으로 이 agent가 존재하는 이유]

## 입력 / 출력
- Input: [무엇을 받는가]
- Output: [무엇을 DB에 저장하는가]
- 다음 agent: [결과를 누구에게 넘기는가]

## 절대 하지 않는 것
- [이 agent가 절대 해서는 안 되는 행동]
```

### AGENTS.md 포맷 (TIER 구분 필수)

```markdown
# [Agent Name] — AGENTS.md

## TIER 1 (항상 주입, 7개 이내)
- 🔴 [절대 규칙 1]
- 🔴 [절대 규칙 2]
- [핵심 행동 규칙]
...

## TIER 2 (레퍼런스 — 필요 시 참조)
- 상세 I/O 계약: docs/AGENT_CONTRACTS.md
- DB 스키마: docs/DB_SCHEMA.md
- 설계 결정: docs/DECISIONS.md
```

### 각 Agent TIER 1 규칙 요약

| Agent | TIER 1 핵심 규칙 |
|-------|----------------|
| Discovery | 소스 없이 entity 생성 금지 / deadline 추측 금지 |
| Entity Resolution | confidence < 0.85 → review_queue, auto merge 금지 |
| Verification | Tier 4/5 단독 소스 → verified 불가 / deadline 보간 금지 |
| Research | PROVIDED_FACTS만 / 추측 데이터 confidence < 0.7 마킹 |
| Matching | fit score 계산 후 반드시 persist=True로 DB 저장 |
| Monitoring | deadline 변경 → UPDATE only, 새 row 생성 금지 |
| Briefing | LLM 자유생성 금지 / card_renderer.render_daily_brief()만 사용 |

### Agent 간 크로스뷰 규칙

Simon 구조의 단톡방 크로스뷰를 Funding Agent 구조에 적용:

**문제:** agent A의 결과를 agent B가 자동으로 인지하지 못함.  
**해결:** orchestrator(scheduler.py)가 중계. 각 agent는 결과를 DB에 저장 + orchestrator에 이벤트 발행.

```python
# 크로스뷰 패턴
# Discovery가 새 opportunity 발견 시:
entity_store.save_opportunity(opp)           # DB 저장
orchestrator.emit('new_opportunity', opp_id) # 이벤트 발행

# Orchestrator가 수신:
# → Verification agent 트리거
# → Matching agent 트리거 (verification 완료 후)
```

**루프 방지 규칙:**
- 각 agent는 자신이 생성한 이벤트에 반응하지 않음
- orchestrator가 이벤트 발신 agent와 수신 대상을 명시적으로 분리
- 동일 entity_id에 대한 동일 작업은 24시간 내 중복 실행 금지

---

## 메모리 시스템

Simon Seojoon Kim의 에이전트 기억 아키텍처를 적용.  
파일이 곧 존재다 — DB가 아니라 마크다운 파일 + git으로 관리.

| 파일 | 역할 | Simon 대응 |
|------|------|-----------|
| MEMORY.md | M0(영구)~M365(1년) 레이어 기억 | MEMORY.md |
| LESSONS.md | 실수 패턴 추출 누적 | compound/lessons.md |
| HEARTBEAT.md | 미해결 태스크 상태 추적 | HEARTBEAT.md |
| memory/YYYY-MM-DD.md | 일별 작업 일지 | memory/날짜.md |

### 기억 레이어 규칙

```
M0  (영구)   — 정체성, 핵심 원칙. 절대 만료 없음.
M365 (1년)   — 주요 설계 결정, 이정표. M90에서 승급.
M90  (90일)  — 분기 내 반복 중요 맥락. M30에서 2주 내 3회+ 참조 시 승급.
M30  (30일)  — 이번 달 작업 맥락. expires 태그 포함. 만료 시 야간 증류가 정리.
```

### 야간 증류 (Nightly Distill)

매일 23:00 cron 실행 (Phase 6 — scheduler.py에서 구현):
1. memory/오늘날짜.md 읽기
2. M30 항목 중 만료된 것 제거
3. 반복 중요 항목 승급 (M30 → M90 → M365)
4. MEMORY.md git commit: `nightly-distill: YYYY-MM-DD`

### LESSONS.md 작성 규칙

- **무엇을 씀:** 사건이 아니라 패턴. "X를 하면 Y가 깨진다 → 대신 Z를 할 것"
- **언제 씀:** 버그 수정 후, 설계 결정 번복 후, 같은 실수 2회째 발견 시
- **포맷:** 날짜, 패턴 제목, 규칙 1줄, 이유, 관련 파일

### HEARTBEAT.md 사용법

- 세션 시작 시 HEARTBEAT.md 확인 → 🔴 항목 먼저 처리
- 완료한 항목은 줄 삭제 → 완료 아카이브 테이블로 이동
- 새 미해결 사항 발생 시 추가 (날짜 포함)

---

## Git 커밋 규칙

기억 파일 변경은 커밋 메시지로 이력을 남긴다.  
커밋 로그 = 에이전트의 자서전.

```bash
# 메모리 업데이트
git commit -m "memory: YYYY-MM-DD 세션 — [작업 요약]"

# 야간 증류
git commit -m "nightly-distill: YYYY-MM-DD"

# 설계 결정 변경
git commit -m "decision: ADR-XXX — [결정 제목]"

# 버그 수정
git commit -m "fix: [파일명] — [버그 설명]"

# Phase 완료
git commit -m "phase-N: [Phase 설명] 완료"

# 기억 삭제 (최대한 피할 것)
git commit -m "memory-delete: [삭제 이유 명시]"
```

**원칙:** 기억은 삭제보다 만료 처리 우선. 삭제 시 커밋 메시지에 반드시 이유 기록.

---

## 세션 시작 체크리스트

새 Claude Code 세션 시작 시 순서대로 확인:

1. **HEARTBEAT.md** — 🔴 즉시 처리 항목 있는지
2. **MEMORY.md M30** — 현재 진행 중인 맥락 파악
3. **LESSONS.md** — 오늘 작업 관련 과거 실수 패턴 있는지
4. 현재 작업 중인 **Phase** 확인 (Current Implementation State)
5. 수정할 파일이 **Do Not Touch** 목록에 있는지
6. Telegram 명령 응답 코드가 **RULE-01** 준수하는지
7. 새 entity 생성 코드가 **RULE-02** 준수하는지

세션 종료 시:
1. memory/오늘날짜.md에 작업 내용 기록
2. HEARTBEAT.md 완료 항목 정리
3. LESSONS.md에 새 패턴 있으면 추가
4. git commit
