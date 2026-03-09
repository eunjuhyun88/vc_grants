# System Intent — Funding Intelligence Agent

## Product Thesis

개인/팀이 **자신의 프로젝트를 등록**하면, 그 프로젝트에 맞는 펀딩 기회(VC·Grant·Accelerator·Ecosystem Program)를 **AI agent가 자동으로 수집·검증·분석·우선순위 산출**하고 **지속적으로 팔로업**해주는 시스템. Telegram은 output interface일 뿐, **핵심은 AI Agent System**.

> **Funding Intelligence Agent = market scanning + opportunity analysis + strategic recommendation**
> 단순한 크롤러가 아니다.

**핵심 차별점:**
- 규칙 기반 스크래퍼가 아닌, 조직을 이해하고 fit을 판단하는 AI agent 시스템
- 특정 회사 전용이 아닌, **누구나 자기 프로젝트를 등록하면 맞춤 추천**
- 한번 찾고 끝이 아닌, **지속적 모니터링 + 변화 감지 + 팔로업**

## 사용 시나리오

1. 사용자가 자기 프로젝트 프로필 등록 (이름, 단계, 섹터 태그, 설명)
2. Agent가 프로필 기반으로 펀딩 기회 탐색 + 검증 + fit score 계산
3. Telegram으로 우선순위 높은 기회 알림
4. 마감일·상태 변화 모니터링 → 자동 알림
5. 사용자는 /grants, /cohorts, /funds로 언제든 현황 조회

## Seed User: HOOT (첫 번째 등록 프로필)

| 항목 | 값 |
|------|-----|
| 회사 | Holo Studio Co., Ltd. |
| 위치 | Korea |
| 단계 | Seed (MVP) |
| 주력 | HOOT — 개인 데이터 기반 소형모델 학습 + 분산 컴퓨팅 + 블록체인 coordination |
| 섹터 | ai_infra, decentralized_ai, crypto_infra, distributed_compute, personal_model_training |
| 프로젝트 우선순위 | HOOT > StockClaw > MoltVC > PlayArts > ClawGene |

## Non-Negotiable Invariants

1. **Fact ≠ AI Reasoning 분리** — deadline·status·apply_url·amount = source-backed facts. fit·thesis·recommendation = AI reasoning. 혼합 금지.
2. **목록 명령에서 LLM 호출 금지** — /grants, /cohorts, /funds는 DB → filter → renderer만. LLM 자유생성 절대 금지.
3. **DB 0건 = "데이터 없음" 고정 출력** — LLM이 상식으로 보완하는 것 금지 (Techstars 마감일 추측 등).
4. **Program 없이 Opportunity 생성 불가** — Entity 계층: Organization → Program → Opportunity.
5. **Deadline 추측 생성 금지** — 검증 불가 시 null 유지.
6. **Output eligibility filter 필수** — verified + confidence ≥ 0.75 + source_tier ≤ 2 + apply_url 있음 + status ≠ closed.
7. **Canonical docs가 chat history보다 우선** — 에이전트는 이 문서만으로 reasoning 가능해야 함.

## Current Constraints

- **스택:** Python (AI agents) + SQLite (DB) + Telegram (output interface)
- **배포:** 로컬 → Railway (예정)
- **DB 전환:** SQLite → Postgres (Phase 후반)
- **1인 개발:** EJ 단독. 자동화 최우선.
- **MVP 우선:** 7개 agent 중 핵심 3개 먼저 (Discovery, Verification, Matching)
