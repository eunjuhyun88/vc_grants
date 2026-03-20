"""
Multi-Engine Search — 3엔진 병렬 fan-out.

사용 가능한 엔진만 골라서 asyncio.gather로 병렬 실행.
엔진 키가 0개면 빈 리스트 반환 (DDG 폴백은 DiscoveryAgent 레벨에서 처리).
"""

from __future__ import annotations

import asyncio
import math
import time
from typing import Sequence

import structlog

from src.core.config import Config
from src.search.engines.base import SearchEngine, SearchEngineError, SearchQuotaExceeded
from src.search.engines.brave_engine import BraveEngine
from src.search.engines.serper_engine import SerperEngine
from src.search.engines.tavily_engine import TavilyEngine
from src.search.types import SearchResult

logger = structlog.get_logger()


class MultiEngineSearch:
    """3엔진 병렬 검색 실행기."""

    def __init__(self, config: Config) -> None:
        self._engines: list[SearchEngine] = [
            TavilyEngine(config),
            SerperEngine(config),
            BraveEngine(config),
        ]
        self._engine_cooldowns: dict[str, float] = {}

    @property
    def available_engines(self) -> list[SearchEngine]:
        now = time.monotonic()
        return [
            e
            for e in self._engines
            if e.is_available and self._engine_cooldowns.get(e.name, 0.0) <= now
        ]

    @property
    def available_count(self) -> int:
        return len(self.available_engines)

    async def search_all(
        self,
        queries: Sequence[str],
        max_results_per_query: int = 10,
    ) -> list[SearchResult]:
        """여러 쿼리를 사용 가능한 모든 엔진에 병렬 전송.

        Args:
            queries: 검색할 쿼리 리스트
            max_results_per_query: 엔진별 쿼리당 최대 결과 수

        Returns:
            모든 엔진 × 모든 쿼리의 합산 결과 (dedup 전)
        """
        engines = self.available_engines
        if not engines:
            logger.warning("search.multi_engine.no_engines_available")
            return []

        # 엔진 간에는 병렬, 엔진 내부 쿼리는 순차 실행해서
        # quota 엔진을 한 라운드 안에서 계속 두드리지 않게 한다.
        tasks = [
            self._search_engine_queries(engine, queries, max_results_per_query)
            for engine in engines
        ]
        results_lists = await asyncio.gather(*tasks)

        # 평탄화
        all_results: list[SearchResult] = []
        for results in results_lists:
            all_results.extend(results)

        logger.info(
            "search.multi_engine.done",
            engines=len(engines),
            queries=len(queries),
            total_results=len(all_results),
        )
        return all_results

    async def _search_engine_queries(
        self,
        engine: SearchEngine,
        queries: Sequence[str],
        max_results: int,
    ) -> list[SearchResult]:
        all_results: list[SearchResult] = []
        for query in queries:
            results = await self._safe_search(engine, query, max_results)
            all_results.extend(results)
            if self._engine_cooldowns.get(engine.name) == math.inf:
                break
        return all_results

    async def _safe_search(
        self,
        engine: SearchEngine,
        query: str,
        max_results: int,
    ) -> list[SearchResult]:
        """개별 엔진 검색 (에러 시 빈 리스트)."""
        try:
            return await engine.search(query, max_results)
        except SearchQuotaExceeded as e:
            # Quota가 난 엔진은 현재 orchestration 세션 동안 바로 식힌다.
            self._engine_cooldowns[engine.name] = math.inf
            logger.warning(
                "search.multi_engine.engine_cooldown",
                engine=engine.name,
                query=query[:60],
                reason="quota_exceeded",
                error=str(e),
            )
            return []
        except SearchEngineError as e:
            logger.warning(
                "search.multi_engine.engine_skip",
                engine=engine.name,
                query=query[:60],
                error=str(e),
            )
            return []
        except Exception as e:
            logger.error(
                "search.multi_engine.engine_error",
                engine=engine.name,
                query=query[:60],
                error=str(e),
            )
            return []
