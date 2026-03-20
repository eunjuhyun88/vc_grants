-- Funding Intelligence Agent — DB Schema
-- Phase 1: organizations, programs, opportunities, application_endpoints, observations, company_profiles
-- Phase 2+: organization_aliases, organization_dossiers, fit_recommendations, change_events, submission_tasks

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ============================================================
-- Phase 1 Tables
-- ============================================================

CREATE TABLE IF NOT EXISTS organizations (
    id              TEXT PRIMARY KEY,
    normalized_name TEXT NOT NULL,
    display_name    TEXT,
    domain          TEXT UNIQUE,                -- dedup 기준 1순위
    org_type        TEXT,                       -- 'vc' | 'ecosystem' | 'foundation' | 'accelerator'
    sector_tags     TEXT,                       -- JSON array
    website_url     TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS programs (
    id              TEXT PRIMARY KEY,
    org_id          TEXT NOT NULL REFERENCES organizations(id),
    normalized_name TEXT NOT NULL,
    display_name    TEXT,
    category        TEXT NOT NULL,              -- 'grant' | 'accelerator' | 'vc_cohort' | 'ecosystem_builder'
    program_url     TEXT,
    description     TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(org_id, normalized_name)             -- dedup 기준
);

CREATE TABLE IF NOT EXISTS opportunities (
    id              TEXT PRIMARY KEY,
    program_id      TEXT NOT NULL REFERENCES programs(id),
    cycle_key       TEXT,                       -- 'S2024' 등 배치 식별자
    status          TEXT NOT NULL DEFAULT 'unknown',
                                                -- 'open' | 'rolling' | 'upcoming' | 'closed' | 'unknown'
    deadline_at     TIMESTAMP,                  -- null 허용 (rolling)
    days_left       INTEGER,                    -- 계산값
    budget_amount   REAL,
    budget_currency TEXT DEFAULT 'USD',
    budget_note     TEXT,                       -- '최대 $500K' 등
    apply_url       TEXT,                       -- null이면 output 제외
    output_status   TEXT DEFAULT 'pending',     -- 'verified' | 'pending' | 'rejected'
    fact_confidence REAL DEFAULT 0.0,
    source_tier     INTEGER,                    -- 1~5
    evidence_json   TEXT,                       -- JSON array
    source_chain    TEXT,                       -- JSON array of source URLs
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS application_endpoints (
    id              TEXT PRIMARY KEY,
    opportunity_id  TEXT NOT NULL REFERENCES opportunities(id),
    endpoint_type   TEXT,                       -- 'form' | 'email' | 'typeform' | 'airtable'
    url             TEXT NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    verified_at     TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS observations (
    id              TEXT PRIMARY KEY,
    opportunity_id  TEXT REFERENCES opportunities(id),
    org_id          TEXT REFERENCES organizations(id),
    source_url      TEXT NOT NULL,
    source_tier     INTEGER NOT NULL,           -- 1~5
    observed_data   TEXT,                       -- JSON
    confidence      REAL DEFAULT 0.0,
    observed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS company_profiles (
    id              TEXT PRIMARY KEY,
    company_name    TEXT NOT NULL,
    stage           TEXT,                       -- 'idea' | 'mvp' | 'seed' | 'series_a' | ...
    sector_tags     TEXT,                       -- JSON array
    subsector_tags  TEXT,                       -- JSON array
    projects        TEXT,                       -- JSON array: [{name, priority, tags}]
    description     TEXT,
    geography       TEXT,                       -- 'South Korea' | 'Global' etc.
    funding_goal    TEXT,                       -- '$500K-$1M' etc.
    product_summary TEXT,
    target_ecosystems TEXT,                     -- JSON array: ["ethereum", "solana"]
    telegram_user_id INTEGER,                   -- Telegram 사용자 연결 (multi-user)
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- Phase 2+ Tables (MVP 이후 추가)
-- ============================================================

CREATE TABLE IF NOT EXISTS organization_aliases (
    id              TEXT PRIMARY KEY,
    org_id          TEXT NOT NULL REFERENCES organizations(id),
    alias           TEXT NOT NULL,
    source          TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(org_id, alias)
);

CREATE TABLE IF NOT EXISTS organization_dossiers (
    id              TEXT PRIMARY KEY,
    org_id          TEXT NOT NULL REFERENCES organizations(id),
    portfolio_count INTEGER,
    avg_check_size  TEXT,
    focus_areas     TEXT,                       -- JSON array
    decision_makers TEXT,                       -- JSON array
    raw_intel       TEXT,                       -- JSON
    fetched_at      TIMESTAMP,
    confidence      REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS fit_recommendations (
    id                  TEXT PRIMARY KEY,
    opportunity_id      TEXT NOT NULL REFERENCES opportunities(id),
    company_profile_id  TEXT NOT NULL REFERENCES company_profiles(id),
    project_name        TEXT,                   -- 'HOOT' | 'StockClaw' 등
    fit_score           REAL NOT NULL,          -- 0.0~1.0
    priority_score      REAL,                   -- 5-factor 가중 합산
    why_fit             TEXT,
    next_action         TEXT,
    urgency_score       REAL,
    actionability_score REAL,                   -- 지원 실행 가능성
    expected_value      REAL,
    confidence          REAL,
    computed_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(opportunity_id, company_profile_id)
);

CREATE TABLE IF NOT EXISTS change_events (
    id              TEXT PRIMARY KEY,
    entity_type     TEXT NOT NULL,              -- 'opportunity' | 'program' | 'organization'
    entity_id       TEXT NOT NULL,
    change_type     TEXT NOT NULL,              -- 'deadline_updated' | 'status_changed' | 'new_opportunity' | 'closed'
    old_value       TEXT,                       -- JSON
    new_value       TEXT,                       -- JSON
    detected_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notified        BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS submission_tasks (
    id              TEXT PRIMARY KEY,
    opportunity_id  TEXT NOT NULL REFERENCES opportunities(id),
    status          TEXT DEFAULT 'todo',        -- 'todo' | 'in_progress' | 'submitted' | 'rejected' | 'accepted'
    assigned_to     TEXT,
    notes           TEXT,
    due_at          TIMESTAMP,
    submitted_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS social_monitoring_events (
    id                      TEXT PRIMARY KEY,
    source_url              TEXT NOT NULL UNIQUE,
    matched_account         TEXT,
    matched_account_type    TEXT,
    monitoring_round        TEXT,
    organization            TEXT,
    program                 TEXT,
    category                TEXT,
    signal_type             TEXT,
    apply_url               TEXT,
    source_tier             INTEGER DEFAULT 5,
    confidence              REAL DEFAULT 0.0,
    promoted_opportunity_id TEXT REFERENCES opportunities(id),
    verification_status     TEXT DEFAULT 'pending',
    notified                BOOLEAN DEFAULT FALSE,
    discovered_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notified_at             TIMESTAMP
);

-- ============================================================
-- Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_orgs_normalized_name ON organizations(normalized_name);
CREATE INDEX IF NOT EXISTS idx_orgs_domain ON organizations(domain);
CREATE INDEX IF NOT EXISTS idx_programs_org_id ON programs(org_id);
CREATE INDEX IF NOT EXISTS idx_programs_category ON programs(category);
CREATE INDEX IF NOT EXISTS idx_opps_program_id ON opportunities(program_id);
CREATE INDEX IF NOT EXISTS idx_opps_status ON opportunities(status);
CREATE INDEX IF NOT EXISTS idx_opps_output_status ON opportunities(output_status);
CREATE INDEX IF NOT EXISTS idx_opps_deadline ON opportunities(deadline_at);
CREATE INDEX IF NOT EXISTS idx_endpoints_opp_id ON application_endpoints(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_observations_opp_id ON observations(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_observations_org_id ON observations(org_id);
CREATE INDEX IF NOT EXISTS idx_profiles_telegram ON company_profiles(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_fit_opp_profile ON fit_recommendations(opportunity_id, company_profile_id);
CREATE INDEX IF NOT EXISTS idx_change_events_entity ON change_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_social_events_status ON social_monitoring_events(verification_status, notified);
CREATE INDEX IF NOT EXISTS idx_social_events_round ON social_monitoring_events(monitoring_round);
CREATE INDEX IF NOT EXISTS idx_social_events_opp ON social_monitoring_events(promoted_opportunity_id);
