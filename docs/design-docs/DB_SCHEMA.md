# Funding Intelligence Agent — DB Schema

## 구현 계획

| 테이블 | MVP Phase | 설명 |
|--------|-----------|------|
| organizations | Phase 1 | 조직 (VC, Foundation, Accelerator) |
| organization_aliases | Phase 2 | 조직 별명 (dedup용) |
| organization_dossiers | Phase 2 | 조직 상세 정보 (Research Agent) |
| programs | Phase 1 | 프로그램 (Grant Round, Cohort 등) |
| opportunities | Phase 1 | 개별 펀딩 기회 |
| application_endpoints | Phase 1 | 지원 링크/폼 |
| observations | Phase 1 | 검증 증거 |
| company_profiles | Phase 1 | 회사 프로필 (HOOT) |
| fit_recommendations | Phase 2 | Fit 분석 결과 |
| change_events | Phase 3 | 변화 감지 이력 |
| submission_tasks | Phase 3 | 지원 태스크 관리 |

---

## Table Definitions

### organizations
```sql
CREATE TABLE organizations (
  id              TEXT PRIMARY KEY,
  normalized_name TEXT NOT NULL,
  display_name    TEXT,
  domain          TEXT UNIQUE,          -- dedup 기준 1순위
  org_type        TEXT,                 -- 'vc' | 'ecosystem' | 'foundation' | 'accelerator'
  sector_tags     TEXT,                 -- JSON array
  website_url     TEXT,
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### organization_aliases (Phase 2)
```sql
CREATE TABLE organization_aliases (
  id              TEXT PRIMARY KEY,
  org_id          TEXT NOT NULL REFERENCES organizations(id),
  alias           TEXT NOT NULL,
  source          TEXT,
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(org_id, alias)
);
```

### organization_dossiers (Phase 2)
```sql
CREATE TABLE organization_dossiers (
  id              TEXT PRIMARY KEY,
  org_id          TEXT NOT NULL REFERENCES organizations(id),
  portfolio_count INTEGER,
  avg_check_size  TEXT,
  focus_areas     TEXT,                 -- JSON array
  decision_makers TEXT,                 -- JSON array
  raw_intel       TEXT,                 -- JSON
  fetched_at      TIMESTAMP,
  confidence      REAL DEFAULT 0.0
);
```

### programs
```sql
CREATE TABLE programs (
  id              TEXT PRIMARY KEY,
  org_id          TEXT NOT NULL REFERENCES organizations(id),
  normalized_name TEXT NOT NULL,
  display_name    TEXT,
  category        TEXT NOT NULL,        -- enum 참조
  program_url     TEXT,
  description     TEXT,
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(org_id, normalized_name)       -- dedup 기준
);
-- category enum (PRD 기준 4가지):
-- 'grant' | 'accelerator' | 'vc_cohort' | 'ecosystem_builder'
```

### opportunities
```sql
CREATE TABLE opportunities (
  id              TEXT PRIMARY KEY,
  program_id      TEXT NOT NULL REFERENCES programs(id),
  cycle_key       TEXT,                 -- 'S2024' 등 배치 식별자
  status          TEXT NOT NULL DEFAULT 'unknown',
  deadline_at     TIMESTAMP,            -- null 허용 (rolling)
  days_left       INTEGER,              -- 계산값
  budget_amount   REAL,
  budget_currency TEXT DEFAULT 'USD',
  budget_note     TEXT,                 -- '최대 $500K' 등
  apply_url       TEXT,                 -- null이면 output 제외
  output_status   TEXT DEFAULT 'pending',  -- 'verified' | 'pending' | 'rejected'
  fact_confidence REAL DEFAULT 0.0,
  source_tier     INTEGER,              -- 1~5
  evidence_json   TEXT,                 -- JSON array
  source_chain    TEXT,                 -- JSON array of source URLs
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- status enum: 'open' | 'rolling' | 'deadline' | 'upcoming' | 'closed' | 'unknown'
-- output_status: 'verified'만 Telegram 출력 대상
```

**규칙:**
- `program_id` NOT NULL — Program 없이 Opportunity 생성 불가
- `deadline_at` NULL 허용 — rolling grant는 null이 정상값
- deadline 변경 → 기존 record UPDATE, 새 row 생성 금지

### application_endpoints
```sql
CREATE TABLE application_endpoints (
  id              TEXT PRIMARY KEY,
  opportunity_id  TEXT NOT NULL REFERENCES opportunities(id),
  endpoint_type   TEXT,                 -- 'form' | 'email' | 'typeform' | 'airtable'
  url             TEXT NOT NULL,
  is_active       BOOLEAN DEFAULT TRUE,
  verified_at     TIMESTAMP,
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### observations
```sql
CREATE TABLE observations (
  id              TEXT PRIMARY KEY,
  opportunity_id  TEXT REFERENCES opportunities(id),
  org_id          TEXT REFERENCES organizations(id),
  source_url      TEXT NOT NULL,
  source_tier     INTEGER NOT NULL,     -- 1~5
  observed_data   TEXT,                 -- JSON
  confidence      REAL DEFAULT 0.0,
  observed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### company_profiles
```sql
CREATE TABLE company_profiles (
  id              TEXT PRIMARY KEY,
  company_name    TEXT NOT NULL,
  stage           TEXT,                 -- 'mvp' | 'seed' | 'series_a'
  sector_tags     TEXT,                 -- JSON array
  projects        TEXT,                 -- JSON array: [{name, priority, tags}]
  description     TEXT,
  updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### fit_recommendations (Phase 2)
```sql
CREATE TABLE fit_recommendations (
  id                  TEXT PRIMARY KEY,
  opportunity_id      TEXT NOT NULL REFERENCES opportunities(id),
  company_profile_id  TEXT NOT NULL REFERENCES company_profiles(id),
  project_name        TEXT,             -- 'HOOT' | 'StockClaw' 등
  fit_score           REAL NOT NULL,    -- 0.0~1.0
  priority_score      REAL,            -- 4-factor 가중 합산
  why_fit             TEXT,
  next_action         TEXT,
  urgency_score       REAL,
  expected_value      REAL,
  confidence          REAL,
  computed_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### change_events (Phase 3)
```sql
CREATE TABLE change_events (
  id              TEXT PRIMARY KEY,
  entity_type     TEXT NOT NULL,        -- 'opportunity' | 'program' | 'organization'
  entity_id       TEXT NOT NULL,
  change_type     TEXT NOT NULL,        -- 'deadline_updated' | 'status_changed' | 'new_opportunity' | 'closed'
  old_value       TEXT,                 -- JSON
  new_value       TEXT,                 -- JSON
  detected_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  notified        BOOLEAN DEFAULT FALSE
);
```

### submission_tasks (Phase 3)
```sql
CREATE TABLE submission_tasks (
  id              TEXT PRIMARY KEY,
  opportunity_id  TEXT NOT NULL REFERENCES opportunities(id),
  status          TEXT DEFAULT 'todo',  -- 'todo' | 'in_progress' | 'submitted' | 'rejected' | 'accepted'
  assigned_to     TEXT,
  notes           TEXT,
  due_at          TIMESTAMP,
  submitted_at    TIMESTAMP,
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Dedup 규칙

### Organization dedup (3단계)
1. `domain` 일치 → 동일 org
2. `normalized_name` 일치 → 동일 org 후보 (confidence 계산)
3. alias 목록 → 동일 org 후보

### Program dedup
- `(org_id, normalized_name)` UNIQUE constraint

### Opportunity dedup
- `normalized_url` 일치 → 동일 opportunity
- `(program_id, cycle_key, label_fingerprint)` 일치 → 동일 opportunity

**Auto merge 기준:** confidence ≥ 0.85
**Review queue:** confidence < 0.85

---

## Source Tier 정의

| Tier | 설명 | confidence weight | 출력 허용 |
|------|------|-------------------|-----------|
| 1 | 공식 사이트 | 0.95 | O |
| 2 | ecosystem portal, docs | 0.90 | O |
| 3 | 블로그/뉴스 | 0.80 | 보조만 |
| 4 | 집계 사이트 | 0.60 | X 단독 금지 |
| 5 | SNS | 0.40 | X 단독 금지 |

output eligibility: source_tier ≤ 2만 출력 대상

---

## 사용자 프로필 등록 예시

company_profiles는 **멀티 유저** — 누구든 자기 프로젝트를 등록하면 맞춤 매칭.

```json
{
  "id": "cp_hoot",
  "company_name": "Holo Studio",
  "stage": "mvp",
  "sector_tags": ["ai_infra", "decentralized_ai", "crypto_infra", "distributed_compute"],
  "projects": [
    {"name": "HOOT", "priority": 1, "tags": ["ai_infra", "decentralized_ai", "distributed_compute", "blockchain"]},
    {"name": "StockClaw", "priority": 2, "tags": ["ai", "fintech"]}
  ],
  "description": "개인 데이터 기반 소형모델 학습 + 분산 컴퓨팅 + 블록체인 coordination"
}
```

각 사용자의 fit_score, priority_score는 자신의 프로필 기준으로 독립 계산됨.
