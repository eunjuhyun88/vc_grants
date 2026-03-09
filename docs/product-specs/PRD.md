# Funding Intelligence Agent — Requirements Specification (PRD)

> 이 문서가 모든 설계 문서의 **원본(source of truth)**이다.
> 설계 문서와 PRD가 충돌하면 PRD가 우선.

---

## 1. 문제 정의

스타트업이 투자/그랜트/액셀러레이터 프로그램을 찾는 과정의 문제:

1. 정보가 여러 웹사이트에 분산
2. Rolling / Cohort / Ecosystem 형태라 단순 리스트 검색으로 찾기 어려움
3. VC + Ecosystem + Cohort 프로그램이 별도로 관리되지 않음
4. 실제 지원 가능한 상태인지 파악 어려움
5. 프로젝트에 맞는 프로그램을 우선순위로 추천하는 시스템 없음

---

## 2. 목표

**Funding Opportunities Intelligence System**

1. Funding opportunity 자동 발견
2. 프로그램 상태 추적 (open / closed / rolling)
3. 마감일 추적
4. 지원 링크 저장
5. 프로젝트 fit 분석
6. 우선순위 추천

---

## 3. 핵심 사용자

- Primary: startup founder (AI / crypto / web3)
- 사용자가 **자기 프로젝트를 등록** → 맞춤 추천

---

## 4. 핵심 데이터 구조

### Organization (투자 조직)
- name, type (VC / foundation / ecosystem), website, portfolio, thesis

### Program (조직이 운영하는 프로그램)
- organization_id, program_name, category, description
- category: grant, accelerator, vc_cohort, ecosystem_builder (Section 5 참조)

### Opportunity (현재 지원 가능한 창구)
- program_id, status, deadline, apply_url, funding_amount, cohort_date
- status: open, rolling, closed, upcoming, unknown

---

## 5. Opportunity Categories (4가지)

### Grants
- 예: Ethereum Ecosystem Grants, Solana Foundation Grants, Arbitrum Grants
- 특징: rolling, $10k-$200k, milestone based

### Accelerators
- 예: Alliance, Outlier, Antler, Techstars
- 특징: 8-12 week cohort, demo day, mentor network

### VC Cohorts
- 예: Speedrun, Nitro Accelerator, Binance Labs Incubation
- 특징: seed investment, $200k-$1M, cohort structure

### Ecosystem Builder Programs
- 예: Chainlink BUILD, Polygon Village, Solana Colosseum, Avalanche infraBUIDL
- 특징: grant + ecosystem support, token incentives, network effects

---

## 6. 핵심 데이터 필드

Opportunity 필수 필드:
- organization, program, category, status
- deadline, days_left, funding_amount, apply_url, confidence

추가 필드:
- cohort_start, cohort_duration, investment_amount, program_type

---

## 7. 데이터 수집 (Discovery)

스캔 소스:
- Official program websites (speedrun.xyz, alliance.xyz 등)
- Ecosystem pages (solana.org, arbitrum.foundation 등)
- Startup ecosystem sites (colosseum.org, encode.club 등)

검색 키워드:
- accelerator, startup cohort, builder program, founder residency
- web3 accelerator, crypto accelerator, grant program, ecosystem funding

---

## 8. 상태 검증

확인 대상: 지원 가능 여부, deadline, rolling 여부, cohort 모집 상태

데이터 source priority:
1. official website
2. official docs
3. blog post
4. news
5. social media

---

## 9. Deduplication

- 기준: organization + normalized_program_name
- URL 정규화: remove http, query, fragment

---

## 10. Matching Engine

Company Profile 예 (HOOT):
- sector: AI infra
- type: decentralized compute
- stage: prototype
- focus: small model training
- technology: blockchain + distributed compute

Fit score: sector match + stage match + ecosystem relevance → 0.0~1.0

---

## 11. Priority Algorithm

```
priority_score =
  fit_score      * 0.35 +
  urgency_score  * 0.35 +
  expected_value * 0.15 +
  confidence     * 0.15
```

urgency:
- 0-3 days → 1.0
- 4-7 days → 0.8
- 8-14 days → 0.6
- 15-30 days → 0.4
- rolling → 0.3

---

## 12. Agent Pipeline

```
Discovery Agent
  ↓
Entity Resolution
  ↓
Verification Agent
  ↓
Opportunity Database
  ↓
Matching Agent
  ↓
Monitoring Agent
  ↓
Output
```

---

## 13. Monitoring

재검증 주기:
- deadline ≤ 14 days → 6h
- status open → 24h
- status unknown → 12h
- status closed → 72h

변경 감지: deadline, status, apply_url, funding 변경

---

## 14. Output Interface

Telegram을 통한 조회 (interface일 뿐, 핵심은 AI Agent):
- /grants, /cohorts, /funds, /all, /brief, /org

---

## 15. MVP Scope

- funding discovery
- deduplication
- deadline tracking
- apply link extraction
- fit scoring
- priority ranking
- telegram output

---

## 16. Future Scope

- auto application preparation
- pitch deck generation
- investor outreach
- submission tracking

---

## 17. Success Criteria

1. 지원 가능한 프로그램을 자동 발견한다
2. deadline을 정확히 추적한다
3. 중복 데이터가 없다
4. 프로젝트에 맞는 funding을 추천한다

---

## 18. 핵심 철학

> 이 시스템은 단순한 크롤러가 아니다.
> **Funding Intelligence Agent** = market scanning + opportunity analysis + strategic recommendation
