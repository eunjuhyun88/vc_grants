# Funding Search Intelligence v1 — 상세 설계 문서

## 한 줄 요약

회사 프로필을 넣으면, 웹 검색 + 소셜(트위터) 검색 + 참조 데이터(CSV/Excel)를 동시에 스캔해서
**지금 실제로 지원 가능한 VC/Grant/Accelerator/Ecosystem Program**을 자동으로 발견하고,
프로젝트 fit + 마감 긴급도 + 실행 가능성까지 계산해서 **우선순위 랭킹**을 만들어주는 시스템.

현재는 이 과정을 사람이 수동으로 한다.
- ecosystem 사이트를 하나하나 방문
- 트위터에서 "accelerator apply", "grants open" 검색
- CSV/Excel에서 관련 프로그램 찾기
- 마감일 확인, 링크 확인, 우리랑 맞는지 판단
- 이걸 AI로 자동화하면 사람이 놓치는 기회를 잡을 수 있다.

이것은 크롤러가 아님.
**Funding Intelligence = market scanning + opportunity analysis + strategic recommendation**

---

## 이 시스템이 해결하는 문제

현재 스타트업이 투자/그랜트/액셀러레이터를 찾는 과정의 문제:

1. 정보가 여러 웹사이트에 분산되어 있다
2. VC + Ecosystem + Cohort 프로그램이 별도로 관리되지 않는다
3. 같은 프로그램이 트위터에서 먼저 발표되고 공식 페이지에 늦게 반영된다
4. 실제 지원 가능한 상태인지 (open/closed/rolling) 파악하기 어렵다
5. 프로젝트에 맞는 프로그램을 우선순위로 추천하는 시스템이 없다
6. Nitro(Monad+Dragonfly), Speedrun(a16z) 같은 VC+Ecosystem 코호트는 일반 검색으로 찾기 어렵다

즉 단순 크롤러나 링크 수집기가 아니라 아래가 필요하다:
**발견 → 검증 → 정규화 → 프로젝트 매칭 → 우선순위 판단 → 지속 모니터링**

---

## 이 시스템이 아닌 것

- 단순 grant 링크 모음
- 제출 폼 찾기 봇
- 크롤링 결과 표시기
- generic 챗봇
- 자동 지원서 제출 시스템 (v1 범위 아님)

---

## 3개 핵심 모듈

### 1. 프로필 기반 검색 쿼리 생성 (ProfileQueryPlanner)

HOOT의 sector_tags, target_ecosystems, stage 정보를 분석해서
웹/소셜 검색에 쓸 효과적인 쿼리를 자동 생성한다.

**데이터 소스**
- CompanyProfile.sector_tags → 검색 키워드 매핑 (deterministic, LLM 없음)
- CompanyProfile.target_ecosystems → ecosystem별 grant/accelerator 쿼리
- CompanyProfile.stage → 단계별 필터링 키워드

**TAG → KEYWORD 매핑**

| sector_tag | 검색 키워드 |
|---|---|
| ai_infra | "AI infrastructure", "AI infra" |
| decentralized_ai | "decentralized AI", "distributed AI" |
| crypto_infra | "crypto infrastructure", "blockchain infra" |
| distributed_compute | "distributed compute", "GPU network", "compute network" |
| personal_model_training | "AI model training", "personal AI" |
| agent_infra | "AI agent infrastructure", "agent framework" |
| small_model_training | "small language model", "SLM training" |

**쿼리 생성 패턴 (총 3개 축)**

축 1: sector + funding type 조합
```
{sector_keyword} grant program apply 2026
{sector_keyword} accelerator cohort open application
{sector_keyword} ecosystem builder program funding
```
- sector_keywords 상위 3개만 사용
- 총 9개 쿼리

축 2: target ecosystem + grant
```
{ecosystem} ecosystem grants funding program 2026
{ecosystem} accelerator builder program apply
```
- target_ecosystems 상위 5개만 사용
- 총 10개 쿼리

축 3: **새로운 VC+Ecosystem 코호트 발견 (가장 중요한 축)**

이미 아는 프로그램(Nitro, Speedrun, Alliance)을 찾는 게 아니라,
**아직 모르는 새로운 VC+Ecosystem 코호트를 발견하는 것**이 시스템의 핵심 가치.

이 유형의 특징:
- VC가 ecosystem과 같이 하는 accelerator (예: Dragonfly + Monad = Nitro)
- $200K~$1M 투자 + 8~12주 코호트 + 데모데이
- 대부분 트위터에서 먼저 발표되고 공식 페이지가 늦게 만들어짐
- 이름이 매번 다름 (Nitro, Speedrun, Fortify, Mach 등 — 패턴이 아니라 브랜딩)

발견용 쿼리:
```
crypto VC accelerator cohort 2026 apply
web3 startup accelerator seed investment cohort
blockchain founder residency program apply
crypto ecosystem accelerator demo day 2026
new web3 accelerator program launch apply
VC backed crypto builder cohort application
AI web3 accelerator seed funding open
crypto infra founder program investment 2026
```
- 고정 8개 쿼리
- 핵심: "VC + ecosystem + cohort/accelerator + apply/investment"를 다양하게 조합
- 이 쿼리들은 아직 이름도 모르는 프로그램을 발견하기 위한 것

