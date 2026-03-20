"""
SearchOrchestrator 통합 테스트.

모든 외부 API 호출은 mock.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.config import Config
from src.search.extractor import OpportunityExtractor
from src.search.orchestrator import SearchOrchestrator
from src.search.types import (
    ExtractedOpportunity,
    FetchedPage,
    RankedResult,
    SearchResult,
)


@pytest.fixture
def config():
    return Config(
        tavily_key="test-tavily",
        serper_key="test-serper",
        brave_key="test-brave",
        groq_key="test-groq",
        jina_key="test-jina",
    )


@pytest.fixture
def orchestrator(config):
    return SearchOrchestrator(config)


class TestSearchOrchestratorDirect:
    """sources 직접 제공 시 동작 테스트."""

    @pytest.mark.asyncio
    async def test_direct_fetch_empty_pages(self, orchestrator):
        """모든 페이지 fetch 실패 시 빈 결과."""
        with patch.object(
            orchestrator._fetcher, "fetch_many",
            new_callable=AsyncMock,
            return_value=[],
        ):
            opps, urls = await orchestrator.search(
                query="test",
                sources=["https://example.com"],
            )
            assert opps == []
            assert urls == []

    @pytest.mark.asyncio
    async def test_direct_fetch_with_pages(self, orchestrator):
        """페이지 fetch 성공 → 기회 추출."""
        mock_pages = [
            FetchedPage(
                url="https://ethereum.org/grants",
                content="Some content about grants",
                content_length=100,
                fetch_method="jina",
                success=True,
            )
        ]
        mock_opps = [
            ExtractedOpportunity(
                organization="Ethereum Foundation",
                program="ESP Grants",
                category="grant",
                apply_url="https://esp.ethereum.foundation/apply",
                source_url="https://ethereum.org/grants",
            )
        ]

        with patch.object(
            orchestrator._fetcher, "fetch_many",
            new_callable=AsyncMock,
            return_value=mock_pages,
        ), patch.object(
            orchestrator._extractor, "extract_per_page",
            new_callable=AsyncMock,
            return_value=mock_opps,
        ):
            opps, urls = await orchestrator.search(
                query="ethereum grants",
                sources=["https://ethereum.org/grants"],
            )
            assert len(opps) == 1
            assert opps[0]["organization"] == "Ethereum Foundation"
            assert "https://ethereum.org/grants" in urls


class TestSearchOrchestratorNoEngines:
    """엔진 키가 없는 경우."""

    @pytest.mark.asyncio
    async def test_no_engines_returns_empty(self):
        config = Config(
            tavily_key="",
            serper_key="",
            brave_key="",
            groq_key="",
        )
        orch = SearchOrchestrator(config)
        opps, urls = await orch.search(query="test")
        assert opps == []
        assert urls == []


class TestSearchOrchestratorAgenticLoop:
    """Agentic RAG 루프 테스트."""

    @pytest.mark.asyncio
    async def test_single_round_sufficient(self, orchestrator):
        """1라운드에서 충분한 결과가 나오면 종료."""
        # QueryPlanner mock
        mock_queries = ["query1", "query2"]
        with patch.object(
            orchestrator._planner, "plan",
            new_callable=AsyncMock,
            return_value=mock_queries,
        ), patch.object(
            orchestrator._multi_engine, "search_all",
            new_callable=AsyncMock,
            return_value=[
                SearchResult(url=f"https://site{i}.com/grant", engine="tavily", score=0.8)
                for i in range(10)
            ],
        ), patch.object(
            orchestrator._fetcher, "fetch_many",
            new_callable=AsyncMock,
            return_value=[
                FetchedPage(url=f"https://site{i}.com/grant", content=f"Content {i}", success=True)
                for i in range(5)
            ],
        ), patch.object(
            orchestrator._extractor, "extract_per_page",
            new_callable=AsyncMock,
            return_value=[
                ExtractedOpportunity(
                    organization=f"Org{i}",
                    program=f"Program{i}",
                    apply_url=f"https://apply{i}.com",
                    category="grant",
                )
                for i in range(8)  # 8개 → 충분
            ],
        ), patch.object(
            orchestrator._extractor, "synthesize",
            new_callable=AsyncMock,
            return_value=[
                ExtractedOpportunity(
                    organization=f"Org{i}",
                    program=f"Program{i}",
                    apply_url=f"https://apply{i}.com",
                    category="grant",
                )
                for i in range(8)
            ],
        ):
            opps, urls = await orchestrator.search(query="AI grants", category="grant")
            assert len(opps) == 8

    @pytest.mark.asyncio
    async def test_to_dicts_conversion(self, orchestrator):
        """ExtractedOpportunity → dict 변환 확인."""
        opps = [
            ExtractedOpportunity(
                organization="Test Org",
                program="Test Program",
                category="grant",
                status="open",
                apply_url="https://apply.com",
                confidence=0.85,
            )
        ]
        result = orchestrator._to_dicts(opps)
        assert len(result) == 1
        assert result[0]["organization"] == "Test Org"
        assert result[0]["confidence"] == 0.85


class TestExtractorFallback:
    @pytest.mark.asyncio
    async def test_heuristic_fallback_extracts_when_llm_unavailable(self):
        extractor = OpportunityExtractor(
            Config(groq_key="", anthropic_key="", jina_key="")
        )
        pages = [
            FetchedPage(
                url="https://nitroacc.xyz/",
                content=(
                    "Nitro Accelerator\n"
                    "Applications close March 14, 2026.\n"
                    "Up to $500k per team for founders building breakout startups.\n"
                    "Apply now: https://nitroacc.xyz/\n"
                ),
                content_length=180,
                fetch_method="httpx",
                success=True,
            )
        ]

        opps = await extractor.extract_per_page(pages)

        assert len(opps) == 1
        assert opps[0].organization == "Monad"
        assert opps[0].program == "Nitro Accelerator"
        assert opps[0].status == "open"
        assert opps[0].deadline == "2026-03-14"
        assert opps[0].apply_url == "https://nitroacc.xyz/"

    @pytest.mark.asyncio
    async def test_heuristic_fallback_canonicalizes_known_source_url(self):
        extractor = OpportunityExtractor(
            Config(groq_key="", anthropic_key="", jina_key="")
        )
        pages = [
            FetchedPage(
                url="https://nitroacc.xyz/",
                content=(
                    "Accelerator for founders building breakout startups.\n"
                    "Applications close March 14, 2026.\n"
                    "Apply now: https://nitroacc.xyz/\n"
                ),
                content_length=140,
                fetch_method="httpx",
                success=True,
            )
        ]

        opps = await extractor.extract_per_page(pages)

        assert len(opps) == 1
        assert opps[0].organization == "Monad"
        assert opps[0].program == "Nitro Accelerator"

    def test_parse_opportunities_json_canonicalizes_known_program_from_source(self):
        extractor = OpportunityExtractor(
            Config(groq_key="", anthropic_key="", jina_key="")
        )
        raw = """
        [
          {
            "organization": "Nitroacc",
            "program": "accelerator.",
            "category": "accelerator",
            "status": "open",
            "deadline": "2026-03-14",
            "budget": "$500k",
            "apply_url": "https://nitroacc.xyz/",
            "description": "12-week accelerator for founders"
          }
        ]
        """

        opps = extractor._parse_opportunities_json(raw, "https://nitroacc.xyz/")

        assert len(opps) == 1
        assert opps[0].organization == "Monad"
        assert opps[0].program == "Nitro Accelerator"
