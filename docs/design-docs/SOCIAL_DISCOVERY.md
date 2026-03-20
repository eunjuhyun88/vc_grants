# Social Discovery

## Purpose

X/Twitter는 Funding Intelligence Agent에서 `verification truth source`가 아니라
`early candidate discovery source`로 사용한다.

역할은 다음 둘이다.

1. 공식 페이지보다 먼저 나오는 cohort/grant/accelerator 발표를 빨리 찾는다.
2. 후보에 붙은 외부 링크를 따라가서 이후 verification이 공식 페이지를 찾게 돕는다.
3. 우선 추적할 VC / L1 / L2 / foundation / accelerator operator 계정에서
   investment, ecosystem fund, grant, cohort 신호를 먼저 찾는다.

즉 소셜은 `finding`, 공식 페이지는 `truth`다.

## Stable Contract

- X/Twitter 포스트만으로 verified opportunity를 만들지 않는다.
- 소셜에서 나온 결과는 항상 `low-confidence candidate`로 ingest한다.
- verified 승격은 공식 application page / official program page / official docs가 담당한다.
- FxTwitter는 검색 엔진이 아니라 `tweet expansion/fetch layer`다.
- `data/curated_social_accounts.json`은 social finding recall을 높이기 위한
  seeded watchlist이며, verified truth source가 아니다.
- `data/discovered_social_accounts.json`은 official-site handle discovery 결과를
  누적하는 runtime registry이며, seeded watchlist를 보강하는 용도다.

## Runtime Flow

```text
CompanyProfile
  -> generate_social_queries(profile)
  -> build monitoring rounds
       -> profile-priority
       -> vc-us / vc-asia / vc-eu / vc-uk / vc-uae / vc-web2 / vc-unknown
       -> ecosystem-operators
  -> SocialSearchEngine.search(profile)
       A. LunarCrush topic search (optional, key-based)
       B. Web-assisted X search (default fallback)
            -> generic topic round
            -> account-targeted monitoring rounds by region/account type
            -> official site handle discovery (homepage/footer/social links -> x.com/<handle>)
            -> MultiEngineSearch.search_all(...) per monitoring round
            -> tweet URL filter
            -> FxTwitter fetch per tweet
       C. signal classification
            -> applications_open / grant_program / accelerator_program
            -> ecosystem_fund / investment_announcement
       D. raw social candidate conversion
           -> social_monitoring_events provenance row upsert
  -> FundingSearchOrchestrator seed round
  -> FundingPipeline ingest (candidate/pending)
  -> Verification later promotes/drops
  -> monitoring queries verified actionable social alert candidates
```

## Source Strategy

### 1. LunarCrush

- 용도: ecosystem/topic 기준으로 빠르게 social chatter를 모은다.
- 필요 조건: `LUNARCRUSH_API_KEY`
- 결과 성격: social post candidate

### 2. Web-Assisted X Search

- 용도: 검색 엔진으로 tweet URL을 찾는다.
- 추가 전략: seeded watchlist 계정에 대해 handle / organization name / program name을
  섞은 account-targeted query를 함께 만든다.
- 필요 조건: 일반 검색 엔진 중 최소 1개 사용 가능
  - `TAVILY_API_KEY`
  - `SERPER_API_KEY`
  - `BRAVE_API_KEY`
- 방식:
  - `site:x.com "<query>"`
  - `site:twitter.com "<query>"`
  - result URL 중 `/status/<tweet_id>`만 유지

### 3. FxTwitter

- 용도: 검색으로 발견한 tweet URL의 본문/메타데이터를 가져온다.
- 필요 조건: 없음
- 주의: FxTwitter 자체는 search backend가 아니다.

### 4. Seeded Social Account Watchlist

- 파일: `data/curated_social_accounts.json`
- 포함 대상:
  - VC accounts
  - L1 / L2 / foundation accounts
  - accelerator operator / ecosystem accounts
- 필드:
  - `organization`
  - `handle`
  - `search_names`
  - `account_type`
  - `ecosystems`
  - `programs`
  - `watch_terms`
- 목적:
  - HOOT 같은 profile에 맞는 ecosystem/VC 계정을 우선 탐색한다.
  - generic X search로 놓치기 쉬운 `applications open`, `ecosystem fund`,
    `investment`, `builder program` 신호를 먼저 찾는다.

### 5. Official Site Handle Discovery