축 4: 경쟁사/유사 프로젝트 기반 발견
```
{similar_project} funding grant received
{similar_project} accelerator program joined
decentralized AI startup funding 2026
distributed compute blockchain funding round
```
- similar_projects: ["bittensor", "prime intellect", "nous research", "modulus labs", "gensyn"]
- 이 프로젝트들이 어디서 돈 받았는지 찾으면 → 같은 곳이 우리에게도 맞을 가능성 높음
- 총 5개 쿼리

**최종 출력**: 최대 20개 쿼리 (중복 제거 후)

**HOOT 기준 쿼리 예시**:
```
# 축 1: sector + funding type
"AI infrastructure grant program apply 2026"
"decentralized AI accelerator cohort open application"
"crypto infrastructure ecosystem builder program funding"

# 축 2: ecosystem별
"ethereum ecosystem grants funding program 2026"
"near accelerator builder program apply"
"solana ecosystem grants funding program 2026"
"arbitrum accelerator builder program apply"
"monad ecosystem grants funding program 2026"

# 축 3: 새로운 VC+Ecosystem 코호트 발견 ← 핵심
"crypto VC accelerator cohort 2026 apply"
"web3 startup accelerator seed investment cohort"
"blockchain founder residency program apply"
"crypto ecosystem accelerator demo day 2026"
"new web3 accelerator program launch apply"
"VC backed crypto builder cohort application"
"AI web3 accelerator seed funding open"
"crypto infra founder program investment 2026"

# 축 4: 유사 프로젝트 기반
"bittensor funding grant received"
"gensyn accelerator program joined"
"decentralized AI startup funding 2026"
```

중요: LLM 호출 없음. 매핑 테이블 기반 deterministic 생성.
왜? 빠르고 예측 가능하고 비용 0. 쿼리 자체가 "좋은 쿼리"일 필요 없음 —
검색 엔진이 관련 결과를 찾아주면 되고, 결과 품질은 OpportunityExtractor가 담당함.

**축 3 + 축 4가 없으면 이 시스템은 "이미 아는 프로그램 확인기"에 불과하다.**
이 쿼리들이 있어야 Nitro 같은 프로그램을 **이름도 모르는 상태에서** 발견할 수 있다.

---

### 2. 3개 소스 병렬 검색

검색은 3개 소스에서 **동시에(asyncio.gather)** 실행된다.
각 소스는 독립적이라 하나가 실패해도 나머지가 결과를 준다.

#### 소스 A: 웹 검색 (기존 SearchOrchestrator 재사용)

**기존 코드 그대로 사용.**

흐름:
```
ProfileQueryPlanner 쿼리
    ↓
SearchOrchestrator.search(query)
    ↓
QueryPlanner.plan(query) → 4-6개 서브쿼리
    ↓
MultiEngineSearch.search_all(sub_queries)
    → DDG + Tavily + Brave + Serper (가용 엔진만)
    → asyncio.gather 병렬
    ↓
ResultReranker.rerank(results, top_k=15)
    → domain_authority(0.4) + engine_agreement(0.3) + relevance(0.2) + freshness(0.1)
    → AUTHORITY_TIER_1: ethereum.org, solana.org, near.org 등
    → BLOCKED: wikipedia, youtube, reddit
    ↓
SmartFetcher.fetch_many(urls, max_pages=10)
    → Jina Reader (JS 렌더링) + httpx 폴백
    → 동시 5개 제한 (Semaphore)
    → 앞 20K + 뒤 4K 스마트 잘라내기
    ↓
OpportunityExtractor.extract_per_page(pages)
    → Fast LLM (Groq llama-3.1-8b-instant)
    → 페이지별 기회 추출
    ↓
SufficiencyEvaluator.evaluate()
    → apply_url 5개 이상 OR 고유 기회 8개 이상이면 충분
    → 부족하면 Round 2 (최대 3라운드)
    ↓
OpportunityExtractor.synthesize(opportunities)
    → Strong LLM (Groq llama-3.3-70b-versatile)
    → dedup + gap-fill + contradiction 감지
```

**출력**: `list[dict]` (raw_opportunities), `list[str]` (source_urls)

**API 키 없이도 동작**: DDG 폴백이 있어서 API 키 0개여도 검색 가능.
API 키가 있으면 Tavily/Brave/Serper가 추가되어 품질 향상.

**기존 코드 변경 없음.**

#### 소스 B: 소셜 검색 (LunarCrush + FxTwitter)

**역할**: 트위터/소셜에서 펀딩 관련 발표를 캐치.
Nitro Accelerator, Speedrun 같은 프로그램은 트위터에서 먼저 발표됨.

**데이터 소스**

| 소스 | API | 용도 | 키 필요 |
|---|---|---|---|
| LunarCrush Topic_Posts | MCP 도구 | ecosystem별 펀딩 토픽 검색 | MCP 접근 가능 |
| LunarCrush Search | MCP 도구 | 일반 펀딩 키워드 검색 | MCP 접근 가능 |
| FxTwitter | REST API | 특정 트윗 전체 텍스트 fetch | 불필요 (무료) |

중요: FxTwitter는 **검색 불가** — 특정 트윗 ID로만 접근 가능.
소셜 검색의 핵심은 LunarCrush.

**검색 패턴**

ecosystem별 펀딩 토픽 검색:
```
for eco in target_ecosystems[:5]:
    LunarCrush.Topic_Posts("{eco} grants")
    LunarCrush.Topic_Posts("{eco} accelerator")
```

