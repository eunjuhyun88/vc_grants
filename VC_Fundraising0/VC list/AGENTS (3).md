# Research Agent — AGENTS.md

## TIER 1 (항상 주입, 항상 준수)
- 🔴 LLM 허용하되 PROVIDED_FACTS(실제 소스에서 확인된 데이터)만 사용. 외부 상식으로 채우기 금지.
- 🔴 추측 데이터는 반드시 confidence < 0.7로 마킹.
- 소스: 공식 사이트 → Crunchbase → LinkedIn 순서로 우선순위. SNS는 보조 참조만.
- 수집 완료 후 orchestrator에 `dossier_updated` 이벤트 발행.

## TIER 2 (레퍼런스 — 필요 시 참조)
- 상세 I/O 계약: docs/AGENT_CONTRACTS.md → Agent 4 Research
- organization_dossiers 스키마: docs/DB_SCHEMA.md → organization_dossiers
