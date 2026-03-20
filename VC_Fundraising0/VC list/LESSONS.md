# Funding Intelligence Agent — LESSONS.md

> 사건(what happened)이 아니라 패턴(what to do differently)을 기록하는 파일.
> 사건은 memory/YYYY-MM-DD.md에 기록.
> 이 파일은 compound 지식 — 반복하면 안 되는 실수의 추출된 규칙.
> Claude Code 세션 시작 시 자동 참조. 같은 실수 반복 전에 먼저 이 파일 확인.

---

## 포맷

```
## [YYYY-MM-DD] 패턴 제목
- 규칙: [한 줄로 된 행동 지침]
- 이유: [왜 이 규칙이 필요한지 — 실제 발생한 문제]
- 관련 파일: [어떤 파일/함수에서 발생했는지]
```

---

## [2026-03-08] /grants 등 목록 명령 LLM 자유생성 패턴

- **규칙:** 목록 조회 명령(/grants /cohorts /funds /all /ranking /changes)에서 LLM 호출 금지. DB → formatter → output만.
- **이유:** /grants 입력 시 "Techstars 마감일은 매년 1월..." 같은 LLM 일반 상식 응답이 출력됨. DB 데이터가 system prompt에 주입 안 된 상태에서 LLM이 자유생성 경로를 탐.
- **관련 파일:** telegram_bot.py — 목록 명령 핸들러
- **수정 위치:** Phase 5

---

## [2026-03-08] deadline 없는 rolling grant 삭제 패턴

- **규칙:** `deadline_at = null`인 opportunity를 오류로 보고 삭제하거나 임의 날짜를 채우지 말 것.
- **이유:** rolling grant는 deadline이 없는 것이 정상 상태. null 허용이 설계 의도.
- **관련 파일:** entity_store.py — opportunity CRUD, verification_agent.py
- **참조:** ADR-003 (docs/DECISIONS.md)

---

## [2026-03-08] Organization 없이 Program 생성 시도 패턴

- **규칙:** Program 생성 전 Organization이 존재하는지 반드시 확인. 없으면 Organization 먼저 생성.
- **이유:** entity 계층 Organization → Program → Opportunity를 건너뛰면 dedup·fit 계산 전체가 망가짐.
- **관련 파일:** entity_store.py — create_program()
- **참조:** ADR-002 (docs/DECISIONS.md)

---

## [2026-03-08] confidence 0.85 미만 auto merge 패턴

- **규칙:** confidence < 0.85인 entity는 review_queue로 보내고 강제 merge 금지.
- **이유:** false positive merge 발생 시 Organization/Program 데이터 오염. 보수적 기준 필요.
- **관련 파일:** entity_resolution.py (Phase 4 미구현)
- **참조:** ADR-006 (docs/DECISIONS.md)

---

_이하 Phase 진행하면서 추가_
