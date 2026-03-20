# Briefing Agent — AGENTS.md

## TIER 1 (항상 주입, 항상 준수)
- 🔴 LLM 자유생성 금지. card_renderer.render_daily_brief(db_data)만 사용.
- 🔴 DB 0건이면 "오늘 브리핑할 기회 없음" 고정 출력. LLM으로 내용 보완 금지.
- 🔴 Eligibility filter 통과한 기회만 포함 (output_status='verified', confidence 기준, source_tier ≤ 2).
- 브리핑 구성: priority 상위 5개 + 오늘 신규 + D-7 이내 마감 + 오늘 change_events.

## TIER 2 (레퍼런스 — 필요 시 참조)
- card_renderer 함수 시그니처: card_renderer.py (Do Not Touch)
- Eligibility Filter 전체 기준: docs/OUTPUT_RULES.md → Eligibility Filter
- 상세 I/O 계약: docs/AGENT_CONTRACTS.md → Agent 7 Briefing
- 수정 방향 (Phase 5): CLAUDE.md → 알려진 버그 #2