일반 펀딩 키워드 검색:
```
LunarCrush.Search("crypto accelerator apply")
LunarCrush.Search("web3 grants program open")
LunarCrush.Search("blockchain funding round seed")
LunarCrush.Search("AI crypto accelerator cohort")
```

**펀딩 관련 포스트 필터링**

LunarCrush 결과에서 펀딩 관련 포스트만 걸러내야 한다.
필터 키워드 (하나 이상 포함 시 통과):
```
"grant", "grants", "funding", "accelerator", "cohort",
"apply", "application", "builder program", "residency",
"incubator", "incubation", "seed round", "demo day",
"ecosystem fund", "builder incentive"
```

필터 제외 키워드 (이것만 있으면 제외):
```
"price prediction", "buy now", "airdrop", "token sale",
"pump", "moon", "100x"
```

**FxTwitter 활용 (보조)**

LunarCrush에서 발견된 트윗에 URL이 포함된 경우:
1. 트윗 텍스트에서 URL 추출
2. URL을 기존 SmartFetcher로 fetch → OpportunityExtractor로 기회 추출
3. 이렇게 하면 "트위터에서 발표된 Nitro Accelerator" → nitroacc.xyz 페이지 fetch → 기회 추출

LunarCrush 결과에 트윗 ID가 있는 경우:
```
FxTwitter API: https://api.fxtwitter.com/{screen_name}/status/{tweet_id}
```
- API 키 불필요
- 레이트 리밋 관대
- 전체 텍스트 + 미디어 + URL 포함

**SocialResult → raw_opportunity 변환**

```python
{
    "organization": extracted_org_name,  # 트윗/URL에서 추출
    "program": extracted_program_name,
    "category": guessed_category,        # "accelerator" | "grant" | "vc_cohort"
    "status": "unknown",                 # 소셜 소스는 검증 필요
    "apply_url": extracted_url,          # 트윗에서 추출한 URL
    "source_url": tweet_url,
    "source_type": "social",
    "confidence": 0.40,                  # 소셜 소스 기본 신뢰도 (낮게)
    "source_tier": 5,                    # SNS
}
```

confidence가 0.40으로 낮은 이유:
- 소셜 데이터는 검증되지 않은 정보
- 후속 Verification이 올려줌
- 하지만 발견 자체가 가치 있음 (공식 페이지보다 빨리 캐치)

#### 소스 C: 참조 데이터 검색 (CSV/Excel)

**역할**: 유저가 수동으로 모은 CSV/Excel 데이터에서 프로필에 맞는 항목을 필터링.
DB 구축 없이 메모리에서 직접 검색.

**데이터 소스**

| 파일 | 내용 | 레코드 수 |
|---|---|---|
| Folk CSV (companies.csv) | Web3 Grant 프로그램 | 90개 |
| Excel - Accelerator Program | 액셀러레이터 프로그램 | 99개 |
| Excel - Web3 VC | Web3 VC 리스트 | 119개 |
| Excel - grants program | 그랜트 프로그램 | 101개 |

총 참조 데이터: ~409개 레코드

**Folk CSV 필드**
```
id, name, description, Category (dApp/Layer-1/Layer-2/Service),
Grant Budget ($1M-$10M/etc), Grant Program, Grant URL, Maximum Amount
```
- 100% 커버리지: name, Grant Program, Grant URL, Category
- 44% 커버리지: Maximum Amount

**Excel 필드**
- Accelerator Program: Name, Website, Application Link, Description, Focus Areas
- Web3 VC: Name, Tier(1-4), Region, Website, Active(Y/N), Thesis/Focus
- grants program: Name, URL, Category, Budget, Status

**로드 방식**: 앱 시작 시 1회 메모리 로드. pandas 사용.
CSV: `pandas.read_csv()`
Excel: `pandas.read_excel(sheet_name=...)`

**매칭 로직**

프로필의 sector_tags + target_ecosystems를 검색 키워드로 변환한 뒤,
각 레코드의 텍스트 필드와 매칭 점수를 계산한다.

```python
def _text_match_score(text: str, keywords: list[str]) -> float:
    """키워드가 텍스트에 얼마나 포함되는지 계산."""
    text_lower = text.lower()
    matched = sum(1 for kw in keywords if kw.lower() in text_lower)
    return matched / max(len(keywords), 1)
```

매칭 대상 텍스트 필드:
- Folk CSV: `description + " " + Category + " " + Grant Program`
- Excel Accelerator: `Name + " " + Description + " " + Focus Areas`
- Excel VC: `Name + " " + Thesis/Focus`
- Excel grants: `Name + " " + Category`

**매칭 키워드 확장**

sector_tags 원본뿐 아니라 TAG_KEYWORDS 매핑의 자연어도 사용:
```
["ai_infra", "decentralized_ai", "crypto_infra"]
→ ["ai_infra", "AI infrastructure", "AI infra",
   "decentralized_ai", "decentralized AI", "distributed AI",
   "crypto_infra", "crypto infrastructure", "blockchain infra"]

target_ecosystems:
→ ["ethereum", "near", "solana", "arbitrum", "monad", "bittensor", "base"]
```

매칭 threshold: **score > 0.15** (키워드 17개 중 3개 이상 매칭)

**ReferenceResult → raw_opportunity 변환**

