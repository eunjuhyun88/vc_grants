# Funding Intelligence Agent — Architecture

## 1. System Goal

이 시스템은 `Startup Funding Intelligence System`이다.

핵심 기능:

- discover opportunities
- track deadlines and status
- analyze fit
- recommend funding

Telegram은 primary user interface이고, 시스템 본체는 agent pipeline + database + ranking logic이다.

## 2. Overall Structure

```text
Internet Sources
      ->
Discovery Agent
      ->
Entity Resolution Agent
      ->
Verification Agent
      ->
Funding Database
      ->
Matching Agent
      ->
Monitoring Agent
      ->
Output Interface (Telegram first, optional future dashboard/API)
```

## 3. Agent Composition

### 3.1 Discovery Agent

역할:

- 새로운 funding program과 opportunity를 발견한다

검색 대상:

- accelerator
- startup cohort
- builder program
- grant program
- ecosystem funding

검색 예:

- `web3 accelerator apply`
- `crypto builder program`
- `AI startup grant`

주요 소스:

- search engine results
- ecosystem websites
- VC websites
- hackathon sites
- startup communities

출력 예:

```json
{
  "organization": "Monad",
  "program": "Nitro Accelerator",
  "url": "https://nitroacc.xyz"
}
```

### 3.2 Entity Resolution Agent

문제:

- 같은 프로그램이 여러 이름으로 발견된다

예:

- `a16z speedrun`
- `speedrun accelerator`
- `speedrun.xyz`

역할:

- normalize name
- match domain
- resolve alias
- decide create vs merge vs review

출력 예:

```json
{
  "organization_id": "org_a16z",
  "program_id": "prg_speedrun"
}
```

### 3.3 Verification Agent

역할:

- 프로그램 정보를 검증한다

검증 대상:

- deadline
- apply_url
- funding_amount
- program_type
- recruiting status

추가 규칙:

- external form URL 단독으로는 verified/actionable로 승격하지 않는다
- 공식 program/apply surface가 현재 opportunity 맥락을 같이 확인해야 한다
- generic funding/build URL만으로 `open`을 추정하지 않는다
- direct apply surface라도 current intake/window evidence가 없으면 actionable로 승격하지 않는다
- user-facing 출력은 verified active endpoint가 있는 기회만 통과한다

출력 예:

```json
{
  "status": "open",
  "deadline": "2026-03-14",
  "apply_url": "https://nitroacc.xyz/apply"
}
```

### 3.4 Matching Agent

역할:

- startup profile과 opportunity를 매칭한다

입력:

- `company_profile`
- `opportunity`

fit 계산 요소:

- sector match
- stage match
- ecosystem match

출력 예:

```json
{
  "fit_score": 0.82,
  "priority_score": 0.75
}
```

### 3.5 Monitoring Agent

역할:

- 프로그램 상태 변경을 추적한다

예:

- deadline 변경
- program closed
- apply form 변경

주기:

- `deadline < 14 days -> 6 hours`
- `open programs -> 24 hours`
- `closed -> 72 hours`

출력 예:

```json
{
  "change": "deadline updated"
}
```

### 3.6 Research Agent

역할:

- organization, partner ecosystem, thesis, portfolio에 대한 dossier를 수집한다

주요 용도:

- `/org`
- `/research`
- fit explanation 보강

제약:

- source-backed facts를 기반으로만 reasoning한다
- deterministic list output의 prerequisite가 되면 안 된다

### 3.7 Briefing Agent

역할:

- 사용자가 빠르게 읽을 수 있는 daily funding brief를 생성한다

구성 요소:

- urgent deadlines
- new programs
- top ranked opportunities
- recent changes

제약:

- brief는 DB facts와 precomputed ranking만 사용한다
- 자유 생성형 general commentary로 확장하지 않는다

### 3.8 Actionable Funding Service

역할:

- `/funding`, `/funding_for_project`, `/funding_map`가 같은 user-facing 경로를 타게 한다
- ranked result를 card로 변환하고 registry enrichment를 붙인다
- current/actionable filter와 strategy-entry readiness를 한 곳에서 강제한다
- runtime profile identity repair를 통해 malformed stored profile이 surface를 망치지 않게 한다

