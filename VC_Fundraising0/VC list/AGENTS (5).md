# Monitoring Agent — AGENTS.md

## TIER 1 (항상 주입, 항상 준수)
- 🔴 deadline 변경 감지 → 기존 opportunity UPDATE + change_events 기록. 새 row 생성 금지.
- 🔴 change_events DB 저장 완료 후에만 알림 발행. 저장 없는 알림 금지.
- 🔴 동일 entity_id + 동일 change_type → 24시간 내 중복 기록 금지.
- 재검증 주기 준수: deadline ≤ 14일=6h / unknown=12h / open·rolling=24h / closed=72h.

## TIER 2 (레퍼런스 — 필요 시 참조)
- change_events 스키마: docs/DB_SCHEMA.md → change_events
- 상세 I/O 계약: docs/AGENT_CONTRACTS.md → Agent 6 Monitoring
- 재검증 주기 전체: CLAUDE.md → RULE-05
