"""
Serper (Google) Search Engine.

POST https://google.serper.dev/search, X-API-KEY 헤더.
무료 한도: 2500회/월.
"""

from __future__ import annotations

import httpx
import structlog

from src.core.config import Config
from src.search.engines.base import SearchEngine, SearchQuotaExceeded
from src.search.types import SearchResult

logger = structlog.get_logger()

SERPER_API_URL = "https://google.serper.dev/search"
QUOTA_MARKERS = (
    "rate limit",
    "quota",
    "usage limit",
    "too many requests",
)


class SerperEngine(SearchEngine):
    """Serper (Google Search) 엔진."""

    def __init__(self, config: Config) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "serper"

    @property
    def is_available(self) -> bool:
        return bool(self._config.serper_key)

    async def search(
        self, query: str, max_results: int = 10
    ) -> list[SearchResult]:
        if not self.is_available:
            return []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    SERPER_API_URL,
                    headers={
                        "X-API-KEY": self._config.serper_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "q": query,
                        "num": max_results,
                        "gl": "us",
                        "hl": "en",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            results: list[SearchResult] = []
            organic = data.get("organic", [])

            for i, item in enumerate(organic[:max_results]):
                # Serper는 position 기반 점수 (1위=1.0, 10위=0.1)
                position_score = max(0.0, 1.0 - (i * 0.1))
                results.append(
                    SearchResult(
                        url=item.get("link", ""),
                        title=item.get("title", ""),
                        snippet=item.get("snippet", "")[:500],
                        score=position_score,
                        engine=self.name,
                        published_date=item.get("date"),
                    )
                )

            logger.info(
                "search.serper.done",
                query=query[:60],
                results=len(results),
            )
            return results

        except Exception as e:
            logger.error("search.serper.error", error=str(e))
            if any(marker in str(e).lower() for marker in QUOTA_MARKERS):
                raise SearchQuotaExceeded(str(e)) from e
            return []
