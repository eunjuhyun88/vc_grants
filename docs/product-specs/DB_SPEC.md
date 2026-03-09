# DB_SPEC — src/db/entity_store.py + schema.sql

## schema.sql

`docs/design-docs/DB_SCHEMA.md`에 정의된 DDL 그대로 사용.
MVP Phase 1에서는 6개 테이블만 생성:
- organizations, programs, opportunities, application_endpoints, observations, company_profiles

Phase 2+에서 추가:
- organization_aliases, organization_dossiers, fit_recommendations, change_events, submission_tasks

---

## src/core/config.py

```python
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

@dataclass(frozen=True)
class Config:
    db_path: Path = Path(os.getenv("DB_PATH", "data/funding.db"))
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    anthropic_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    tavily_key: str = os.getenv("TAVILY_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
    llm_model_fast: str = os.getenv("LLM_MODEL_FAST", "claude-haiku-4-20250414")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

config = Config()
```

---

## src/db/entity_store.py — 전체 함수 시그니처

### 초기화

```python
import aiosqlite
from pathlib import Path
from src.core.config import config

class EntityStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or config.db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """DB 연결. 없으면 생성 + schema 실행."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA foreign_keys = ON")
        await self._db.execute("PRAGMA journal_mode = WAL")

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def init_schema(self) -> None:
        """schema.sql 실행하여 테이블 생성."""
        schema_path = Path(__file__).parent / "schema.sql"
        schema = schema_path.read_text()
        await self._db.executescript(schema)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.close()
```

### Organization CRUD

```python
    # --- Organization ---

    async def create_organization(self, org: Organization) -> str:
        """조직 생성. 반환: org.id"""

    async def get_organization(self, org_id: str) -> Organization | None:
        """ID로 조직 조회."""

    async def get_organization_by_domain(self, domain: str) -> Organization | None:
        """도메인으로 조직 조회 (dedup 기준 1순위)."""

    async def get_organization_by_name(self, normalized_name: str) -> Organization | None:
        """정규화된 이름으로 조직 조회."""

    async def list_organizations(
        self,
        org_type: OrgType | None = None,
        limit: int = 50
    ) -> list[Organization]:
        """조직 목록 조회. org_type 필터 선택."""

    async def update_organization(self, org_id: str, **fields) -> None:
        """조직 필드 업데이트. updated_at 자동 갱신."""
```

### Program CRUD

```python
    # --- Program ---

    async def create_program(self, program: Program) -> str:
        """프로그램 생성. UNIQUE(org_id, normalized_name) 위반 시 에러."""

    async def get_program(self, program_id: str) -> Program | None:
        """ID로 프로그램 조회."""

    async def get_program_by_org_and_name(
        self, org_id: str, normalized_name: str
    ) -> Program | None:
        """조직 + 정규화 이름으로 프로그램 조회 (dedup 기준)."""

    async def list_programs(
        self,
        org_id: str | None = None,
        category: ProgramCategory | None = None,
        limit: int = 50
    ) -> list[Program]:
        """프로그램 목록. org_id 또는 category 필터."""
```

### Opportunity CRUD

```python
    # --- Opportunity ---

    async def create_opportunity(self, opp: Opportunity) -> str:
        """기회 생성. program_id 필수."""

    async def get_opportunity(self, opp_id: str) -> Opportunity | None:
        """ID로 기회 조회."""

    async def update_opportunity(self, opp_id: str, **fields) -> None:
        """기회 필드 업데이트. deadline 변경 시 기존 record UPDATE, 새 row 생성 금지."""

    async def list_opportunities_curated(
        self,
        company_profile_id: str | None = None,
        category: ProgramCategory | None = None,
        min_confidence: float = 0.75,
        limit: int = 10
    ) -> list[dict]:
        """
        Curated View 조회 — Eligibility Filter 적용.
        조건: verified + confidence ≥ min + tier ≤ 2 + apply_url + not closed.
        JOIN: organizations, programs, fit_recommendations (LEFT).
        정렬: priority_score DESC, fallback: fact_confidence DESC, days_left ASC.
        """

    async def count_opportunities(
        self,
        category: ProgramCategory | None = None,
        status: OpportunityStatus | None = None
    ) -> int:
        """기회 수 카운트."""
```

### Observation CRUD

```python
    # --- Observation ---

    async def create_observation(self, obs: Observation) -> str:
        """검증 증거 저장."""

    async def list_observations(
        self,
        opportunity_id: str | None = None,
        org_id: str | None = None
    ) -> list[Observation]:
        """특정 기회 또는 조직의 observation 목록."""
```

### Application Endpoint CRUD

```python
    # --- Application Endpoint ---

    async def create_endpoint(self, ep: ApplicationEndpoint) -> str:
        """지원 엔드포인트 저장."""

    async def get_active_endpoints(self, opportunity_id: str) -> list[ApplicationEndpoint]:
        """활성 엔드포인트 목록."""
```

### Company Profile CRUD

