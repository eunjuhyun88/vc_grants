# Funding Intelligence Agent — HEARTBEAT.md

> 크론이 시간축이라면 HEARTBEAT는 상태축.
> "지금 당장은 아닌데 조만간 처리해야 할 것"을 추적.
> Claude Code 세션 시작 시 이 파일 확인 → 미해결 항목 처리 → 완료 시 해당 줄 삭제.
> 항목 추가 시: `- [YYYY-MM-DD 추가] 내용 — 처리 기준`

---

## 🔴 즉시 처리 필요

- [2026-03-08 추가] Monad Mach Accelerator 2026 마감일 미확인 — 3월 14일 신청 전 deadline 확인 필수. https://monad.xyz/mach
- [2026-03-08 추가] Alliance Accelerator 현재 cohort 모집 여부 미확인 — docs/HOOT_FUNDING_LIST.md priority 1번 항목. https://alliance.xyz/apply

---

## 🟡 이번 Phase 처리

- [2026-03-08 추가] Phase 1 미완료 — entity_store.py에 fit_recommendations + change_events + organization_aliases 테이블 추가
- [2026-03-08 추가] Phase 2 미완료 — matching_agent.py: evaluate(persist=True) + batch_rank()
- [2026-03-08 추가] Phase 3 미완료 — monitoring_agent.py: change_events DB 저장 + /changes 연결
- [2026-03-08 추가] Phase 4 미완료 — entity_resolution.py 신규 생성
- [2026-03-08 추가] Phase 5 미완료 — telegram_bot.py LLM 자유생성 제거
- [2026-03-08 추가] Phase 6 미완료 — scheduler.py + deploy.sh

---

## 🟢 백로그 (나중에)

- [2026-03-08 추가] 벡터 검색 추가 — SQLite + text-embedding 기반 오래된 기억 검색 (Phase 6 이후)
- [2026-03-08 추가] DB SQLite → Postgres 전환 (Railway 배포 시점에)
- [2026-03-08 추가] HOOT_FUNDING_LIST.md priority_score 실측값으로 교체 — matching_agent 완성 후

---

## 완료된 항목 아카이브

| 날짜 완료 | 항목 |
|----------|------|
| 2026-03-08 | 설계 문서 6개 + CLAUDE.md 생성 완료 |
| 2026-03-08 | MEMORY.md + LESSONS.md + HEARTBEAT.md 생성 완료 |
