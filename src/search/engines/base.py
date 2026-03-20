"""
Search Engine ABC.

모든 검색 엔진은 이 인터페이스를 구현한다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.search.types import SearchResult


class SearchEngineError(Exception):
    """검색 엔진 레벨 예외 베이스."""


class SearchQuotaExceeded(SearchEngineError):
    """엔진 quota/rate limit로 인해 잠시 사용 불가한 상태."""


class SearchEngine(ABC):
    """검색 엔진 추상 베이스 클래스."""

    @property
    @abstractmethod
    def name(self) -> str:
        """엔진 이름 (예: "tavily", "serper", "brave")."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """API 키 존재 여부. False이면 skip."""
        ...

    @abstractmethod
    async def search(
        self, query: str, max_results: int = 10
    ) -> list[SearchResult]:
        """쿼리 실행 → SearchResult 리스트.

        quota/temporarily blocked 상태는 `SearchEngineError` 계열 예외를
        올려서 상위 fan-out이 엔진을 식히도록 한다.
        """
        ...
