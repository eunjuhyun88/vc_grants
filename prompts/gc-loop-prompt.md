# GC 루프 — 실전 프롬프트

주기별로 아래 프롬프트를 그대로 붙여넣기.
코드는 수정하지 않음. 문서와 메모만 정리.

---

## 주간 GC (매주 금요일 또는 스프린트 종료)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
첨부: README.md, AGENTS.md, docs/README.md

주간 GC 실행. 코드 수정 금지. 문서/메모 정리만.

작업:
1. docs/exec-plans/active/ 확인
   → 완료된 항목: docs/exec-plans/completed/ 로 이동
   → 파일 내 Status를 "completed"로 업데이트

2. docs/AGENT_WATCH_LOG.md 확인
   → 반복되는 저신호 로그가 많으면 정리 제안
   → 완료된 작업이 canonical docs로 승격됐는지 확인

3. workspace/ 확인
   → 7일 이상 된 임시 파일 목록 출력 (삭제 여부는 내가 결정)

4. 작업 결과 요약 출력
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 격주 GC

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
첨부: README.md, AGENTS.md, docs/README.md

격주 GC 실행. 코드 수정 금지.

작업:
1. docs/ 스캔
   → Changelog가 30일 이상 미업데이트인 파일 목록 출력
   → [STALE] 헤더 추가 여부는 내가 결정

2. `.claude/commands/`와 `.claude/agents/` 확인
   → 실사용되지 않거나 너무 넓은 워크플로 항목 플래그
   → 정리 여부는 내가 결정

3. AGENTS.md 줄 수 확인
   → 100줄 초과 시 초과 내용 docs/로 이동 제안

4. docs/CLAUDE_COMPATIBILITY.md와 local `CLAUDE.md` 확인
   → 더 이상 맞지 않는 위험 안내가 있으면 갱신 제안

5. 작업 결과 요약 출력
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 월간 GC

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
첨부: README.md, AGENTS.md, docs/README.md, ARCHITECTURE.md

월간 GC 실행. 코드 수정 금지.

작업:
1. ARCHITECTURE.md ↔ 실제 src/ 구조 정합성 확인
   → 문서에 있는데 실제 디렉토리 없는 항목
   → 실제 디렉토리 있는데 문서에 없는 항목
   → 불일치 목록 출력 (수정 여부는 내가 결정)

2. generated context 신선도 확인
   → `docs/generated/legacy-doc-audit.md`와 `docs/generated/context-contract-report.md` 기준으로 stale 항목 목록 출력
   → [DEPRECATED] 표시 여부는 내가 결정

3. context memory compaction 상태 확인
   → `.agent-context/briefs/*-latest.md`, `.agent-context/handoffs/*-latest.md` 존재 여부 확인
   → 필요 시 `npm run ctx:compact` 제안

4. docs/CLAUDE_COMPATIBILITY.md 및 local `CLAUDE.md` 검토
   → 더 이상 유효하지 않은 위험 안내 플래그

5. 작업 결과 요약 + 다음 달 주의사항 출력
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Context Compaction 프롬프트 (독립 실행)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
첨부: 최신 brief/handoff 또는 checkpoint

Context artifact 압축.

유지할 것:
- 미완료 작업 전체
- 발견된 패턴 / 주의사항 (재발 방지 필요한 것)
- 미결 결정 전체
- 다음 세션 시작 포인트

제거 / 압축할 것:
- 완료된 항목 (날짜만 남기고 상세 제거)
- 반복된 동일 패턴 (한 줄로 합치기)

압축 결과 미리보기 출력 후 `npm run ctx:compact`로 갱신할지 제안해줘.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
