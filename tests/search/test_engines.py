"""
검색 엔진 + MultiEngineSearch 단위 테스트.

모든 외부 API는 mock — 실제 네트워크 호출 없음.
"""

from __future__ import annotations

import pytest

from src.agents.verification import (
    _analyze_page_content,
    _infer_status_from_source,
    _merge_status,
    determine_source_tier,
)
from src.core.config import Config
from src.core.profiles import get_default_profile
from src.core.types import OpportunityStatus
from src.search.engines.base import SearchEngine, SearchQuotaExceeded
from src.search.engines.brave_engine import BraveEngine
from src.search.engines.reference_engine import (
    ReferenceDataEngine,
    ReferenceResult,
    _parse_status_note,
)
from src.search.profile_query_planner import get_matching_keywords, get_priority_ecosystems
from src.search.engines.serper_engine import SerperEngine
from src.search.engines.tavily_engine import TavilyEngine
from src.search.multi_engine import MultiEngineSearch
from src.search.types import SearchResult


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def config_all_keys():
    """모든 API 키가 설정된 Config."""
    return Config(
        tavily_key="test-tavily",
        serper_key="test-serper",
        brave_key="test-brave",
    )


@pytest.fixture
def config_no_keys():
    """API 키가 없는 Config."""
    return Config(
        tavily_key="",
        serper_key="",
        brave_key="",
        groq_key="",
        anthropic_key="",
    )


# ============================================================
# Engine availability
# ============================================================

class TestEngineAvailability:
    def test_tavily_available_with_key(self, config_all_keys):
        engine = TavilyEngine(config_all_keys)
        assert engine.is_available is True
        assert engine.name == "tavily"

    def test_tavily_unavailable_without_key(self, config_no_keys):
        engine = TavilyEngine(config_no_keys)
        assert engine.is_available is False

    def test_serper_available_with_key(self, config_all_keys):
        engine = SerperEngine(config_all_keys)
        assert engine.is_available is True
        assert engine.name == "serper"

    def test_serper_unavailable_without_key(self, config_no_keys):
        engine = SerperEngine(config_no_keys)
        assert engine.is_available is False

    def test_brave_available_with_key(self, config_all_keys):
        engine = BraveEngine(config_all_keys)
        assert engine.is_available is True
        assert engine.name == "brave"

    def test_brave_unavailable_without_key(self, config_no_keys):
        engine = BraveEngine(config_no_keys)
        assert engine.is_available is False


# ============================================================
# Engine returns empty when unavailable
# ============================================================

class TestEngineUnavailable:
    @pytest.mark.asyncio
    async def test_tavily_returns_empty_no_key(self, config_no_keys):
        engine = TavilyEngine(config_no_keys)
        results = await engine.search("test query")
        assert results == []

    @pytest.mark.asyncio
    async def test_serper_returns_empty_no_key(self, config_no_keys):
        engine = SerperEngine(config_no_keys)
        results = await engine.search("test query")
        assert results == []

    @pytest.mark.asyncio
    async def test_brave_returns_empty_no_key(self, config_no_keys):
        engine = BraveEngine(config_no_keys)
        results = await engine.search("test query")
        assert results == []


# ============================================================
# Engine ABC contract
# ============================================================

class TestSearchEngineABC:
    def test_all_engines_implement_abc(self, config_all_keys):
        engines = [
            TavilyEngine(config_all_keys),
            SerperEngine(config_all_keys),
            BraveEngine(config_all_keys),
        ]
        for engine in engines:
            assert isinstance(engine, SearchEngine)
            assert isinstance(engine.name, str)
            assert isinstance(engine.is_available, bool)


# ============================================================
# MultiEngineSearch
# ============================================================

