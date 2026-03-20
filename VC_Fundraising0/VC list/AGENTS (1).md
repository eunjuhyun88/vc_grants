# Entity Resolution Agent — AGENTS.md

## TIER 1 (항상 주입, 항상 준수)
- 🔴 confidence ≥ 0.85 → auto merge. confidence < 0.85 → review_queue 이동, 강제 merge 절대 금지.
- 🔴 Program 없이 Opportunity 생성 금지. Organization → Program → Opportunity 순서 필수.
- 🔴 URL normalization 필수: query string 제거, trailing slash 제거, http→https.
- deadline 변경은 기존 record UPDATE만. 새 row 생성 금지.
- 처리 완료 후 orchestrator에 `entity_resolved` 이벤트 발행 (Verification 트리거용).

## TIER 2 (레퍼런스 — 필요 시 참조)
- Dedup 3단계 규칙: docs/DB_SCHEMA.md → Dedup 규칙 요약
- 상세 I/O 계약: docs/AGENT_CONTRACTS.md → Agent 2 Entity Resolution
- 설계 결정 ADR-002, ADR-003, ADR-004, ADR-006: docs/DECISIONS.md
