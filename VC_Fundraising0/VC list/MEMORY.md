# Funding Intelligence Agent — MEMORY.md

> 이 파일은 에이전트의 장기 기억이다.
> 야간 증류(nightly distill) cron이 매일 자동 업데이트.
> 수동 수정 시 반드시 git commit 메시지에 이유 기록.
> 삭제보다 만료 처리 우선. 기억 삭제는 git history에 흔적 남김.

---

## 🔴 M0 — 코어 메모리 (영구, 만료 없음)

> 절대 바뀌지 않는 정체성과 핵심 규칙.

- 이 시스템은 Holo Studio의 펀딩 기회 인텔리전스 에이전트다
- 운영자: Eunjoo (jkbaek@hololabster.co), Product Owner & Chief Builder
- 프로젝트 우선순위: HOOT > StockClaw > MoltVC > PlayArts > ClawGene
- 핵심 원칙: 목록 명령에서 LLM 자유생성 절대 금지. DB → formatter → output만.
- 핵심 원칙: deadline은 verified source 없으면 null. 추측 보간 금지.
- 핵심 원칙: Opportunity는 Program 없이 생성 불가.

---

## 🌳 M365 — 1년 기억

> 장기적으로 중요한 설계 결정, 주요 이정표.
> M90에서 반복적으로 중요했던 것이 승급.

- [2026-03-08] 프로젝트 시작. 6개 설계 문서 + CLAUDE.md 완성. Phase 1~6 로드맵 확정.
- [2026-03-08] 2-layer 아키텍처 확정: Fact Engine(하위) + AI Agent Layer(상위). ADR-010.
- [2026-03-08] Priority Score 가중치 확정: fit(0.35) + urgency(0.25) + actionability(0.20) + EV(0.10) + confidence(0.10). ADR-009.

---

## 📚 M90 — 90일 기억

> 지난 분기 내 중요 결정, 반복 참조된 맥락.
> M30에서 2주 내 3회 이상 참조 시 승급.
> <!-- expires: 해당 없음 (신규) -->

_현재 비어 있음. Phase 진행하면서 채워질 예정._

---

## 📝 M30 — 30일 기억

> 이번 달 주요 작업, 현재 진행 중인 맥락.
> 만료일 지나면 야간 증류가 정리.

- [2026-03-08] Phase 1 시작 전 상태: entity_store.py에 fit_recommendations + change_events + organization_aliases 3개 테이블 미구현. <!-- expires: 2026-04-08 -->
- [2026-03-08] 핵심 버그: /grants 등 목록 명령이 LLM 자유생성 경로를 탐 — Phase 5 수정 전까지 목록 명령 결과 신뢰 불가. <!-- expires: 2026-04-08 -->
- [2026-03-08] Monad Mach Accelerator 마감일 미확인 상태. 3월 14일 이전 확인 필요. <!-- expires: 2026-03-20 -->

---

## 🗓️ 야간 증류 로그

> nightly-distill cron이 실행될 때마다 한 줄 기록.

| 날짜 | 요약 |
|------|------|
| 2026-03-08 | 초기 설정. M0 + M365 + M30 초기값 입력. |