핵심 이유:

- handler별 drift를 막는다
- research surface와 deterministic funding surface가 같은 eligibility contract를 공유한다
- verified endpoint가 없는 row가 presentation 단계에서 다시 살아나는 것을 막는다
- `Infra/null` 같은 generic project identity가 추천/맵/dossier 출력으로 전파되는 것을 막는다
- 지난 intake나 weak apply page가 ranking budget을 쓰기 전에 current/actionable gate에서 탈락하게 한다

## 4. Database Layer

주요 테이블:

### organizations

- `id`
- `name`
- `type`
- `website`

### programs

- `id`
- `organization_id`
- `program_name`
- `program_type`

### opportunities

- `id`
- `program_id`
- `status`
- `deadline`
- `apply_url`
- `funding_amount`

### observations

- 근거 데이터
- `source_url`
- `page_text`
- `confidence`

추가 구현 테이블은 repo schema를 따른다.

## 5. Data Pipeline

Funding Agent 실행 흐름:

1. Discovery
2. Entity resolution
3. Verification
4. Store database
5. Matching
6. Monitoring
7. Output

### User-Facing Pipeline

```text
verified opportunities
  -> verified endpoint sync
  -> actionable funding service
  -> eligibility filter
  -> ranking/sort or funding map/dossier shaping
  -> card renderer
  -> Telegram response or alert
```

## 6. Output Layer

### Output Channels

- Telegram bot
- future dashboard
- future API

### Telegram Commands

- `/grants`
- `/cohorts`
- `/funds`
- `/all`
- `/brief`

예:

```text
Nitro Accelerator (Monad)

Funding
$500k

Deadline
2026-03-14 (D-5)

Apply
https://nitroacc.xyz
```

## 7. Priority Engine

```text
priority_score =
  fit_score * 0.35 +
  urgency * 0.25 +
  actionability * 0.20 +
  expected_value * 0.10 +
  confidence * 0.10
```

실제 구현은 5-factor priority contract를 따른다.

## 8. Discovery Sources

주요 사이트군:

### VC

- a16z
- paradigm
- dragonfly
- electric capital

### Accelerators

- speedrun.xyz
- alliance.xyz
- outlierventures.io
- encode.club

### Ecosystem

- solana.org
- arbitrum.foundation
- polygon.technology

### Hackathons / Community Feeders

- colosseum.org
- ethglobal.com
- encode.club

## 9. AI Components And Boundaries

### LLM Allowed

- program thesis 분석
- fit score reasoning
- priority explanation

### LLM Forbidden

- deadline 생성
- funding amount 추측
- apply_url 생성

즉, 시스템은 `fact engine + reasoning engine`을 분리한다.

## 10. Repo Implementation Mapping

현재 repo 기준 핵심 구현 경로:

```text
src/agents/          # discovery, verification, matching
src/db/              # schema and entity store
src/core/pipeline.py # orchestration
src/interface/       # Telegram handlers and rendering
```

권장 의존성 방향:

```text
types -> db -> agents -> interface
```

agent가 다른 agent를 직접 호출하지 않고 orchestrator를 통해 연결되는 구조를 유지한다.

## 11. Runtime And Deployment Baseline

### Current Baseline

- Python
- SQLite
- async Telegram bot
- HTML parsing / HTTP fetch

### Planned Evolution

- Postgres
- scheduler / worker separation
- optional dashboard or API surface

다음 스택들은 후보일 뿐, 현재 canonical commitment는 아니다.

- FastAPI
- Playwright
- Serper API
- LangGraph
- Celery

## 12. Scaling And Future Extensions

추가 기능:

- submission tracker
- application status (`submitted`, `interview`, `accepted`)
- auto outreach
- investor email / intro request workflow
- deck generator
- grant proposal / accelerator application support

## 13. Non-Negotiable Architecture Rules

1. Program 없이 Opportunity 생성 금지
2. source-backed facts와 AI reasoning 분리
3. deterministic output path에서 LLM 호출 금지
4. monitoring과 alert dispatch는 noise gate를 통과해야 함
5. Telegram은 primary interface지만 system authority는 canonical docs + DB facts
