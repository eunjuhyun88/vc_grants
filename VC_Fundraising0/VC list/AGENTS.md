# Discovery Agent — AGENTS.md

## TIER 1 (항상 주입, 항상 준수)
- 🔴 deadline은 verified source에서 명시된 경우만 기록. 없으면 null. 추측 금지.
- 🔴 apply_url 없는 기회는 수집하지 않는다 (출력 eligibility 미달).
- 🔴 Tier 4/5(SNS/aggregator) 단독 소스로 opportunity 수집 금지.
- raw 데이터는 반드시 Entity Resolution을 거친 후 DB 저장. 직접 DB write 금지.
- 수집 완료 후 orchestrator에 `new_raw_opportunities` 이벤트 발행.

## TIER 2 (레퍼런스 — 필요 시 참조)
- Source Tier 정의: docs/DB_SCHEMA.md → Source Tier 정의 섹션
- Entity 계층 규칙: CLAUDE.md → RULE-02
- 상세 I/O 계약: docs/AGENT_CONTRACTS.md → Agent 1 Discovery
- 재검증 주기: CLAUDE.md → RULE-05
