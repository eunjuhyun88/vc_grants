# Feature Loop — 실전 프롬프트 템플릿

새 기능 시작 시 이 파일을 복사해서 채운다.
각 단계의 프롬프트를 그대로 Claude에게 붙여넣기.

---

## STEP 0: SPEC 작성 (사람이 작성)

파일 위치: `docs/product-specs/{FEATURE_NAME}_{YYYYMMDD}.md`

```markdown
# Feature Spec: {기능명}

| Version | Date | Author |
|---|---|---|
| 1.0 | YYYY-MM-DD | {작성자} |

## 한 줄 정의
[이 기능이 무엇을 하는가]

## 완료 기준 (Done = 이 모든 것이 통과)
- [ ] {측정 가능한 기준 1} — 예: "로딩 2초 이하"
- [ ] {측정 가능한 기준 2} — 예: "에러율 1% 미만"
- [ ] {측정 가능한 기준 3}

## 범위 밖 (이번에 하지 않을 것)
- {명시적 제외 항목 1}
- {명시적 제외 항목 2}

## 입력 / 출력
- 입력: {무엇을 받는가}
- 출력: {무엇을 반환/표시하는가}

## 엣지 케이스
- {케이스 1}: {처리 방법}
- {케이스 2}: {처리 방법}

## 깊이 레이어 (최소 3단계)
1. 기본 구현 — {무엇}
2. 엣지케이스 처리 — {무엇}
3. 성능 최적화 — {수치 목표}
```

---

## STEP 1: PLAN 작성 (사람이 작성 또는 Claude에게 요청)

파일 위치: `docs/exec-plans/active/{FEATURE_NAME}_{YYYYMMDD}.md`

### Plan 생성 프롬프트
```
[README.md 첨부]
[AGENTS.md 첨부]
[docs/README.md 첨부]
[ARCHITECTURE.md 첨부]
[docs/CONTEXT_ENGINEERING.md 첨부]
[해당 product-spec.md 첨부]

위 스펙을 기반으로 실행 계획을 작성해줘.
각 단계는:
- 독립적으로 완결 가능해야 함
- 완료 기준이 명확해야 함
- 이전 단계에만 의존해야 함

파일: docs/exec-plans/active/{FEATURE_NAME}_{YYYYMMDD}.md
형식: 아래 템플릿 사용
```

### Plan 파일 템플릿
```markdown
# Exec Plan: {기능명}

| Version | Date | Status |
|---|---|---|
| 1.0 | YYYY-MM-DD | active |

## 단계 목록

### Step 1: {단계명}
- 작업: {구체적 작업}
- 완료 기준: {이 단계의 done 정의}
- 산출물: {파일 또는 기능}
- Status: [ ] 대기 / [x] 완료

### Step 2: {단계명}
...

## 전체 완료 기준
→ product-spec.md의 완료 기준 전부 통과
```

---

## STEP 2: BUILD 프롬프트 (단계별 복사-붙여넣기)

### BUILD 단계 프롬프트 템플릿

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
첨부 파일:
- README.md
- AGENTS.md
- docs/README.md
- ARCHITECTURE.md
- docs/product-specs/{FEATURE_NAME}.md
- docs/exec-plans/active/{FEATURE_NAME}_{YYYYMMDD}.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

현재 단계: Step {N} / {전체}
단계명: {단계명}

## 이번 작업
{구체적 작업 내용}

## 완료 기준
- [ ] {기준 1}
- [ ] {기준 2}

## 범위 밖 (이 단계에서 하지 말 것)
- {명시적 제외}

## 관련 파일
- {파일 경로}: {용도}

## 완료 후
1. 완료 기준 달성 여부 직접 확인
2. docs/AGENT_WATCH_LOG.md에 진행 상황 기록
3. 필요하면 `npm run ctx:checkpoint -- --work-id "<W-ID>" --surface "<surface>" --objective "<objective>"`로 semantic memory 갱신
4. git commit: "feat({scope}): Step {N} — {단계명}"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## STEP 3: VERIFY 프롬프트

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[README.md 첨부]
[AGENTS.md 첨부]
[docs/README.md 첨부]
[해당 product-spec.md 첨부]

{기능명} 검증 요청.

체크 항목:
1. product-spec.md의 완료 기준 각각 통과 여부 확인
2. 린트 통과 여부 (아래 명령 실행)
3. 타입 에러 없음 확인

검증 명령:
  npm run lint        # 아키텍처 린트
  npm run typecheck   # 타입 체크
  npm test           # 테스트

통과하지 못한 항목이 있으면 수정 후 재검증.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## STEP 4: CLOSE 프롬프트

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[README.md 첨부]
[AGENTS.md 첨부]

{기능명} 완료 처리:

1. docs/exec-plans/active/{FEATURE_NAME}.md
   → docs/exec-plans/completed/ 로 이동
   Status를 "completed"로 업데이트

2. docs/AGENT_WATCH_LOG.md 업데이트:
   - 완료된 것과 검증 결과 기록
   - 다음 세션이 알아야 할 패턴/주의사항 기록

3. 재사용 가능한 패턴이 있으면:
   → `.claude/commands/` 또는 `.claude/agents/`로 승격 제안
   → 안정된 엔지니어링 규칙이면 canonical docs로 승격

코드 수정 금지. 파일 이동과 메모 업데이트만.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 컨텍스트 재시작 프롬프트 (세션 끊긴 후)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
첨부 파일:
- README.md
- AGENTS.md
- docs/README.md
- `.agent-context/briefs/*-latest.md` 또는 `.agent-context/handoffs/*-latest.md`가 있으면 첨부
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

이전 세션 이어서 진행.

최신 brief/handoff와 canonical docs를 기준으로:
1. 마지막 완료 단계 확인
2. 다음 단계 시작

추가 컨텍스트가 필요하면 요청해줘.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Compaction 프롬프트 (컨텍스트 창 80% 이상 시)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
지금까지의 대화를 압축해줘.

유지할 것:
- 아키텍처 결정사항 (무엇을 왜 결정했는가)
- 미해결 버그 또는 이슈
- 구현 세부사항 중 다음에 필요한 것
- 다음 단계 작업 포인터

제거할 것:
- 반복된 툴 호출 결과
- 이미 완료된 중간 출력
- 실패한 시도의 상세 로그

압축 결과는 chat에만 두지 말고 `npm run ctx:compact`를 사용해서 brief/handoff를 갱신해줘.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
