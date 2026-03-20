"""
SearchOrchestrator — Agentic RAG 루프 컨트롤러.

진입점. DiscoveryAgent가 호출. 전체 검색 루프를 관리한다.

흐름:
  sources 제공 → 바로 fetch + extract + synthesize
  sources 없음 → Round 1~3 반복 (plan → search → rerank → fetch → extract → evaluate)
"""

from __future__ import annotations

import structlog

from src.core.config import Config
from src.search.evaluator import SufficiencyEvaluator
from src.search.extractor import OpportunityExtractor
from src.search.fetcher import SmartFetcher
from src.search.multi_engine import MultiEngineSearch
from src.search.query_planner import QueryPlanner
from src.search.reranker import ResultReranker
from src.search.types import (
    ExtractedOpportunity,
    SearchContext,
    SearchRound,
)

logger = structlog.get_logger()


class SearchOrchestrator:
    """Agentic RAG 검색 오케스트레이터.

    DiscoveryAgent → SearchOrchestrator.search() → (opportunities, source_urls)
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._planner = QueryPlanner(config)
        self._multi_engine = MultiEngineSearch(config)
        self._reranker = ResultReranker()
        self._fetcher = SmartFetcher(config)
        self._extractor = OpportunityExtractor(config)
        self._evaluator = SufficiencyEvaluator()

    @property
    def has_available_engines(self) -> bool:
        return self._multi_engine.available_count > 0

    async def search(
        self,
        query: str,
        category: str | None = None,
        sources: list[str] | None = None,
    ) -> tuple[list[dict], list[str]]:
        """메인 검색 진입점.

        Args:
            query: 사용자 검색 쿼리
            category: 프로그램 카테고리 (grant, accelerator 등)
            sources: 직접 지정된 URL 리스트 (있으면 검색 건너뜀)

        Returns:
            (raw_opportunities, source_urls) — DiscoveryOutput 호환 형식
        """
        # 사용 가능한 엔진 확인
        engine_count = self._multi_engine.available_count
        logger.info(
            "search.orchestrator.start",
            query=query[:60],
            category=category,
            engines=engine_count,
            sources=len(sources) if sources else 0,
        )

        # sources가 직접 제공된 경우 → 바로 fetch + extract
        if sources:
            return await self._direct_fetch(sources)

        # 엔진이 0개면 빈 결과 반환 (DDG 폴백은 DiscoveryAgent에서)
        if engine_count == 0:
            logger.warning("search.orchestrator.no_engines")
            return [], []

        # Agentic RAG 루프
        ctx = SearchContext(
            original_query=query,
            category=category,
            max_rounds=self._config.search_max_rounds,
        )

        while not ctx.is_sufficient and ctx.current_round < ctx.max_rounds:
            await self._execute_round(ctx)
            self._evaluator.evaluate(ctx)

        # 최종 종합 (Strong LLM)
        if ctx.all_opportunities:
            synthesized = await self._extractor.synthesize(
                ctx.all_opportunities
            )
            if synthesized:
                ctx.all_opportunities = synthesized

        # dict 변환 + source_urls 수집
        raw_opps = self._to_dicts(ctx.all_opportunities)
        source_urls = self._collect_source_urls(ctx)

        logger.info(
            "search.orchestrator.complete",
            rounds=ctx.current_round,
            total_opportunities=len(raw_opps),
            source_urls=len(source_urls),
        )

        return raw_opps, source_urls

    # ============================================================
    # Internal: Direct fetch (sources 제공 시)
    # ============================================================

    async def _direct_fetch(
        self, sources: list[str]
    ) -> tuple[list[dict], list[str]]:
        """URL 리스트가 직접 주어진 경우: fetch → extract → synthesize."""
        pages = await self._fetcher.fetch_many(sources)
        if not pages:
            return [], []

        opportunities = await self._extractor.extract_per_page(pages)
        if len(opportunities) > 3:
            synthesized = await self._extractor.synthesize(opportunities)
            if synthesized:
                opportunities = synthesized

        raw_opps = self._to_dicts(opportunities)
        source_urls = [p.url for p in pages if p.success]

        return raw_opps, source_urls

    # ============================================================
    # Internal: Agentic RAG Round
    # ============================================================

    async def _execute_round(self, ctx: SearchContext) -> None:
        """단일 검색 라운드 실행."""
        round_num = ctx.current_round + 1
        logger.info("search.orchestrator.round_start", round=round_num)

        # Step 1: 쿼리 계획
        if round_num == 1:
            queries = await self._planner.plan(
                ctx.original_query, ctx.category
            )
        else:
            queries = await self._planner.refine(
                ctx.original_query,
                ctx.all_opportunities,
                ctx.gap_reasons,
            )

        if not queries:
            logger.warning("search.orchestrator.no_queries", round=round_num)
            round_record = SearchRound(round_number=round_num)
            ctx.rounds.append(round_record)
            return

        # Step 2: 다중 엔진 검색
        search_results = await self._multi_engine.search_all(queries)

        # Step 3: 리랭킹
        ranked = self._reranker.rerank(search_results, top_k=15)

        # 이미 본 URL 제외
        new_ranked = [
            r for r in ranked if r.url not in ctx.all_urls_seen
        ]

        # URL 기록
        for r in new_ranked:
            ctx.all_urls_seen.add(r.url)

        # Step 4: 페이지 수집
        urls_to_fetch = [r.url for r in new_ranked]
        pages = await self._fetcher.fetch_many(urls_to_fetch)
        ctx.fetched_pages.extend(pages)

        # Step 5: 기회 추출
        new_opportunities = await self._extractor.extract_per_page(pages)
        ctx.all_opportunities.extend(new_opportunities)

        # 라운드 기록
        round_record = SearchRound(
            round_number=round_num,
            queries=queries,
            urls_found=len(ranked),
            urls_fetched=len(pages),
            opportunities_extracted=len(new_opportunities),
        )
        ctx.rounds.append(round_record)

        logger.info(
            "search.orchestrator.round_complete",
            round=round_num,
            new_urls=len(new_ranked),
            fetched=len(pages),
            extracted=len(new_opportunities),
            total_cumulative=len(ctx.all_opportunities),
        )

    # ============================================================
    # Utils
    # ============================================================

    @staticmethod
    def _to_dicts(
        opportunities: list[ExtractedOpportunity],
    ) -> list[dict]:
        """ExtractedOpportunity → dict 리스트 (DiscoveryOutput 호환)."""
        results: list[dict] = []
        for opp in opportunities:
            d = {
                "organization": opp.organization,
                "program": opp.program,
                "category": opp.category,
                "status": opp.status,
                "deadline": opp.deadline,
                "budget": opp.budget,
                "apply_url": opp.apply_url,
                "description": opp.description,
                "focus_areas": opp.focus_areas,
                "source_url": opp.source_url,
            }
            if opp.confidence:
                d["confidence"] = opp.confidence
            results.append(d)
        return results

    @staticmethod
    def _collect_source_urls(ctx: SearchContext) -> list[str]:
        """성공적으로 페치된 모든 소스 URL."""
        return list({
            p.url for p in ctx.fetched_pages if p.success
        })
