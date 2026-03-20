# Verification Agent — AGENTS.md

## TIER 1 (항상 주입, 항상 준수)
- 🔴 Tier 4/5(SNS/aggregator) 단독 소스 → output_status = 'pending' 고정. verified 부여 금지.
- 🔴 deadline 소스 없음 → null 유지. 추측·보간 절대 금지.
- 🔴 output_status = 'verified' 조건: Tier 1/2 소스 + confidence ≥ 0.75 (grants/cohorts), ≥ 0.70 (funds).
- 재검증 주기 준수: deadline ≤ 14일=6h / unknown=12h / open·rolling=24h / closed=72h.
- 검증 완료 후 orchestrator에 `verification_complete` 이벤트 발행.

## TIER 2 (레퍼런스 — 필요 시 참조)
- Source Tier 정의 및 confidence weight: docs/DB_SCHEMA.md → Source Tier 정의
- Output Eligibility 전체 기준: docs/OUTPUT_RULES.md → Eligibility Filter
- 상세 I/O 계약: docs/AGENT_CONTRACTS.md → Agent 3 Verification
- 설계 결정 ADR-005: docs/DECISIONS.md
