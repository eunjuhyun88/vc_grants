# Product Specs — Funding Intelligence Agent

> **이 시스템은 AI Agent System이다.** Telegram은 output interface일 뿐.

## Source of Truth

**[PRD.md](PRD.md)** — 요구사항 명세서. 다른 문서와 충돌 시 PRD 우선.

## 개발 순서대로 읽기

| 순서 | 문서 | 내용 |
|------|------|------|
| 0 | [PRD.md](PRD.md) | 요구사항 명세서 (source of truth) |
| 1 | [DEV_SETUP.md](DEV_SETUP.md) | Python 환경, 의존성, 디렉토리 구조, 실행 방법 |
| 2 | [TYPES_SPEC.md](TYPES_SPEC.md) | Enum, Dataclass, Output DTO, Agent I/O 타입, 유틸 함수 |
| 3 | [DB_SPEC.md](DB_SPEC.md) | Config, EntityStore 함수 시그니처, SQL 쿼리, Seed 데이터 |
| 4 | [AGENTS_SPEC.md](AGENTS_SPEC.md) | BaseAgent, Discovery, Verification, Matching, 나머지 agent |
| 5 | [BOT_SPEC.md](BOT_SPEC.md) | Output interface (Telegram), 핸들러, card_renderer |
| 6 | [PIPELINE_SPEC.md](PIPELINE_SPEC.md) | 파이프라인 오케스트레이션, 스케줄러, CLI, 에러 복구 |

## 개념 설계 (참조)

- `docs/design-docs/` — Entity 모델, Agent 계약, Priority 알고리즘, Output 규칙
- `docs/SYSTEM_INTENT.md` — 시스템 목적, 불변 원칙