```python
{
    "organization": record.name,           # Folk: "Ethereum Foundation"
    "program": record.grant_program,       # Folk: "Ecosystem Support Program"
    "category": inferred_category,         # "grant" | "accelerator" | "fund"
    "status": "unknown",                   # 참조 데이터는 현재 상태 모름
    "apply_url": record.grant_url,         # Folk: "https://esp.ethereum.foundation"
    "budget": record.max_amount or record.budget,
    "source_url": record.grant_url,
    "source_type": "reference_data",
    "confidence": 0.60,                    # 참조 데이터 기본 신뢰도
    "source_tier": 3,                      # 집계 수준
}
```

confidence가 0.60인 이유:
- 유저가 수동으로 모은 데이터라 기본 신뢰도 있음
- 하지만 현재 상태(open/closed) 미확인
- Verification으로 올릴 수 있음

**출력**: 매칭 점수 상위 20개 레코드

---

### 3. 결과 통합 + 매칭 + 랭킹

#### 3.1 결과 합치기

3개 소스 결과를 하나의 리스트로 합친다:
```
web_results      → list[dict]   (SearchOrchestrator 결과)
social_results   → list[dict]   (LunarCrush/FxTwitter 결과)
reference_results → list[dict]  (CSV/Excel 매칭 결과)
```

#### 3.2 중복 제거 (Organization + Program 기준)

같은 프로그램이 3개 소스에서 모두 발견될 수 있다:
- 웹: "Ethereum Ecosystem Support Program" (esp.ethereum.foundation)
- 소셜: "@ethereum grants program open" 트윗
- 참조: Folk CSV의 "Ethereum Foundation" 레코드

Dedup 규칙 (우선순위):
1. **apply_url 정규화 비교**: `normalize_url()` 후 동일하면 merge
2. **organization + program 정규화 비교**: `normalize_org_name()` 후 동일하면 merge
3. **domain 비교**: `extract_domain(apply_url)` 동일하면 merge

Merge 시 필드 우선순위:
- confidence: **max** (가장 높은 값)
- source_tier: **min** (가장 높은 티어)
- apply_url: 웹 > 참조 > 소셜 순
- status: "open" > "rolling" > "unknown" 순 (확실한 것 우선)
- deadline: non-null 우선
- budget: non-null 우선

#### 3.3 기존 Pipeline으로 Ingest

dedup된 raw_opportunity를 **기존 FundingPipeline._ingest_raw_opportunity()** 로 처리:
```
raw_opportunity dict
    ↓
FundingPipeline._ingest_raw_opportunity(raw)
    ↓
Entity Resolution:
    1. Organization: domain dedup → name dedup → create
    2. Program: org+name dedup → create
    3. Opportunity: apply_url dedup → latest-by-program dedup → update or create
    ↓
DB 저장 (organizations, programs, opportunities 테이블)
    ↓
opp_id 반환
```

**기존 코드 변경 없음.**

#### 3.4 5-Factor 매칭 (기존 MatchingAgent 재사용)

DB에 저장된 opportunity를 **기존 MatchingAgent.batch_rank()** 로 스코어링:

```python
MatchingAgent.batch_rank(
    opportunity_ids=ingested_opp_ids,
    profile_id=company_profile_id,
    intent="default",  # 또는 "urgent", "biggest_check", "ready_now", "best_fit"
    top_n=15,
)
```

5-Factor 계산 (기존 코드 그대로):

```
priority_score = fit * 0.35 + urgency * 0.25 + actionability * 0.20
               + expected_value * 0.10 + confidence * 0.10
```

**fit_score 계산**:
- Jaccard 오버랩: opportunity.sector_tags ∩ profile.sector_tags
- 스케일 *2, 클램프 [0.1, 1.0]
- best_project 선택: profile.projects 중 가장 높은 오버랩

**urgency_score 계산**:
```
CLOSED    → 0.00
ROLLING   → 0.35
UPCOMING  → 0.25
None(unknown) → 0.10
D0-3      → 1.00
D4-7      → 0.85
D8-14     → 0.70
D15-30    → 0.50
D31+      → 0.20
```

**actionability_score 계산**:
```
endpoint_ready    * 0.35  # verified apply form=1.0, url만=0.7, 없음=0.3
+ status_readiness * 0.25  # OPEN=1.0, ROLLING=0.9, UPCOMING=0.3, UNKNOWN=0.2
+ requirement_fit  * 0.20  # stage_match=1.0, else=0.5
+ material_ready   * 0.20  # MVP=0.85 (하드코딩)
```

**expected_value 계산**:
```
money_value * 0.60 + strategic_value * 0.40

money_value:
  ≥$500K → 1.0, ≥$200K → 0.8, ≥$50K → 0.6, ≥$10K → 0.4, else → 0.2

strategic_value (category별):
  fund=0.9, vc_cohort=0.8, accelerator=0.7,
  builder_program=0.6, grant=0.5, hackathon=0.4
```

**confidence_score 계산**:
```
source_quality      * 0.35  # tier1=0.95, tier2=0.80, tier3=0.65, tier4=0.50, tier5=0.35
+ evidence_agreement * 0.25  # evidence 개수 기반
+ field_completeness * 0.20  # status, apply_url, deadline, budget, category 중 몇 개 있는지
+ verification_fresh * 0.20  # 최근 검증 여부
```

**Intent별 가중치 변경**:

| intent | fit | urgency | actionability | expected_value | confidence |
|---|---|---|---|---|---|
| default | 0.35 | 0.25 | 0.20 | 0.10 | 0.10 |
| urgent | 0.20 | 0.45 | 0.15 | 0.10 | 0.10 |
| biggest_check | 0.20 | 0.10 | 0.15 | 0.45 | 0.10 |
| ready_now | 0.25 | 0.15 | 0.35 | 0.10 | 0.15 |
| best_fit | 0.50 | 0.15 | 0.15 | 0.10 | 0.10 |

