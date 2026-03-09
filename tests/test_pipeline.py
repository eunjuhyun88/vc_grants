"""
Pipeline 통합 테스트 — E2E (mock 기반).

실행: pytest tests/test_pipeline.py -v
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.agents.base_agent import BaseAgent
from src.core.config import Config
from src.core.pipeline import FundingPipeline, PipelineResult
from src.core.types import (
    AgentResult,
    CompanyProfile,
    CompanyStage,
    Opportunity,
    OpportunityStatus,
    Organization,
    OrgType,
    OutputStatus,
    Program,
    ProgramCategory,
    generate_id,
)
from src.db.entity_store import EntityStore


# ============================================================
# Fixtures
# ============================================================


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    db_path = tmp_path / "test_pipeline.db"
    async with EntityStore(db_path) as s:
        await s.init_schema()
        yield s


@pytest.fixture
def cfg():
    return Config()


@pytest_asyncio.fixture
async def seeded_store(store: EntityStore):
    """시드 데이터가 있는 store."""
    profile = CompanyProfile(
        id="cp_test",
        company_name="Test Corp",
        stage=CompanyStage.MVP,
        sector_tags=["ai", "crypto"],
        projects=[{"name": "TestProject", "priority": 1, "tags": ["ai"]}],
    )
    await store.create_company_profile(profile)
    return store


# ============================================================
# PipelineResult Tests
# ============================================================


def test_pipeline_result_summary():
    """PipelineResult summary 형식."""
    result = PipelineResult(
        total_discovered=5,
        total_ingested=4,
        total_verified=3,
        total_matched=2,
        errors=["Test error"],
        elapsed_ms=1234.5,
    )
    summary = result.summary
    assert "Discovered: 5" in summary
    assert "Ingested:   4" in summary
    assert "Verified:   3" in summary
    assert "Matched:    2" in summary
    assert "Errors:     1" in summary
    assert "Test error" in summary


def test_pipeline_result_empty():
    """빈 결과."""
    result = PipelineResult()
    summary = result.summary
    assert "Discovered: 0" in summary


# ============================================================
# Ingest Tests
# ============================================================


@pytest.mark.asyncio
async def test_ingest_raw_opportunity(store: EntityStore, cfg: Config):
    """raw opportunity → DB 레코드."""
    pipeline = FundingPipeline(store=store, cfg=cfg)

    raw = {
        "organization": "Ethereum Foundation",
        "program": "ESP Grants",
        "category": "grant",
        "status": "open",
        "deadline": "2026-06-01",
        "budget": "$50K-$500K",
        "apply_url": "https://esp.ethereum.foundation/apply",
        "source_url": "https://esp.ethereum.foundation",
    }

    opp_id = await pipeline._ingest_raw_opportunity(raw)

    assert opp_id is not None

    # Organization이 생성되었는지
    org = await store.get_organization_by_name("ethereum")
    assert org is not None

    # Program이 생성되었는지
    program = await store.get_program_by_org_and_name(
        org.id, "esp grants"
    )
    assert program is not None
    assert program.category == ProgramCategory.GRANT

    # Opportunity가 생성되었는지
    opp = await store.get_opportunity(opp_id)
    assert opp is not None
    assert opp.status == OpportunityStatus.OPEN
    assert opp.budget_amount == 500000.0  # $500K 파싱


@pytest.mark.asyncio
async def test_ingest_dedup(store: EntityStore, cfg: Config):
    """같은 organization → 중복 생성 안됨."""
    pipeline = FundingPipeline(store=store, cfg=cfg)

    raw1 = {
        "organization": "Solana Foundation",
        "program": "Grant Program",
        "category": "grant",
        "status": "open",
    }
    raw2 = {
        "organization": "Solana Foundation",
        "program": "Developer Fund",
        "category": "grant",
        "status": "rolling",
    }

    await pipeline._ingest_raw_opportunity(raw1)
    await pipeline._ingest_raw_opportunity(raw2)

    # Organization은 1개만 존재
    org = await store.get_organization_by_name("solana")
    assert org is not None

    # Program은 2개
    programs = await store.list_programs(org_id=org.id)
    assert len(programs) == 2


@pytest.mark.asyncio
async def test_ingest_empty_fields(store: EntityStore, cfg: Config):
    """필수 필드 없으면 None 반환."""
    pipeline = FundingPipeline(store=store, cfg=cfg)

    raw = {"organization": "", "program": ""}
    result = await pipeline._ingest_raw_opportunity(raw)
    assert result is None


# ============================================================
# Budget Parsing Tests
# ============================================================


def test_parse_budget_amount():
    """예산 텍스트 → 금액 파싱."""
    pipeline_cls = FundingPipeline.__new__(FundingPipeline)

    assert pipeline_cls._parse_budget_amount("$500K") == 500000.0
    assert pipeline_cls._parse_budget_amount("$50K-$500K") == 500000.0
    assert pipeline_cls._parse_budget_amount("$1M") == 1000000.0
    assert pipeline_cls._parse_budget_amount("$200,000") == 200000.0
    assert pipeline_cls._parse_budget_amount(None) is None
    assert pipeline_cls._parse_budget_amount("TBD") is None


# ============================================================
# Full Pipeline Test (Mock)
# ============================================================


@pytest.mark.asyncio
async def test_pipeline_with_mock_discovery(seeded_store: EntityStore, cfg: Config):
    """Discovery를 mock하여 전체 파이프라인 테스트."""
    pipeline = FundingPipeline(store=seeded_store, cfg=cfg)

    # Discovery mock
    mock_discovery_output = AgentResult(
        success=True,
        data={
            "raw_opportunities": [
                {
                    "organization": "Test Foundation",
                    "program": "Test Grant",
                    "category": "grant",
                    "status": "open",
                    "budget": "$100K",
                    "apply_url": "https://test.com/apply",
                    "source_url": "https://test.com",
                },
            ],
            "source_urls": ["https://test.com"],
            "fetched_at": "2026-03-09T00:00:00",
        },
    )
    pipeline.discovery.run = AsyncMock(return_value=mock_discovery_output)

    # Verification mock (URL 접근 불필요하게)
    mock_verify_output = AgentResult(
        success=True,
        data={
            "opportunity_id": "dummy",
            "output_status": "pending",
            "fact_confidence": 0.5,
            "source_tier": 3,
            "evidence": [],
            "verified_at": "2026-03-09T00:00:00",
        },
    )
    pipeline.verification.run = AsyncMock(return_value=mock_verify_output)

    result = await pipeline.run_discovery_pipeline(
        query="test grants",
        category=ProgramCategory.GRANT,
        company_profile_id="cp_test",
    )

    assert result.total_discovered == 1
    assert result.total_ingested == 1
    assert result.total_verified == 1
    assert result.total_matched == 1
    assert result.elapsed_ms > 0


@pytest.mark.asyncio
async def test_pipeline_partial_failure(seeded_store: EntityStore, cfg: Config):
    """Discovery 실패해도 pipeline 자체는 안 죽음."""
    pipeline = FundingPipeline(store=seeded_store, cfg=cfg)

    # Discovery 실패
    pipeline.discovery.run = AsyncMock(
        return_value=AgentResult(success=False, error="API timeout")
    )

    result = await pipeline.run_discovery_pipeline(
        query="failing query",
    )

    assert result.total_discovered == 0
    assert result.total_ingested == 0
    assert len(result.errors) >= 1
    assert "Discovery failed" in result.errors[0]
