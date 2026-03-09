# Funding Intelligence Agent — Entity Model & Dedup Rules

## Entity 계층 구조

```
Organization (VC, Foundation, Accelerator, Ecosystem)
  ├── Alias (별명 목록 — dedup용)
  ├── Dossier (조직 상세 정보 — Research Agent)
  └── Program (Grant, Accelerator, VC Cohort, Ecosystem Builder)
        └── Opportunity (개별 펀딩 기회)
              ├── Application Endpoint (form, email, typeform, airtable)
              └── Observation (검증 증거)
```

---

## Organization 분류

| org_type | 설명 | 예시 |
|----------|------|------|
| vc | 벤처 캐피탈 | a16z, Paradigm, Polychain |
| foundation | 재단 (grant 운영) | Ethereum Foundation, Solana Foundation |
| accelerator | 액셀러레이터 | Alliance DAO, Outlier Ventures, Y Combinator |
| ecosystem | 생태계 지원 조직 | NEAR, Avalanche, Polygon (grant + program) |

---

## Program Category 분류

| category | 설명 | 예시 |
|----------|------|------|
| grant | 보조금 (Grant) | ESP, Solana Foundation Grants, Arbitrum Grants |
| accelerator | 액셀러레이터 | Alliance, Outlier, Antler, Techstars |
| vc_cohort | VC 코호트 | Speedrun, Nitro Accelerator, Binance Labs Incubation |
| ecosystem_builder | 생태계 빌더 프로그램 | Chainlink BUILD, Polygon Village, Avalanche infraBUIDL |

> **Note:** org_type과 category는 독립적이다. 어떤 org_type의 조직이든 어떤 category의 프로그램을 운영할 수 있다.

---

## Opportunity Status

| status | 설명 | days_left |
|--------|------|-----------|
| open | 접수 중 | 계산값 |
| rolling | 상시 접수 | null (정상) |
| deadline | 마감일 있음 | 계산값 |
| upcoming | 아직 미오픈 | null |
| closed | 마감됨 | 0 |
| unknown | 상태 미확인 | null |

---

## Normalization Rules

### Organization Name
```python
def normalize_org_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r'\s+', ' ', name)
    # 접미사 제거: Foundation, Labs, Protocol, Network, DAO, Inc, Corp
    for suffix in ['foundation', 'labs', 'protocol', 'network', 'dao', 'inc', 'corp', 'co']:
        name = re.sub(rf'\s+{suffix}$', '', name)
    return name
```

### URL Normalization
```python
def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    # http → https
    scheme = 'https'
    # trailing slash 제거
    path = parsed.path.rstrip('/')
    # query string 제거
    # fragment 제거
    return f"{scheme}://{parsed.netloc}{path}"
```

---

## Dedup Rules

### Organization Dedup (3단계)

| 단계 | 기준 | confidence |
|------|------|-----------|
| 1 | `domain` 일치 | 1.0 (확정) |
| 2 | `normalized_name` 일치 | 0.90 |
| 3 | alias 목록 매칭 | alias별 상이 |

### Program Dedup
- `(org_id, normalized_name)` UNIQUE constraint
- 같은 조직의 같은 이름 프로그램 = 동일

### Opportunity Dedup (2단계)

| 단계 | 기준 | confidence |
|------|------|-----------|
| 1 | `normalized_url` 일치 | 1.0 (확정) |
| 2 | `(program_id, cycle_key, label_fingerprint)` 일치 | 0.85+ |

### Merge Policy
- **Auto merge:** confidence ≥ 0.85
- **Review queue:** confidence < 0.85 → 강제 merge 금지
- **Conflict resolution:** 신규 데이터의 source_tier가 기존보다 높으면(숫자 작으면) 신규 채택

---

## Fact vs AI Reasoning 경계

| 분류 | 필드 | 저장 위치 | 생성자 |
|------|------|---------|--------|
| Fact | deadline_at, status, apply_url, budget_amount | opportunities | Discovery + Verification |
| Fact | source_tier, fact_confidence, evidence_json | opportunities | Verification |
| Fact | portfolio_count, avg_check_size, focus_areas | organization_dossiers | Research |
| AI Reasoning | fit_score, priority_score, why_fit | fit_recommendations | Matching |
| AI Reasoning | next_action, urgency_score | fit_recommendations | Matching |

**규칙:** Fact 필드에 AI 추측값 저장 금지. AI Reasoning은 반드시 fit_recommendations 테이블에만.