**기존 코드 변경 없음.**

---

## 전체 실행 흐름

```
유저: /funding HOOT
    │
    ├─① HOOT 프로필 로드
    │   DB에서 조회 → 없으면 하드코딩 프로필 폴백
    │   sector_tags: [ai_infra, decentralized_ai, crypto_infra,
    │                 distributed_compute, personal_model_training]
    │   target_ecosystems: [ethereum, near, solana, arbitrum, monad, bittensor, base]
    │   stage: mvp
    │
    ├─② ProfileQueryPlanner.generate_queries(profile) → 20개 검색 쿼리
    │
    ├─③ 3개 소스 병렬 검색 (asyncio.gather)
    │   │
    │   ├─ A. 웹 검색 ── SearchOrchestrator.search(query)
    │   │   QueryPlanner → MultiEngineSearch → Reranker → Fetcher → Extractor
    │   │   → Agentic RAG 루프 (1~3라운드, 충분성 평가)
    │   │   → 결과: raw_opportunities[], source_urls[]
    │   │
    │   ├─ B. 소셜 검색 ── SocialSearchEngine.search(profile)
    │   │   LunarCrush Topic_Posts (ecosystem별)
    │   │   + LunarCrush Search (펀딩 키워드)
    │   │   → 펀딩 관련 포스트 필터링
    │   │   → URL 추출 → SmartFetcher → OpportunityExtractor
    │   │   → 결과: raw_opportunities[]
    │   │
    │   └─ C. 참조 데이터 ── ReferenceDataEngine.search(profile)
    │       Folk CSV + Excel 메모리 로드
    │       → sector_tags + ecosystems 키워드 매칭
    │       → 상위 20개 매칭 결과
    │       → 결과: raw_opportunities[]
    │
    ├─④ 결과 합치기 + 중복 제거
    │   apply_url 정규화 → org+program 정규화 → domain 비교
    │   → merge 시 confidence max, source_tier min
    │
    ├─⑤ FundingPipeline._ingest_raw_opportunity() × N건
    │   Entity Resolution → DB 저장
    │   → Organization → Program → Opportunity 계층 생성
    │
    ├─⑥ MatchingAgent.batch_rank(opp_ids, profile_id, intent, top_n=15)
    │   5-Factor 계산:
    │   fit * 0.35 + urgency * 0.25 + actionability * 0.20
    │   + expected_value * 0.10 + confidence * 0.10
    │
    └─⑦ 결과 출력
        OpportunityCard 생성 → render_funding_results()
        Telegram MarkdownV2로 전송
```

---

## 출력 형식

```
🏆 TOP FUNDING FOR HOOT
📊 Intent: 추천 순위

1️⃣ Nitro Accelerator (Monad)
   📁 VC + Ecosystem Accelerator
   📊 Priority: 0.82 │ Fit: 0.80
   ⏰ D-5 │ 💰 $500K
   🔗 지원하기

2️⃣ Ethereum ESP
   📁 Grant
   📊 Priority: 0.79 │ Fit: 0.90
   ⏰ Rolling │ 💰 $10K-$200K
   🔗 지원하기

3️⃣ Alliance Accelerator
   📁 Accelerator
   📊 Priority: 0.77 │ Fit: 0.80
   ⏰ D-18 │ 💰 ~$500K
   🔗 지원하기

...

📊 출처: 웹 8건 │ 소셜 3건 │ 참조 5건
⏱ 검색 시간: 45초
```

각 결과에 반드시 포함되어야 하는 3가지:
1. **왜 높게 나왔는지** (why_fit)
2. **왜 지금 해야 하는지** (urgency 근거)
3. **지금 바로 뭘 해야 하는지** (next_action)

next_action 자동 생성 규칙:
```
priority ≥ 0.80 → "지금 바로 지원"
0.65 ≤ priority < 0.80 → "이번 주 내 준비 및 지원"
0.50 ≤ priority < 0.65 → "자료 보완 후 대기"
priority < 0.50 → "Watchlist"
```

---

## HOOT 기본 프로필 (하드코딩)

DB 등록 전에도 바로 동작하도록 기본 프로필 하드코딩:

```python
HOOT_PROFILE = CompanyProfile(
    id="hoot-default",
    company_name="Holo Studio Co., Ltd.",
    stage=CompanyStage.MVP,
    sector_tags=[
        "ai_infra",
        "decentralized_ai",
        "crypto_infra",
        "distributed_compute",
        "personal_model_training",
    ],
    subsector_tags=[
        "agent_infra",
        "small_model_training",
        "torrent_coordination",
        "blockchain_compute",
    ],
    geography="global",
    funding_goal="grant,accelerator,seed_vc",
    product_summary="개인 데이터 기반 소형모델 학습 + 분산 컴퓨팅 + 블록체인 coordination",
    target_ecosystems=[
        "ethereum", "near", "solana", "arbitrum",
        "monad", "bittensor", "base",
    ],
    projects=[
        {"name": "HOOT", "tags": ["ai_infra", "distributed_compute"], "priority": 1},
        {"name": "StockClaw", "tags": ["crypto_analytics", "trading_infra"], "priority": 2},
        {"name": "MoltVC", "tags": ["ai_evaluation", "ai_benchmark"], "priority": 3},
        {"name": "PlayArts", "tags": ["ai_content", "creator_economy"], "priority": 4},
        {"name": "ClawGene", "tags": ["physical_ai", "desci"], "priority": 5},
    ],
)
```