- watchlist는 고정값만 쓰지 않는다.
- social engine은 relevant account의 `official_urls`를 읽고,
  그 페이지 HTML에서 `x.com/<handle>` / `twitter.com/<handle>` profile 링크를 찾아
  동적 watch account를 추가한다.
- 목적:
  - 공식 handle rename (`monad_xyz` -> `monad`) 같은 drift 대응
  - seeded registry에 아직 없는 secondary handle / foundation handle 보강
- 제약:
  - `status/...` 링크는 profile handle discovery로 쓰지 않는다.
  - 공식 사이트에서 발견한 handle도 여전히 `finding source`일 뿐,
    verified truth는 아니다.

### 6. Reference-Seeded VC / Ecosystem Expansion

- 파일:
  - `data/seed_raw.json`
  - `data/discovered_social_accounts.json`
  - `output/spreadsheet/vc_list_final.csv`
- 역할:
  - curated watchlist 밖에 있는 VC / foundation / accelerator operator도
    seed data의 공식 웹사이트를 기준으로 social watch 후보로 확장한다.
  - 특히 VC는 `vc_list_final.csv`를 직접 읽어 region/country bucket과 함께
    social watch 후보로 승격한다.
  - social engine은 seed row의 `website` / `program_url`에서 official site를 읽고,
    거기서 X handle을 찾은 뒤 runtime registry에 누적한다.
- 제약:
  - Typeform / Airtable / Google Form 같은 외부 폼 URL은
    official handle discovery source로 쓰지 않는다.
  - reference-seeded account도 verified truth source는 아니며,
    social candidate recall을 높이는 watch 후보일 뿐이다.

## Candidate Rules

소셜 포스트가 raw opportunity로 변환되려면:

- funding keyword가 포함되어야 한다
- 스팸/price/pump 키워드는 제외한다
- 최소한 org/program 텍스트가 추정 가능하거나, 충분한 길이의 설명이 있어야 한다
- `investment_announcement` 같은 research-only 신호는 raw opportunity로 승격하지 않는다
- `generic_funding` / `ecosystem_fund`는 실제 apply surface 또는 submit/open evidence가 있을 때만 raw opportunity로 승격한다

생성되는 기본 값:

- `source_type = "social"`
- `source_tier = 5`
- `confidence = 0.40`
- `fact_confidence = 0.40`
- `status = "unknown"`
- `social_signal_type` = signal classifier 결과
- `matched_account` / `matched_account_type` = watchlist 매칭 결과
- `social_monitoring_round` = 어떤 region/account round에서 발견됐는지

즉 소셜 후보는 추천 시스템에 참고는 되지만, 공식 verification 전에는 약한 증거다.

## Why This Design

- 많은 프로그램이 먼저 X/Twitter에서 발표된다.
- 많은 VC / L1 / L2가 fund launch, cohort launch, builder program,
  investment thesis를 먼저 X/Twitter에서 알린다.
- 하지만 deadline/apply URL/funding amount를 소셜만으로 확정하면 오탐이 많아진다.
- 그래서 `social for recall`, `official pages for precision` 구조가 필요하다.

## Operator Notes

- LunarCrush 키가 없어도 social discovery는 동작할 수 있다.
- 다만 이 경우 발견 품질은 web search index 품질에 크게 의존한다.
- watchlist 파일은 canonical seed이며, 필요하면 operator가 직접 확장할 수 있다.
- social engine은 official-site handle discovery를 통해 watchlist를 runtime에서 보강한다.
- social engine은 seed/reference company list의 official website도 watch 후보로 사용한다.
- VC watch query selection은 relevance만 보지 않고 region diversity도 일부 강제한다.
- social engine은 blended query 1회 호출이 아니라 `profile-priority`와
  `vc-<region>` round를 실제로 나눠 실행한다.
- 현재 registry가 country보다 region bucket(`US`, `Asia`, `EU`, `UK`, `UAE`,
  `Web2`, `UNKNOWN`) 위주이므로 monitoring도 우선 이 bucket 기준으로 돈다.
- pipeline은 social raw candidate를 ingest할 때 `social_monitoring_events`에
  provenance를 남긴다.
- verification 뒤에 `pending / verified / rejected` 상태가 social provenance에
  반영되고, monitoring은 여기서 verified actionable alert 후보를 뽑는다.
- Typeform / Airtable / Google Form 같은 외부 제출 폼은 social post에서
  직접 발견할 수 있지만, 최종 open/closed/current window 판정은 verification이 한다.
- 검색 엔진 키도 없으면 X/Twitter discovery는 비활성화되고, reference/web 경로만 동작한다.