```python
    # --- Company Profile ---

    async def create_company_profile(self, profile: CompanyProfile) -> str:
        """사용자 프로필 생성."""

    async def get_company_profile(self, profile_id: str) -> CompanyProfile | None:
        """ID로 프로필 조회."""

    async def get_profile_by_telegram_user(self, telegram_user_id: int) -> CompanyProfile | None:
        """Telegram 사용자 ID로 프로필 조회."""

    async def update_company_profile(self, profile_id: str, **fields) -> None:
        """프로필 업데이트."""
```

### Fit Recommendations (Phase 2)

```python
    # --- Fit Recommendations (Phase 2) ---

    async def upsert_fit_recommendation(self, rec: FitRecommendation) -> str:
        """fit 추천 생성 또는 갱신. (opportunity_id, company_profile_id) 기준."""

    async def get_fit_recommendations(
        self,
        company_profile_id: str,
        top_n: int = 10
    ) -> list[FitRecommendation]:
        """프로필 기준 상위 N개 fit 추천. priority_score DESC."""
```

---

## src/db/queries.py — SQL 쿼리 상수

```python
CURATED_VIEW_SQL = """
SELECT
    o.id, o.status, o.deadline_at, o.days_left,
    o.budget_amount, o.budget_currency, o.budget_note,
    o.apply_url, o.output_status, o.fact_confidence, o.source_tier,
    p.display_name AS program_name,
    p.category,
    org.display_name AS org_name,
    fr.fit_score,
    fr.priority_score,
    fr.why_fit,
    fr.next_action
FROM opportunities o
JOIN programs p ON o.program_id = p.id
JOIN organizations org ON p.org_id = org.id
LEFT JOIN fit_recommendations fr
    ON fr.opportunity_id = o.id
    AND fr.company_profile_id = :company_profile_id
WHERE
    o.output_status = 'verified'
    AND o.fact_confidence >= :min_confidence
    AND o.source_tier <= 2
    AND o.apply_url IS NOT NULL
    AND o.status != 'closed'
"""

CURATED_VIEW_CATEGORY_FILTER = """
    AND p.category = :category
"""

CURATED_VIEW_ORDER = """
ORDER BY
    COALESCE(fr.priority_score, 0) DESC,
    o.fact_confidence DESC,
    COALESCE(o.days_left, 9999) ASC
LIMIT :limit
"""

COUNT_BY_CATEGORY = """
SELECT COUNT(*) FROM opportunities o
JOIN programs p ON o.program_id = p.id
WHERE p.category = :category
"""
```

---

## Seed Data: data/seed/hoot_profile.json

```json
{
    "id": "cp_hoot",
    "company_name": "Holo Studio",
    "stage": "mvp",
    "sector_tags": [
        "ai_infra",
        "decentralized_ai",
        "crypto_infra",
        "distributed_compute",
        "personal_model_training"
    ],
    "projects": [
        {
            "name": "HOOT",
            "priority": 1,
            "tags": ["ai_infra", "decentralized_ai", "personal_model_training", "distributed_compute", "blockchain"]
        },
        {
            "name": "StockClaw",
            "priority": 2,
            "tags": ["ai", "fintech"]
        },
        {
            "name": "MoltVC",
            "priority": 3,
            "tags": ["vc", "ai"]
        },
        {
            "name": "PlayArts",
            "priority": 4,
            "tags": ["gaming", "ai"]
        },
        {
            "name": "ClawGene",
            "priority": 5,
            "tags": ["ai", "biotech"]
        }
    ],
    "description": "개인 데이터 기반 소형모델(Qwen 등) 학습 + 분산 컴퓨팅(토렌트 개념) + 블록체인 coordination",
    "telegram_user_id": null
}
```

---

## 테스트: tests/test_entity_store.py

```python
import pytest
import pytest_asyncio
from pathlib import Path
from src.db.entity_store import EntityStore
from src.core.types import *

@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = tmp_path / "test.db"
    async with EntityStore(db_path) as s:
        await s.init_schema()
        yield s

# --- 테스트 케이스 ---

async def test_create_and_get_organization(store):
    """조직 생성 후 조회."""

async def test_organization_dedup_by_domain(store):
    """같은 domain으로 조직 생성 시 에러 또는 기존 반환."""

async def test_create_program_requires_org(store):
    """존재하지 않는 org_id로 프로그램 생성 시 FK 에러."""

async def test_create_opportunity_requires_program(store):
    """program_id 없이 기회 생성 시 에러."""

async def test_curated_view_filter(store):
    """verified + confidence ≥ 0.75 + tier ≤ 2만 반환."""

async def test_curated_view_excludes_closed(store):
    """status='closed'는 curated view에서 제외."""

async def test_curated_view_excludes_no_apply_url(store):
    """apply_url=None은 curated view에서 제외."""

async def test_company_profile_crud(store):
    """프로필 생성, 조회, 업데이트."""

async def test_profile_by_telegram_user(store):
    """telegram_user_id로 프로필 조회."""

async def test_seed_data_load(store):
    """hoot_profile.json seed 데이터 정상 로드."""
```