---

## 지금 있는 자산 (변경 없이 재사용)

| 자산 | 위치 | 상태 |
|---|---|---|
| SearchOrchestrator (Agentic RAG 루프) | `src/search/orchestrator.py` | ✅ 동작 |
| MultiEngineSearch (Brave/Tavily/Serper/DDG) | `src/search/multi_engine.py` | ✅ 동작 |
| QueryPlanner (쿼리 분해/리파인) | `src/search/query_planner.py` | ✅ 동작 |
| OpportunityExtractor (LLM 추출) | `src/search/extractor.py` | ✅ 동작 |
| ResultReranker (도메인 기반 리랭킹) | `src/search/reranker.py` | ✅ 동작 |
| SmartFetcher (Jina+httpx 페이지 수집) | `src/search/fetcher.py` | ✅ 동작 |
| SufficiencyEvaluator (충분성 평가) | `src/search/evaluator.py` | ✅ 동작 |
| MatchingAgent (5-factor 스코어링) | `src/agents/matching.py` | ✅ 동작 |
| FundingPipeline (ingest + entity resolution) | `src/core/pipeline.py` | ✅ 동작 |
| EntityStore (DB 저장/조회) | `src/db/entity_store.py` | ✅ 동작 |
| CompanyProfile 스키마 | `src/core/types.py` | ✅ 동작 |
| card_renderer (Telegram 출력) | `src/interface/card_renderer.py` | ✅ 동작 |
| DB에 368개 시드 데이터 | `data/seed_raw.json` | ✅ 로드됨 |
| LunarCrush MCP | MCP 도구 | ✅ 접근 가능 |

---

## 새로 만드는 코드

| 파일 | 역할 | 크기 예상 |
|---|---|---|
| `src/core/profiles.py` | HOOT 기본 프로필 하드코딩 | ~50줄 |
| `src/search/profile_query_planner.py` | 프로필 → 검색 쿼리 생성 | ~120줄 |
| `src/search/engines/social_engine.py` | LunarCrush + FxTwitter 소셜 검색 | ~200줄 |
| `src/search/engines/reference_engine.py` | CSV/Excel 참조 데이터 검색 | ~250줄 |
| `src/search/funding_orchestrator.py` | 웹+소셜+참조 통합 오케스트레이터 | ~200줄 |
| `src/interface/handlers/funding_handler.py` | `/funding` 텔레그램 커맨드 | ~120줄 |

기존 파일 수정:

| 파일 | 수정 내용 |
|---|---|
| `src/interface/telegram_app.py` | `CommandHandler("funding", funding_command)` 추가 (1줄) |
| `src/interface/card_renderer.py` | `render_funding_results()` 함수 추가 (~40줄) |

합계: **새 코드 ~940줄, 수정 ~41줄**

---

## 구현 순서

### Step 1: 프로필 + 쿼리 생성 (30분)
- `src/core/profiles.py` — HOOT 하드코딩 프로필
- `src/search/profile_query_planner.py` — TAG_KEYWORDS + generate_queries()
- 테스트: `generate_queries(HOOT_PROFILE)` → 20개 쿼리 출력 확인

### Step 2: 참조 데이터 엔진 (30분)
- `src/search/engines/reference_engine.py` — CSV/Excel 로드 + 태그 매칭
- 테스트: `search(HOOT_PROFILE)` → Folk CSV에서 Ethereum/Solana/NEAR 그랜트 매칭 확인

### Step 3: 소셜 검색 엔진 (30분)
- `src/search/engines/social_engine.py` — LunarCrush API 래핑 + FxTwitter
- 테스트: `search_funding_posts(HOOT_PROFILE)` → 펀딩 관련 소셜 포스트 확인

### Step 4: 통합 오케스트레이터 (20분)
- `src/search/funding_orchestrator.py` — 3소스 병렬 → 합치기 → dedup
- 테스트: `search_for_project(HOOT_PROFILE)` → 통합 결과 확인

### Step 5: Telegram 커맨드 + 출력 (20분)
- `src/interface/handlers/funding_handler.py` — `/funding HOOT` 커맨드
- `src/interface/card_renderer.py` — render_funding_results() 추가
- `src/interface/telegram_app.py` — 커맨드 등록

### Step 6: 테스트 + 검증 (30분)
- `tests/test_profile_query_planner.py` — 쿼리 생성 테스트
- `tests/test_reference_engine.py` — CSV/Excel 파싱 + 매칭 테스트
- `tests/test_funding_orchestrator.py` — 통합 결과 테스트
- 기존 140개 테스트 통과 확인

---

## 설계 검증: 이 흐름이 올바른가?

### 유저가 수동으로 한 것 vs 시스템이 자동으로 하는 것

| 수동 (내가 한 것) | 자동 (시스템) |
|---|---|
| WebSearch "HOOT AI agent 맞는 투자사" | ProfileQueryPlanner → 20개 쿼리 자동 생성 |
| WebSearch "ethereum grants", "near grants" | SearchOrchestrator → DDG+API 멀티엔진 검색 |
| LunarCrush로 crypto accelerator 검색 | SocialSearchEngine → LunarCrush Topic_Posts/Search |
| Folk CSV에서 관련 그랜트 찾기 | ReferenceDataEngine → sector_tags 매칭 |
| 결과 합치고 중복 제거 | FundingSearchOrchestrator → apply_url/org+program dedup |
| "HOOT와 맞는가?" 수동 판단 | MatchingAgent → 5-factor scoring |
| "어디부터 지원할까?" 수동 정렬 | batch_rank(intent="default") → priority_score 정렬 |
| Telegram에 결과 정리해서 보내기 | render_funding_results() → MarkdownV2 |

