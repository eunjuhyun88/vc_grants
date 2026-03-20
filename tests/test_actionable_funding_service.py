from __future__ import annotations

import pytest

from src.core.config import Config
from src.core.types import (
    ApplicationEndpoint,
    CompanyProfile,
    CompanyStage,
    EndpointType,
    MatchingOutput,
    Opportunity,
    OpportunityStatus,
    Organization,
    OrgType,
    OutputStatus,
    Program,
    ProgramCategory,
)
from src.db.entity_store import EntityStore
from src.research.actionable_funding_service import build_actionable_funding_view
from src.search.research_reflection import ReflectionSeeds
from src.search.funding_orchestrator import FundingSearchResult


@pytest.mark.asyncio
async def test_build_actionable_funding_view_uses_shared_actionable_path(tmp_path, monkeypatch):
    async with EntityStore(tmp_path / "test.db") as store:
        await store.init_schema()
        captured: dict[str, object] = {}

        org = Organization(
            id="org_monad",
            normalized_name="monad",
            display_name="Monad",
            org_type=OrgType.ECOSYSTEM,
        )
        await store.create_organization(org)
        program = Program(
            id="prg_nitro",
            org_id=org.id,
            normalized_name="nitro accelerator",
            display_name="Nitro Accelerator",
            category=ProgramCategory.VC_COHORT,
            description="12-week accelerator for crypto infra teams.",
            program_url="https://nitroacc.xyz",
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
        pending = Opportunity(
            id="opp_pending",
            program_id=program.id,
            status=OpportunityStatus.OPEN,
            apply_url="https://nitroacc.xyz/waitlist",
            output_status=OutputStatus.PENDING,
            fact_confidence=0.90,
        )
        await store.create_opportunity(good)
        await store.create_opportunity(pending)
        await store.create_endpoint(
            ApplicationEndpoint(
                id="ep_good",
                opportunity_id=good.id,
                endpoint_type=EndpointType.FORM,
                url="https://nitroacc.xyz/apply",
                is_active=True,
            )
        )

        profile = CompanyProfile(
            id="cp_hoot",
            company_name="Infra",
            stage=CompanyStage.MVP,
            sector_tags=["ai_infra", "crypto_infra"],
            projects=[{"name": "HOOT", "priority": 1, "tags": ["ai_infra", "crypto_infra"]}],
        )

        async def mock_search_for_project(
            self,
            profile,
            intent="default",
            top_n=15,
            mode="fast",
            search_hints=None,
            bootstrap_terms=None,
        ):
            captured["search_hints"] = list(search_hints or [])
            captured["bootstrap_terms"] = list(bootstrap_terms or [])
            return FundingSearchResult(
                ranked_results=[
                    MatchingOutput(
                        opportunity_id="opp_good",
                        project_name="HOOT",
                        fit_score=0.82,
                        priority_score=0.74,
                        why_fit="vc cohort 기준 ai infra / crypto infra thesis fit 높음 · 현재 open",
                        next_action="이번 주 내 지원서 제출",
                    ),
                    MatchingOutput(
                        opportunity_id="opp_pending",
                        project_name="HOOT",
                        fit_score=0.40,
                        priority_score=0.32,
                        why_fit="기본 적합성 확인",
                        next_action="요건 확인",
                    ),
                ],
                reference_count=2,
                total_raw=2,
                total_ingested=2,
            )

        monkeypatch.setattr(
            "src.research.actionable_funding_service.resolve_runtime_reflection_seeds",
            lambda **kwargs: ReflectionSeeds(
                search_hints=["Nitro Accelerator apply official"],
                bootstrap_terms=["Nitro Accelerator"],
            ),
        )
        monkeypatch.setattr(
            "src.research.actionable_funding_service.load_program_registry",
            lambda: [],
        )
        monkeypatch.setattr(
            "src.research.actionable_funding_service.enrich_cards_from_registry",
            lambda cards, registry: cards,
        )
        monkeypatch.setattr(
            "src.research.actionable_funding_service.FundingSearchOrchestrator.search_for_project",
            mock_search_for_project,
        )

        view = await build_actionable_funding_view(
            store=store,
            config=Config(),
            profile=profile,
            intent="default",
            mode="fast",
        )

        assert view.project_name == "HOOT"
        assert view.reflection_seeds.search_hints == ["Nitro Accelerator apply official"]
        assert [card.program for card in view.actionable_cards] == ["Nitro Accelerator"]
        assert view.actionable_cards[0].apply_url == "https://nitroacc.xyz/apply"
        assert captured["search_hints"] == ["Nitro Accelerator apply official"]
        assert captured["bootstrap_terms"] == ["Nitro Accelerator"]
