"""
Tavily Search Engine.

search_depth="advanced"로 깊이 있는 검색. SDK 사용.
무료 한도: 1000회/월.
"""

from __future__ import annotations

import structlog

from src.core.config import Config
from src.search.engines.base import SearchEngine, SearchQuotaExceeded
from src.search.types import SearchResult

logger = structlog.get_logger()

QUOTA_MARKERS = (
    "plan's set usage limit",
    "rate limit",
    "rate_limit_exceeded",
    "quota",
)


class TavilyEngine(SearchEngine):
    """Tavily API 검색 엔진."""

    def __init__(self, config: Config) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "tavily"

    @property
    def is_available(self) -> bool:
        return bool(self._config.tavily_key)

    async def search(
        self, query: str, max_results: int = 10
    ) -> list[SearchResult]:
        if not self.is_available:
            return []

        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=self._config.tavily_key)
            response = client.search(
                query=query,
                max_results=max_results,
                search_depth="advanced",
            )

            results: list[SearchResult] = []
            for item in response.get("results", []):
                score = item.get("score", 0.0)
                results.append(
                    SearchResult(
                        url=item.get("url", ""),
                        title=item.get("title", ""),
                        snippet=item.get("content", "")[:500],
                        score=float(score) if score else 0.0,
                        engine=self.name,
                        published_date=item.get("published_date"),
                    )
                )

            logger.info(
                "search.tavily.done",
                query=query[:60],
                results=len(results),
            )
            return results

        except Exception as e:
            error_text = str(e).lower()
            logger.error("search.tavily.error", error=str(e))
            if any(marker in error_text for marker in QUOTA_MARKERS):
                raise SearchQuotaExceeded(str(e)) from e
            return []
