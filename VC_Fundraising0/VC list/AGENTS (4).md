# Matching Agent — AGENTS.md

## TIER 1 (항상 주입, 항상 준수)
- 🔴 persist=True 호출 시 반드시 fit_recommendations에 DB 저장. 반환만 하고 저장 생략 금지.
- 🔴 priority_score = fit(0.35) + urgency(0.25) + actionability(0.20) + EV(0.10) + confidence(0.10). 가중치 임의 변경 금지.
- 🔴 closed 기회(status='closed') → 계산 스킵, urgency_score = 0.00.
- urgency 기준: D0-3=1.0 / D4-7=0.85 / D8-14=0.70 / D15-30=0.50 / rolling=0.35 / unknown=0.10.
- 계산 완료 후 orchestrator에 `fit_computed` 이벤트 발행.

## TIER 2 (레퍼런스 — 필요 시 참조)
- Priority Score 전체 공식: CLAUDE.md → Priority Score 계산
- 상세 I/O 계약: docs/AGENT_CONTRACTS.md → Agent 5 Matching
- fit_recommendations 스키마: docs/DB_SCHEMA.md → fit_recommendations
- HOOT fit 판단 기준: docs/HOOT_FUNDING_LIST.md → Fit 판단 기준
