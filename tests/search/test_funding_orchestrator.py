from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.core.config import Config
from src.core.opportunity_matcher import MatchingOutcome
from src.core.opportunity_verifier import VerificationOutcome
from src.core.types import (
    ApplicationEndpoint,
    EndpointType,
    Opportunity,
    OpportunityStatus,
    OutputStatus,
    Program,
    ProgramCategory,
    Organization,
    OrgType,
)
from src.db.entity_store import EntityStore
from src.search.funding_orchestrator import FundingSearchOrchestrator, _combine_query_batch, _merge_seed_queries


def test_merge_seed_queries_preserves_order_and_dedups():
    merged = _merge_seed_queries(
        ["ethereum grants", "solana grants"],
        ["solana grants", "Nitro Accelerator apply", " "],
    )

    assert merged == [
        "ethereum grants",
        "solana grants",
        "Nitro Accelerator apply",
    ]


def test_combine_query_batch_uses_all_queries():
    combined = _combine_query_batch(
        ["q1", "q2", "q3", "q4"]
    )

    assert combined == "q1 OR q2 OR q3 OR q4"


@pytest.mark.asyncio
async def test_search_web_runs_queries_individually(tmp_path, monkeypatch):
    async with EntityStore(tmp_path / "test.db") as store:
        await store.init_schema()
        orchestrator = FundingSearchOrchestrator(store=store, config=Config())
        seen_queries: list[str] = []

        async def mock_search(query: str, category=None, sources=None):
            seen_queries.append(query)
            return (
                [{
                    "organization": query,
                    "program": f"{query} Program",
                    "category": "grant",
                    "apply_url": f"https://example.com/{len(seen_queries)}",
                }],
                [],
            )

        monkeypatch.setattr(orchestrator._web_orchestrator, "search", mock_search)

        results = await orchestrator._search_web(["q1", "q2", "q3"])

        assert seen_queries == ["q1", "q2", "q3"]
        assert len(results) == 3


@pytest.mark.asyncio
async def test_filter_rankable_opportunity_ids_keeps_only_verified_actionable_rows(tmp_path):
    async with EntityStore(tmp_path / "test.db") as store:
        await store.init_schema()
        orchestrator = FundingSearchOrchestrator(store=store, config=Config())

        org = Organization(
            id="org_1",
            normalized_name="monad",
            display_name="Monad",
            org_type=OrgType.ECOSYSTEM,
        )
        await store.create_organization(org)
        program = Program(
            id="prg_1",
            org_id=org.id,
            normalized_name="nitro accelerator",
            display_name="Nitro Accelerator",
            category=ProgramCategory.VC_COHORT,
        )
        await store.create_program(program)

        good = Opportunity(
            id="opp_good",
            program_id=program.id,
            status=OpportunityStatus.OPEN,
            apply_url="https://nitroacc.xyz/apply",
            output_status=OutputStatus.VERIFIED,
            fact_confidence=0.90,
        )
        weak = Opportunity(
            id="opp_weak",
            program_id=program.id,
            status=OpportunityStatus.OPEN,
            apply_url="https://weak.example/apply",
            output_status=OutputStatus.PENDING,
            fact_confidence=0.90,
        )
        unknown = Opportunity(
            id="opp_unknown",
            program_id=program.id,
            status=OpportunityStatus.UNKNOWN,
            apply_url="https://unknown.example/apply",
            output_status=OutputStatus.VERIFIED,
            fact_confidence=0.90,
        )
        no_apply = Opportunity(
            id="opp_no_apply",
            program_id=program.id,
            status=OpportunityStatus.OPEN,
            apply_url=None,
            output_status=OutputStatus.VERIFIED,
            fact_confidence=0.90,
        )
        low_conf = Opportunity(
            id="opp_low_conf",
            program_id=program.id,
            status=OpportunityStatus.OPEN,
            apply_url="https://lowconf.example/apply",
            output_status=OutputStatus.VERIFIED,
            fact_confidence=0.60,
        )
        no_endpoint = Opportunity(
            id="opp_no_endpoint",
            program_id=program.id,
            status=OpportunityStatus.OPEN,
            apply_url="https://noendpoint.example/apply",
            output_status=OutputStatus.VERIFIED,
            fact_confidence=0.90,
        )

        await store.create_opportunity(good)
        await store.create_opportunity(weak)
        await store.create_opportunity(unknown)
        await store.create_opportunity(no_apply)
        await store.create_opportunity(low_conf)
        await store.create_opportunity(no_endpoint)
        await store.create_endpoint(
            ApplicationEndpoint(
                id="ep_good",
                opportunity_id="opp_good",
                endpoint_type=EndpointType.FORM,
                url="https://nitroacc.xyz/apply",
                is_active=True,
            )
        )

        rankable = await orchestrator._opportunity_matcher.filter_rankable_opportunity_ids(
            [
                "opp_good",
                "opp_weak",
                "opp_unknown",
                "opp_no_apply",
                "opp_low_conf",
                "opp_no_endpoint",
            ]
        )

        assert rankable == ["opp_good"]


