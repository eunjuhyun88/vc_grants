# Design Documents Index

## Core Design Docs

| 문서 | 설명 |
|------|------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 시스템 토폴로지, agent composition, data pipeline, runtime boundary |
| [DB_SCHEMA.md](DB_SCHEMA.md) | SQLite MVP schema reference, persistence mapping |
| [AGENT_CONTRACTS.md](AGENT_CONTRACTS.md) | 7 Agent I/O 계약, 실행 계층 |
| [TELEGRAM_UX.md](TELEGRAM_UX.md) | Telegram 명령 UX, 대화 흐름, 알림/에러/empty state 계약 |
| [TELEGRAM_COMMAND_SPEC.md](TELEGRAM_COMMAND_SPEC.md) | active/planned Telegram command contract와 deterministic/reasoned 경계 |
| [OUTPUT_RULES.md](OUTPUT_RULES.md) | Telegram 출력 규칙, Eligibility Filter, Output DTO |
| [OPERATIONS_MODEL.md](OPERATIONS_MODEL.md) | Discovery/Verification cadence, alert gating, human review 운영 모델 |
| [ENTITY_MODEL.md](ENTITY_MODEL.md) | canonical data vocabulary, state axes, display mapping, dedup rules |
| [PRIORITY_ALGORITHM.md](PRIORITY_ALGORITHM.md) | canonical scoring contract, confidence/actionability, intent-aware ranking |
| [DATA_FILL_SPEC.md](DATA_FILL_SPEC.md) | user-provided spreadsheets/CSVs를 canonical entities와 seed DB로 채우는 규칙 |
| [SOCIAL_DISCOVERY.md](SOCIAL_DISCOVERY.md) | X/Twitter를 finding source로 쓰는 runtime contract, FxTwitter/LunarCrush 역할 분리 |
| [AUTORESEARCH_ADOPTION.md](AUTORESEARCH_ADOPTION.md) | goal-driven self-improving discovery loop, benchmark harness, mutable policy boundary |

## Reference

- [core-beliefs.md](core-beliefs.md) — memento-kit 기본 신념
