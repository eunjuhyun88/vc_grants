# NOTES.md — 현재 상태

## 마지막 작업 (2026-03-09)

### 완료
- memento-kit 설치 + agent memory workspace 설치
- 개념 설계 문서 7개 (`docs/design-docs/`)
- MVP 구현 계획 (`docs/exec-plans/active/MVP_IMPLEMENTATION.md`)
- **PRD 저장** (`docs/product-specs/PRD.md`) — source of truth
- **개발용 설계 문서 6개** (`docs/product-specs/`):
  - DEV_SETUP.md — 환경, 의존성, 디렉토리 구조
  - TYPES_SPEC.md — 모든 Enum, Dataclass, DTO, 유틸 함수
  - DB_SPEC.md — EntityStore 전체 함수 시그니처, SQL, Seed 데이터
  - AGENTS_SPEC.md — BaseAgent + 7 Agent 구현 명세
  - BOT_SPEC.md — Output interface (Telegram), 핸들러, card_renderer
  - PIPELINE_SPEC.md — 오케스트레이션, 스케줄러, CLI, 에러 복구
- **PRD 기준으로 설계 문서 정렬 완료:**
  - "bot" → "AI Agent System" (Telegram은 output interface)
  - Priority: fit*0.35 + urgency*0.35 + value*0.15 + confidence*0.15 (4-factor)
  - Categories: grant, accelerator, vc_cohort, ecosystem_builder (4개)
  - src/bot/ → src/interface/ (디렉토리명 변경)
- **PRD 기준 교차 검증 완료 (13 Critical + 10 Moderate + 2 Minor 수정):**
  - AGENT_CONTRACTS.md: 4-factor priority, urgency PRD값, actionability 제거, category 4개
  - DB_SCHEMA.md: actionability 컬럼 제거, category enum 4개
  - ARCHITECTURE.md (design-docs): category 4개, bot→interface 경로, Telegram Interface 명칭
  - ENTITY_MODEL.md: category 6→4, org_type/category 독립성 명시
  - OUTPUT_RULES.md: category 주석 4개로 수정
  - PRIORITY_ALGORITHM.md: batch_rank actionability 참조 제거
  - AGENTS_SPEC.md: LLM 프롬프트 category 4개
  - PIPELINE_SPEC.md: CLI choices 4개, 사용 예시 수정
  - BOT_SPEC.md: 전체 src/bot/ → src/interface/, easiest_to_apply intent 제거
  - MVP_IMPLEMENTATION.md: Phase 4 Output Interface, src/interface/ 경로
  - root ARCHITECTURE.md: system map 경로 interface/로 수정
  - CLAUDE.md: summary에 Ecosystem Builder 포함
  - PRD.md: Section 4 program_type → category 일관성 수정
  - DEV_SETUP.md: deterministic/reasoned 명령별 agent 호출 규칙 명시

## 다음 시작 포인트

**Phase 1 구현 시작 — `docs/product-specs/` 순서대로:**
1. `src/core/types.py` ← TYPES_SPEC.md 그대로 구현
2. `src/core/config.py` ← DB_SPEC.md Config 클래스
3. `src/core/errors.py` ← DEV_SETUP.md 에러 패턴
4. `src/db/schema.sql` ← DB_SCHEMA.md DDL
5. `src/db/entity_store.py` ← DB_SPEC.md 함수 시그니처
6. `data/seed/hoot_profile.json` ← DB_SPEC.md Seed Data
7. `tests/test_entity_store.py` ← DB_SPEC.md 테스트 케이스

## 막힌 지점

없음. 설계 완료, 구현 시작 가능.

## 참고

- 개념 설계: `docs/design-docs/` (Entity 모델, Agent 계약, Priority 알고리즘)
- 개발 설계: `docs/product-specs/` (함수 시그니처, 테스트 케이스, 에러 처리)
- 이전 작업: `VC_Fundraising0/VC list/` (참고만, 코드 재사용 안 함)
