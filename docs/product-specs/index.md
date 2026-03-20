# Product Specs — Funding Intelligence Agent

> **이 시스템은 AI Agent System이다.** Telegram은 primary user interface이고, authority는 repo-local canonical docs와 DB facts에 있다.

## Source of Truth

**[core.md](core.md)** — 현재 active surface spec.
**[PRD.md](PRD.md)** — 상세 요구사항, entity vocabulary, pipeline requirements.

`core.md`는 현재 Telegram surface behavior를 우선 정의하고, `PRD.md`는 제품 문제, v1 범위, success criteria를 정의한다.
세부 data / scoring / command contract는 `docs/design-docs/*.md`가 authority다.

## Active Read Order

| 순서 | 문서 | 내용 |
|------|------|------|
| 0 | [core.md](core.md) | 현재 active product surface spec |
| 1 | [PRD.md](PRD.md) | 제품 문제, 목표, v1 범위, success criteria |
| 2 | [../design-docs/TELEGRAM_COMMAND_SPEC.md](../design-docs/TELEGRAM_COMMAND_SPEC.md) | command lifecycle와 active/planned command contract |
| 3 | [../design-docs/ENTITY_MODEL.md](../design-docs/ENTITY_MODEL.md) | canonical data vocabulary와 state axes |
| 4 | [../design-docs/PRIORITY_ALGORITHM.md](../design-docs/PRIORITY_ALGORITHM.md) | scoring, intent-aware ranking, explanation rules |
| 5 | [../design-docs/OPERATIONS_MODEL.md](../design-docs/OPERATIONS_MODEL.md) | monitoring, verification cadence, alert gating |
| 6 | [../design-docs/OUTPUT_RULES.md](../design-docs/OUTPUT_RULES.md) | deterministic output eligibility와 rendering contract |
| 7 | [BOT_SPEC.md](BOT_SPEC.md) | implementation reference |
| 8 | [PIPELINE_SPEC.md](PIPELINE_SPEC.md) | implementation reference |
| 9 | [AGENTS_SPEC.md](AGENTS_SPEC.md) | implementation reference |
| 10 | [DB_SPEC.md](DB_SPEC.md) | implementation reference |
| 11 | [TYPES_SPEC.md](TYPES_SPEC.md) | implementation reference |
| 12 | [DEV_SETUP.md](DEV_SETUP.md) | 로컬 개발 setup reference |

## 개념 설계 (참조)

- `docs/design-docs/` — Entity 모델, command 계약, scoring, operations, output 규칙
- `docs/SYSTEM_INTENT.md` — 시스템 목적, 불변 원칙
