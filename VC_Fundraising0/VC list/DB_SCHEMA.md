# Funding Intelligence Agent — DB Schema

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-03-08 | 초기 작성 (11 tables) |

---

## 구현 상태

| 테이블 | entity_store.py | Phase |
|--------|----------------|-------|
| organizations | ✅ | - |
| organization_aliases | ❌ 미구현 | Phase 1 |
| organization_dossiers | ✅ | - |
| programs | ✅ | - |
| opportunities | ✅ | - |
| application_endpoints | ✅ | - |
| observations | ✅ | - |
| company_profiles | ✅ | - |
| fit_recommendations | ❌ 미구현 | Phase 1 |
| change_events | ❌ 미구현 | Phase 1 |
| submission_tasks | ✅ | - |

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

### organization_aliases ❌ Phase 1
```sql
CREATE TABLE organization_aliases (
  id              TEXT PRIMARY KEY,
  org_id          TEXT NOT NULL REFERENCES organizations(id),
  alias           TEXT NOT NULL,
  source          TEXT,                 -- 어디서 이 alias를 발견했는지
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(org_id, alias)
);
```

### organization_dossiers
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
  category        TEXT NOT NULL,        -- 아래 enum 참조
  program_url     TEXT,
  description     TEXT,
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(org_id, normalized_name)       -- dedup 기준
);
-- category enum:
-- 'grant_round' | 'ecosystem_program' | 'accelerator_cohort'
-- 'fellowship' | 'open_fund' | 'scout'
```

### opportunities
```sql
CREATE TABLE opportunities (
  id              TEXT PRIMARY KEY,
  program_id      TEXT NOT NULL REFERENCES programs(id),  -- 필수. null 불가
  cycle_key       TEXT,                 -- 'S2024' 등 배치 식별자
  status          TEXT NOT NULL DEFAULT 'unknown',
  deadline_at     TIMESTAMP,            -- null 허용 (rolling 등)
  days_left       INTEGER,              -- 계산값, deadline_at 기반
  budget_amount   REAL,
  budget_currency TEXT DEFAULT 'USD',
  budget_note     TEXT,                 -- '최대 $500K' 등 텍스트
  apply_url       TEXT,                 -- null이면 output 제외
  output_status   TEXT DEFAULT 'pending',  -- 'verified' | 'pending' | 'rejected'
  fact_confidence REAL DEFAULT 0.0,
  source_tier     INTEGER,              -- 1~5
  evidence_json   TEXT,                 -- JSON array of observations
  source_chain    TEXT,                 -- JSON array of source URLs
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- status enum:
-- 'open' | 'rolling' | 'deadline' | 'upcoming' | 'closed' | 'unknown'
-- output_status: 'verified'만 Telegram 출력 대상
```

**중요 규칙:**
- `program_id` NOT NULL — Program 없이 Opportunity 생성 불가
- `deadline_at` NULL 허용 — rolling grant는 null이 정상값, 삭제 금지
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
  source_tier     INTEGER NOT NULL,     -- 1=공식, 2=ecosystem, 3=블로그, 4=뉴스, 5=SNS
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
-- Holo Studio 프로필 초기값: docs/HOOT_FUNDING_LIST.md 참조
```

### fit_recommendations ❌ Phase 1
```sql
CREATE TABLE fit_recommendations (
  id                  TEXT PRIMARY KEY,
  opportunity_id      TEXT NOT NULL REFERENCES opportunities(id),
  company_profile_id  TEXT NOT NULL REFERENCES company_profiles(id),
  project_name        TEXT,             -- 'HOOT' | 'StockClaw' 등
  fit_score           REAL NOT NULL,    -- 0.0~1.0
  priority_score      REAL,            -- 가중 합산 점수
  why_fit             TEXT,             -- 근거 (LLM 생성, PROVIDED_FACTS 기반)
  next_action         TEXT,
  urgency_score       REAL,
  actionability       REAL,
  expected_value      REAL,
  confidence_score    REAL,
  computed_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### change_events ❌ Phase 1
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

### submission_tasks
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

## Dedup 규칙 요약

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
| 1 | 공식 사이트 | 0.95 | ✅ |
| 2 | ecosystem portal, docs | 0.90 | ✅ |
| 3 | 블로그/뉴스 | 0.80 | 보조만 |
| 4 | 집계 사이트 | 0.60 | ❌ 단독 금지 |
| 5 | SNS | 0.40 | ❌ 단독 금지 |

output eligibility: source_tier ≤ 2만 출력 대상