class TestMultiEngineSearch:
    def test_available_count_all_keys(self, config_all_keys):
        ms = MultiEngineSearch(config_all_keys)
        assert ms.available_count == 3

    def test_available_count_no_keys(self, config_no_keys):
        ms = MultiEngineSearch(config_no_keys)
        assert ms.available_count == 0

    def test_available_count_partial(self):
        config = Config(
            tavily_key="test-tavily",
            serper_key="",
            brave_key="",
        )
        ms = MultiEngineSearch(config)
        assert ms.available_count == 1

    @pytest.mark.asyncio
    async def test_search_all_no_engines(self, config_no_keys):
        ms = MultiEngineSearch(config_no_keys)
        results = await ms.search_all(["test query"])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_all_with_mock(self, config_all_keys, monkeypatch):
        """mock 엔진으로 search_all 동작 확인."""
        ms = MultiEngineSearch(config_all_keys)

        # 모든 엔진의 search를 mock
        async def mock_search(self, query, max_results=10):
            return [
                SearchResult(
                    url=f"https://example.com/{self.name}/{query[:5]}",
                    title=f"Result from {self.name}",
                    snippet=f"Snippet for {query}",
                    score=0.8,
                    engine=self.name,
                )
            ]

        monkeypatch.setattr(TavilyEngine, "search", mock_search)
        monkeypatch.setattr(SerperEngine, "search", mock_search)
        monkeypatch.setattr(BraveEngine, "search", mock_search)

        results = await ms.search_all(["AI grants", "DeFi grants"])

        # 3 엔진 × 2 쿼리 = 6 결과
        assert len(results) == 6
        engines_used = {r.engine for r in results}
        assert engines_used == {"tavily", "serper", "brave"}

    @pytest.mark.asyncio
    async def test_search_all_cools_down_quota_exceeded_engine(self, config_no_keys):
        class QuotaEngine(SearchEngine):
            def __init__(self):
                self.calls = 0

            @property
            def name(self) -> str:
                return "quota"

            @property
            def is_available(self) -> bool:
                return True

            async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
                self.calls += 1
                raise SearchQuotaExceeded("plan's set usage limit")

        class OkEngine(SearchEngine):
            def __init__(self):
                self.calls = 0

            @property
            def name(self) -> str:
                return "ok"

            @property
            def is_available(self) -> bool:
                return True

            async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
                self.calls += 1
                return [SearchResult(url="https://example.com", engine=self.name)]

        ms = MultiEngineSearch(config_no_keys)
        quota_engine = QuotaEngine()
        ok_engine = OkEngine()
        ms._engines = [quota_engine, ok_engine]

        first = await ms.search_all(["query one"])
        second = await ms.search_all(["query two", "query three"])

        assert len(first) == 1
        assert len(second) == 2
        assert quota_engine.calls == 1
        assert ok_engine.calls == 3