### 결과 품질: 현실적 평가

**DDG만 있을 때 (API 키 0개)**:
- DDG 웹 검색은 기본 동작하지만 결과 품질이 제한적
- 공식 페이지가 검색 상위에 나오는 유명 프로그램(Ethereum ESP, Alliance 등)은 찾을 수 있음
- 하지만 새로 런칭된 프로그램, 소규모 ecosystem 프로그램은 DDG만으로 발견하기 어려움
- **현실적 기대: 웹에서 5~10개 raw opportunities**

**LunarCrush (소셜 검색)**:
- 트위터/소셜에서 펀딩 발표를 캐치하는 데 강함
- "accelerator apply", "grants open" 같은 발표 시점의 포스트를 잡음
- 하지만 모든 프로그램이 소셜에서 화제가 되는 건 아님
- **현실적 기대: 2~5개 raw opportunities (새로운 발견 가능성이 여기에 있음)**

**참조 데이터 (CSV/Excel 409개)**:
- 가장 신뢰할 수 있는 소스 — 유저가 수동으로 검증한 데이터
- sector_tags 매칭은 deterministic이라 결과가 예측 가능
- 하지만 현재 상태(open/closed)를 모르므로 이미 마감된 것도 포함될 수 있음
- **현실적 기대: 태그 매칭으로 15~25개 후보 → 실제 유효한 것 5~10개**

**API 키 추가 시 (Tavily/Brave/Serper)**:
- 검색 엔진 다양성이 핵심 — 한 엔진이 못 찾는 걸 다른 엔진이 찾음
- 특히 Tavily는 최신 컨텐츠에 강해서 새 프로그램 발견에 유리
- Jina Reader로 JS 렌더링 페이지(Typeform, Airtable 등)도 fetch 가능
- **현실적 기대: 웹 결과 2~3배 증가**

**통합 현실적 기대**:
| 구성 | Raw Opportunities | Dedup 후 유효 결과 |
|---|---|---|
| DDG만 | 20~35개 | 8~15개 |
| DDG + 1개 API 키 | 30~50개 | 12~20개 |
| DDG + 3개 API 키 | 45~70개 | 18~30개 |

핵심: **결과 개수보다 "이전에 몰랐던 프로그램을 발견했는가"가 진짜 가치.**
이미 아는 Ethereum ESP, Alliance를 다시 찾아주는 건 가치가 낮다.
Quantara Labs AI x Web3 Accelerator, Polygon ecosystem grants처럼
**이름도 모르던 프로그램을 발견해주는 것**이 이 시스템의 존재 이유.

### 미지의 프로그램 발견 메커니즘 (이 시스템의 핵심 가치)

**문제 정의**:
"Ethereum ESP 찾아줘"는 쉽다. 구글 검색해도 나온다.
진짜 가치는 **"Ethereum ESP 같은 건데 내가 아직 이름도 모르는 프로그램"**을 찾는 것.

**발견이 가능한 이유**:
웹3 펀딩 프로그램은 표준화된 언어 패턴을 사용한다.
어떤 프로그램이든 아래 단어들이 공식 페이지나 발표에 포함된다:
```
"apply", "application", "grant", "funding", "accelerator",
"cohort", "builder program", "demo day", "seed", "incubator",
"residency", "ecosystem fund"
```
이 패턴이 존재하기 때문에 이름을 모르는 프로그램도 검색으로 발견 가능.

**4가지 발견 경로**:

1. **웹 검색 + LLM 추출 (축 3 쿼리)**
   ```
   "crypto VC accelerator cohort 2026 apply"
   "new web3 accelerator program launch apply"
   ```
   → 검색 결과에 "XYZ Accelerator — Applications Now Open" 같은 페이지가 나옴
   → OpportunityExtractor가 페이지에서 프로그램명, 마감일, 지원 링크 추출
   → 이전에 이름도 몰랐던 프로그램이 결과에 포함됨

   **이게 가능한 조건**: 검색 엔진이 해당 페이지를 인덱싱하고 있어야 함.
   DDG만으로는 부족할 수 있음 → Tavily/Brave 추가가 발견율을 높임.

2. **소셜 검색 (LunarCrush)**
   새 프로그램은 대부분 트위터에서 먼저 발표된다:
   ```
   "@dragonfly_xyz is launching Fortify Accelerator with @SuiNetwork"
   "Announcing HyperBuild — a new builder program by @hyperlane_xyz"
   ```
   → LunarCrush Topic_Posts/Search로 이런 발표 캐치
   → 포스트에서 URL 추출 → SmartFetcher로 공식 페이지 fetch
   → OpportunityExtractor로 상세 정보 추출

   **이게 가능한 조건**: 프로그램이 트위터에서 충분한 engagement를 받아야 LunarCrush에 잡힘.
   → 소규모 프로그램은 놓칠 수 있음.

