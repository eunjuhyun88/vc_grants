"""
Brave Search Engine.

GET https://api.search.brave.com/res/v1/web/search, X-Subscription-Token 헤더.
무료 한도: 2000회/월.
"""

from __future__ import annotations

import httpx
import structlog

from src.core.config import Config
from src.search.engines.base import SearchEngine, SearchQuotaExceeded
from src.search.types import SearchResult

logger = structlog.get_logger()

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
QUOTA_MARKERS = (
    "rate limit",
    "quota",
    "usage limit",
    "too many requests",
)


class BraveEngine(SearchEngine):
    """Brave Search 엔진."""

    def __init__(self, config: Config) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "brave"

    @property
    def is_available(self) -> bool:
        return bool(self._config.brave_key)

    async def search(
        self, query: str, max_results: int = 10
    ) -> list[SearchResult]:
        if not self.is_available:
            return []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    BRAVE_API_URL,
                    headers={
                        "X-Subscription-Token": self._config.brave_key,
                        "Accept": "application/json",
                    },
                    params={
                        "q": query,
                        "count": max_results,
                        "search_lang": "en",
                        "country": "us",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            results: list[SearchResult] = []
            web_results = data.get("web", {}).get("results", [])

            for i, item in enumerate(web_results[:max_results]):
                position_score = max(0.0, 1.0 - (i * 0.1))
                results.append(
                    SearchResult(
                        url=item.get("url", ""),
                        title=item.get("title", ""),
                        snippet=item.get("description", "")[:500],
                        score=position_score,
                        engine=self.name,
                        published_date=item.get("page_age"),
                    )
                )

            logger.info(
                "search.brave.done",
                query=query[:60],
                results=len(results),
            )
            return results

        except Exception as e:
            logger.error("search.brave.error", error=str(e))
            if any(marker in str(e).lower() for marker in QUOTA_MARKERS):
                raise SearchQuotaExceeded(str(e)) from e
            return []