class TestReferenceEngine:
    def test_matching_keywords_include_funding_goal_terms(self):
        profile = get_default_profile("HOOT")
        keywords = get_matching_keywords(profile)

        assert "accelerator" in keywords
        assert "cohort" in keywords
        assert "grant" in keywords
        assert "vc cohort" in keywords
        assert "chainlink" in keywords

    def test_priority_ecosystems_expand_from_sector_tags(self):
        profile = get_default_profile("HOOT")
        ecosystems = get_priority_ecosystems(profile)

        assert "chainlink" in ecosystems
        assert "avalanche" in ecosystems

    def test_search_boosts_accelerators_for_accelerator_seeking_profile(self):
        profile = get_default_profile("HOOT")
        engine = ReferenceDataEngine()
        engine._loaded = True
        engine._records = [
            {
                "_source_file": "accelerator_list_final.csv",
                "organization": "Alliance",
                "program": "Alliance Accelerator",
                "program_type": "accelerator",
                "website": "https://alliance.xyz/apply",
                "apply_url": "https://alliance.xyz/apply",
                "description": "Founder program",
                "sector_tags": "web3",
                "industry_category": "",
                "funding_range": "",
                "status_note": "진행중",
            }
        ]

        results = engine.search(profile, top_n=5)

        assert len(results) == 1
        assert results[0].program == "Alliance Accelerator"
        assert results[0].match_score > 0.10

    def test_search_dedups_duplicate_reference_rows(self):
        profile = get_default_profile("HOOT")
        engine = ReferenceDataEngine()
        engine._loaded = True
        duplicate = {
            "_source_file": "fund_list_final.csv",
            "organization": "Outlier Ventures",
            "program": "Outlier Ventures Base Camp",
            "program_type": "accelerator",
            "website": "https://outlierventures.io/apply/form/",
            "apply_url": "https://outlierventures.io/apply/form/",
            "description": "Web3 accelerator",
            "sector_tags": "web3,crypto,ai",
            "industry_category": "Web3",
            "funding_range": "",
            "status_note": "진행중",
        }
        engine._records = [duplicate, duplicate.copy()]

        results = engine.search(profile, top_n=10)

        assert len(results) == 1
        assert results[0].organization == "Outlier Ventures"

    def test_to_raw_opportunities_preserves_status_description_and_program_url(self):
        engine = ReferenceDataEngine()
        results = [
            ReferenceResult(
                source_file="grant_list_final.csv",
                organization="Ethereum Foundation",
                program="Ethereum Ecosystem Support Program",
                program_type="grant",
                website="https://esp.ethereum.foundation/about/how-we-support",
                apply_url="https://esp.ethereum.foundation/about/how-we-support",
                funding_range="$10K-$250K",
                description="Infrastructure, tooling, and research support.",
                sector_tags="ai,crypto,infra",
                status_note="롤링 / 2025-04-10",
                match_score=0.9,
            )
        ]

        raw = engine.to_raw_opportunities(results)

        assert len(raw) == 1
        assert raw[0]["status"] == "rolling"
        assert raw[0]["program_url"] == "https://esp.ethereum.foundation/about/how-we-support"
        assert raw[0]["apply_url"] == ""
        assert raw[0]["description"] == "Infrastructure, tooling, and research support."
        assert raw[0]["source_tier"] == 2

    def test_to_raw_opportunities_treats_applications_close_as_open(self):
        engine = ReferenceDataEngine()
        results = [
            ReferenceResult(
                source_file="curated_priority_programs.json",
                organization="Monad",
                program="Nitro Accelerator",
                program_type="vc_cohort",
                website="https://nitroacc.xyz/",
                apply_url="https://nitroacc.xyz/",
                description="12-week accelerator",
                sector_tags="web3,crypto",
                status_note="Applications close March 14, 2026",
                match_score=1.0,
            )
        ]

        raw = engine.to_raw_opportunities(results)

        assert raw[0]["status"] == "open"

    def test_to_raw_opportunities_keeps_program_page_without_promoting_it_to_apply_url(self):
        engine = ReferenceDataEngine()
        results = [
            ReferenceResult(
                source_file="grant_list_final.csv",
                organization="NEAR",
                program="NEAR Funding",
                program_type="grant",
                website="https://www.near.org/funding",
                apply_url="https://www.near.org/funding",
                description="Official funding hub",
                status_note="Applications open for ecosystem support",
                match_score=0.8,
            )
        ]

        raw = engine.to_raw_opportunities(results)

        assert len(raw) == 1
        assert raw[0]["apply_url"] == ""
        assert raw[0]["program_url"] == "https://www.near.org/funding"

    def test_to_raw_opportunities_skips_closed_reference_rows(self):
        engine = ReferenceDataEngine()
        results = [
            ReferenceResult(
                source_file="grant_list_final.csv",
                organization="Arbitrum Foundation",
                program="Trailblazer AI Grant Program",
                program_type="grant",
                website="https://docs.google.com/forms/d/e/closed-form/viewform",
                apply_url="https://docs.google.com/forms/d/e/closed-form/viewform",
                status_note="활성 (2024-11 시작) / 2025-04-10",
                match_score=0.8,
            )
        ]

        assert engine.to_raw_opportunities(results) == []

    def test_to_raw_opportunities_skips_generic_fund_homepage_rows(self):
        engine = ReferenceDataEngine()
        results = [
            ReferenceResult(
                source_file="vc_list_final.csv",
                organization="Blockchain Capital",
                program="Blockchain Capital Investment",
                program_type="vc_fund",
                website="https://blockchain.capital",
                apply_url="",
                description="Active Web3 VC",
                status_note="active=Yes",
                match_score=0.6,
            )
        ]

        assert engine.to_raw_opportunities(results) == []

    def test_bootstrap_sources_prioritize_anchor_terms(self):
        profile = get_default_profile("HOOT")
        engine = ReferenceDataEngine()
        engine._loaded = True
        engine._records = [
            {
                "_source_file": "curated_priority_programs.json",
                "organization": "Monad",
                "program": "Nitro Accelerator",
                "program_type": "vc_cohort",
                "website": "https://nitroacc.xyz/",
                "apply_url": "https://nitroacc.xyz/",
                "description": "VC + ecosystem accelerator",
                "sector_tags": "ai,crypto,infra",
                "industry_category": "Web3",
                "funding_range": "",
                "status_note": "Applications close March 14, 2026",
            },
            {
                "_source_file": "grant_list_final.csv",
                "organization": "Ethereum Foundation",
                "program": "Ethereum Ecosystem Support Program",
                "program_type": "grant",
                "website": "https://esp.ethereum.foundation/about/how-we-support",
                "apply_url": "https://esp.ethereum.foundation/about/how-we-support",
                "description": "Infra grants",
                "sector_tags": "ai,crypto,infra",
                "industry_category": "Web3",
                "funding_range": "",
                "status_note": "Rolling",
            },
        ]

        sources = engine.bootstrap_sources(
            profile,
            top_n=2,
            priority_terms=["Nitro Accelerator"],
        )

        assert sources[0] == "https://nitroacc.xyz/"

    def test_bootstrap_sources_can_pull_anchor_from_low_rank_reference_row(self):
        profile = get_default_profile("HOOT")
        engine = ReferenceDataEngine()
        engine._loaded = True
        engine._records = [
            {
                "_source_file": "grant_list_final.csv",
                "organization": "Ethereum Foundation",
                "program": "Ethereum Ecosystem Support Program",
                "program_type": "grant",
                "website": "https://esp.ethereum.foundation/about/how-we-support",
                "apply_url": "https://esp.ethereum.foundation/about/how-we-support",
                "description": "Infra grants",
                "sector_tags": "ai,crypto,infra",
                "industry_category": "Web3",
                "funding_range": "",
                "status_note": "Rolling",
            },
            {
                "_source_file": "vc_list_final.csv",
                "organization": "YZi Labs (Binance Labs)",
                "program": "YZi Labs (Binance Labs) Investment",
                "program_type": "vc_fund",
                "website": "https://labs.binance.com",
                "apply_url": "",
                "description": "Active Web3 VC; region=Asia; tier=1",
                "sector_tags": "",
                "industry_category": "Asia",
                "funding_range": "",
                "status_note": "",
            },
        ]

        sources = engine.bootstrap_sources(
            profile,
            top_n=2,
            priority_terms=["Binance Labs"],
        )

        assert "https://labs.binance.com" in sources

    def test_determine_source_tier_recognizes_priority_official_domains(self):
        assert determine_source_tier("https://nitroacc.xyz/") == 1
        assert determine_source_tier("https://chain.link/build") == 1

    def test_infer_status_from_source_does_not_promote_generic_funding_urls_to_open(self):
        assert _infer_status_from_source("https://www.near.org/funding") is None
        assert _infer_status_from_source("https://chain.link/build") is None
        assert _infer_status_from_source("https://foo.xyz/rolling") == "rolling"

    def test_merge_status_upgrades_unknown_but_not_actionable_status(self):
        assert _merge_status(OpportunityStatus.UNKNOWN, OpportunityStatus.OPEN) == OpportunityStatus.OPEN
        assert _merge_status(OpportunityStatus.ROLLING, OpportunityStatus.UNKNOWN) == OpportunityStatus.ROLLING

    def test_merge_status_closed_overrides_previous_open(self):
        assert _merge_status(OpportunityStatus.OPEN, OpportunityStatus.CLOSED) == OpportunityStatus.CLOSED

    def test_parse_status_note_marks_past_exact_date_closed(self):
        assert _parse_status_note("활성 / 2025-10-11") == "closed"

    def test_page_analysis_marks_generic_vc_homepage_unverified(self):
        analysis = _analyze_page_content(
            url="https://blockchain.capital/",
            title="Blockchain Capital",
            text="We invest in leading crypto companies. Portfolio. Team. Thesis.",
            expected_terms=["Blockchain Capital Investment"],
        )

        assert analysis["generic_homepage"] is True
        assert analysis["content_verified"] is False

    def test_page_analysis_rejects_unmatched_external_form(self):
        analysis = _analyze_page_content(
            url="https://taverncommunity.typeform.com/to/RW1j6BMu",
            title="Typeform",
            text="Please fill out the form below.",
            expected_terms=["Nitro Accelerator", "Monad"],
        )

        assert analysis["application_surface"] is True
        assert analysis["direct_apply_surface"] is True
        assert analysis["external_form_surface"] is True
        assert analysis["expected_hits"] == 0
        assert analysis["content_verified"] is False
        assert analysis["current_window_evidence"] is False

    def test_page_analysis_treats_apply_path_as_application_surface(self):
        analysis = _analyze_page_content(
            url="https://alliance.xyz/apply",
            title="Alliance",
            text="Alliance accelerator for founders.",
            expected_terms=["Alliance Accelerator", "Alliance"],
        )

        assert analysis["application_surface"] is True
        assert analysis["direct_apply_surface"] is True
        assert analysis["content_verified"] is True
        assert analysis["current_window_evidence"] is True

    def test_page_analysis_keeps_generic_funding_page_unknown_without_current_window_evidence(self):
        analysis = _analyze_page_content(
            url="https://www.near.org/funding",
            title="NEAR Funding",
            text="Official ecosystem funding hub for builders and teams.",
            expected_terms=["NEAR Funding", "NEAR"],
        )

        assert analysis["program_surface"] is True
        assert analysis["content_verified"] is True
        assert analysis["status"] == "unknown"
        assert analysis["current_window_evidence"] is False

    def test_page_analysis_can_treat_matched_direct_form_as_open_when_current(self):
        analysis = _analyze_page_content(
            url="https://nitroacc.xyz/apply",
            title="Nitro Accelerator Application",
            text="Nitro Accelerator applications open. Apply here for the Monad cohort.",
            expected_terms=["Nitro Accelerator", "Monad"],
        )

        assert analysis["direct_apply_surface"] is True
        assert analysis["content_verified"] is True
        assert analysis["status"] == "open"
        assert analysis["current_window_evidence"] is True