@pytest.mark.asyncio
async def test_verify_ingested_batch_uses_shared_verifier(tmp_path, monkeypatch):
    async with EntityStore(tmp_path / "test.db") as store:
        await store.init_schema()
        orchestrator = FundingSearchOrchestrator(store=store, config=Config())
        orchestrator_result = type(
            "Result",
            (),
            {"errors": []},
        )()

        async def fake_verify_batch(*args, **kwargs):
            return [
                VerificationOutcome(opportunity_id="opp_1", verified=True),
                VerificationOutcome(opportunity_id="opp_2", verified=False, error="timeout"),
            ]

        monkeypatch.setattr(
            orchestrator._opportunity_verifier,
            "verify_batch",
            fake_verify_batch,
        )

        verified_count = await orchestrator._verify_ingested_batch(
            ["opp_1", "opp_2"],
            orchestrator_result,
        )

        assert verified_count == 1
        assert orchestrator_result.errors == ["Verification error: opp_2: timeout"]


@pytest.mark.asyncio
async def test_ingest_and_rank_uses_shared_matcher(tmp_path, monkeypatch):
    async with EntityStore(tmp_path / "test.db") as store:
        await store.init_schema()
        orchestrator = FundingSearchOrchestrator(store=store, config=Config())

        ctx = type(
            "Ctx",
            (),
            {
                "all_raw_opps": [
                    {
                        "organization": "Monad",
                        "program": "Nitro Accelerator",
                        "category": "accelerator",
                        "status": "open",
                        "apply_url": "https://nitroacc.xyz/apply",
                    }
                ],
                "ingested_opp_ids": [],
            },
        )()
        result = type(
            "Result",
            (),
            {
                "errors": [],
                "total_ingested": 0,
                "new_discovered": 0,
                "ranked_results": [],
            },
        )()
        profile = type(
            "Profile",
            (),
            {
                "id": "cp_test",
                "company_name": "Test Corp",
                "stage": "mvp",
                "sector_tags": ["ai"],
                "projects": [],
                "target_ecosystems": [],
                "subsector_tags": [],
                "product_summary": "",
                "funding_goal": None,
                "geography": None,
            },
        )()

        monkeypatch.setattr(
            orchestrator,
            "_count_existing_programs",
            AsyncMock(side_effect=[0, 1]),
        )
        monkeypatch.setattr(
            orchestrator._pipeline,
            "ingest_raw_opportunity",
            AsyncMock(return_value="opp_1"),
        )
        monkeypatch.setattr(
            orchestrator,
            "_verify_ingested_batch",
            AsyncMock(return_value=1),
        )
        monkeypatch.setattr(
            orchestrator._store,
            "get_company_profile",
            AsyncMock(return_value=None),
        )
        monkeypatch.setattr(
            orchestrator._store,
            "create_company_profile",
            AsyncMock(),
        )
        monkeypatch.setattr(
            orchestrator._opportunity_matcher,
            "filter_rankable_opportunity_ids",
            AsyncMock(return_value=["opp_1", "opp_2"]),
        )
        monkeypatch.setattr(
            orchestrator._opportunity_matcher,
            "match_batch",
            AsyncMock(
                return_value=[
                    MatchingOutcome(opportunity_id="opp_1", matched=True),
                    MatchingOutcome(
                        opportunity_id="opp_2",
                        matched=False,
                        error="profile missing",
                    ),
                ]
            ),
        )
        monkeypatch.setattr(
            orchestrator._opportunity_matcher,
            "rank_outputs",
            lambda outcomes, top_n=None: ["ranked"],
        )

        await orchestrator._ingest_and_rank(
            ctx,
            result,
            profile,
            intent="default",
            top_n=5,
        )

        assert result.total_ingested == 1
        assert result.new_discovered == 1
        assert ctx.ingested_opp_ids == ["opp_1"]
        assert result.ranked_results == ["ranked"]
        assert result.errors == ["Matching error: opp_2: profile missing"]