3. **경쟁사 추적 (축 4 쿼리)**
   HOOT과 유사한 프로젝트가 어디서 펀딩 받았는지 추적:
   ```
   "gensyn accelerator program joined"
   "prime intellect funding grant received"
   ```
   → "Gensyn participated in XYZ Accelerator" 같은 기사/포스트 발견
   → XYZ Accelerator가 HOOT에도 맞을 가능성 높음
   → **경쟁사의 펀딩 이력 = 우리의 타겟 리스트**

   **이게 가능한 조건**: 경쟁사의 펀딩 사실이 공개되어 있어야 함.
   → 대부분의 accelerator/grant 수혜 사실은 공개됨 (데모데이, 블로그 등).

4. **Aggregator 페이지 크롤링 (검색 결과 내 간접 발견)**
   웹 검색 결과에 개별 프로그램 페이지뿐 아니라 aggregator 페이지도 나옴:
   ```
   "Top 20 Crypto Accelerators in 2026"
   "Best Web3 Grants for AI Projects"
   "Complete List of Blockchain Funding Programs"
   ```
   → SmartFetcher가 이런 페이지를 fetch
   → OpportunityExtractor가 페이지 내 **여러 프로그램을 한번에 추출**
   → 한 페이지에서 5~10개 프로그램을 동시에 발견할 수 있음

   **이게 가능한 조건**: OpportunityExtractor가 리스트 형태의 페이지를 잘 파싱해야 함.
   → 기존 구현에서 이미 페이지별 multi-opportunity 추출 지원.

**현실적 발견 시나리오 (HOOT 기준)**:

| 발견 경로 | 예시 발견 | 신뢰도 |
|---|---|---|
| 축3 웹검색 | "Polygon AI Grants" — polygon.technology에서 발견 | 높음 (공식 페이지) |
| 축3 웹검색 | "Quantara Labs AI x Web3 Accelerator" — 블로그에서 발견 | 중간 (검증 필요) |
| 소셜 | "@cosmos 새 infra grants 프로그램 런칭" — 트위터에서 캐치 | 중간 (source_tier=5) |
| 축4 경쟁사 | "Gensyn이 Longhash Ventures에서 펀딩 받음" → Longhash도 우리 타겟 | 높음 (실적 기반) |
| Aggregator | "2026 Best Crypto Accelerators" 글에서 10개 프로그램 한번에 추출 | 높음 (복수 소스) |

**발견 못하는 경우 (한계)**:
- 비공개 프로그램 (초대 전용, 네트워크 기반)
- 검색 엔진에 아직 인덱싱 안 된 페이지
- 소셜에서 engagement 없는 소규모 발표
- 영어 외 언어로만 된 프로그램

**한계를 줄이는 방법 (v1.1)**:
- 주기적 재검색 (24h마다) → 인덱싱 시차 커버
- API 키 추가 → 검색 엔진 다양성으로 커버리지 확대
- 특정 Twitter 계정 모니터링 → LunarCrush Creator API로 VC/Ecosystem 계정 추적

### 이미 아는 프로그램 vs 새로 발견한 프로그램 구분

결과 출력 시 "발견 유형"을 표시한다:
```
🆕 NEW — 이전에 DB에 없던 프로그램 (이번 검색에서 발견)
🔄 UPDATED — DB에 있었지만 정보가 변경됨 (마감일, 상태 등)
📋 KNOWN — DB에 이미 있던 프로그램 (참조 데이터에서 확인)
```

이 구분이 중요한 이유:
- 유저에게 **"이 시스템이 새로운 걸 찾아줬다"**는 것을 명확히 보여줘야 함
- 409개 참조 데이터에서 매칭된 결과만 보여주면 "그냥 CSV 필터기"에 불과
- 🆕 NEW가 결과에 있어야 이 시스템의 가치가 증명됨

---

## 제한 사항 및 향후 계획

### v1 제한
- 소셜 검색은 LunarCrush API 가용성에 의존
- FxTwitter는 검색 불가 — 보조 역할만
- 참조 데이터는 파일 경로 하드코딩 (설정 필요)
- 실시간 모니터링 아직 없음 (수동 `/funding` 호출)

### v1.1 (다음 단계)
- MonitoringAgent 연동 → 마감일 변화 자동 추적
- Daily Brief에 펀딩 결과 포함
- `/funding_map HOOT` → Discovery Map 출력
- `/urgent` → 마감 가까운 것만 필터

### v2
- 자동 주기적 검색 (24시간마다)
- 새 기회 발견 시 Telegram 알림
- 지원 상태 트래킹 (/apply_status)
- 프로젝트별 narrative 자동 생성

---

## 핵심 원칙

1. **기존 코드 최대한 재사용** — SearchOrchestrator, MatchingAgent, FundingPipeline 모두 그대로
2. **새로 만드는 건 "접착제" 역할만** — 프로필→쿼리, 소셜엔진, 참조엔진, 통합 오케스트레이터
3. **DB 없이도 동작** — 참조 데이터는 CSV/Excel에서 직접 로드, 프로필은 하드코딩
4. **Fact ≠ AI Reasoning 분리** — deadline/status/apply_url은 검증 기반 facts. fit/priority/why는 AI reasoning
5. **점진적 개선** — DDG+참조데이터로 기본 동작. API 키 추가 시 발견 범위가 크게 확대됨. 새 프로그램 발견은 검색 엔진 다양성에 비례
6. **발견 > 확인** — 이미 아는 프로그램 재확인이 아니라, 이름도 모르던 프로그램을 발견하는 것이 핵심 가치
