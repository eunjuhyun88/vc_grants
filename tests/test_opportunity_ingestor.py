from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from src.core.opportunity_ingestor import OpportunityIngestor
from src.core.types import OpportunityStatus, ProgramCategory
from src.db.entity_store import EntityStore


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    db_path = tmp_path / "test_ingestor.db"
    async with EntityStore(db_path) as s:
        await s.init_schema()
        yield s


@pytest.mark.asyncio
async def test_opportunity_ingestor_ingests_raw_opportunity(store: EntityStore):
    ingestor = OpportunityIngestor(store)

    opp_id = await ingestor.ingest_raw_opportunity(
        {
            "organization": "Ethereum Foundation",
            "program": "ESP Grants",
            "category": "grant",
            "status": "open",
            "deadline": "2026-06-01",
            "budget": "$50K-$500K",
            "apply_url": "https://esp.ethereum.foundation/apply",
            "source_url": "https://esp.ethereum.foundation",
        }
    )

    assert opp_id is not None

    org = await store.get_organization_by_name("ethereum")
    assert org is not None

    program = await store.get_program_by_org_and_name(org.id, "esp grants")
    assert program is not None
    assert program.category == ProgramCategory.GRANT

    opp = await store.get_opportunity(opp_id)
    assert opp is not None
    assert opp.status == OpportunityStatus.OPEN


def test_opportunity_ingestor_parse_budget_amount():
    assert OpportunityIngestor.parse_budget_amount("$500K") == 500000.0
    assert OpportunityIngestor.parse_budget_amount("$50K-$500K") == 500000.0
    assert OpportunityIngestor.parse_budget_amount("$1M") == 1000000.0
    assert OpportunityIngestor.parse_budget_amount(None) is None
