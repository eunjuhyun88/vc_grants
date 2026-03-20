"""
Reranker 단위 테스트.

순수 로직 테스트 — 외부 의존성 없음.
"""

from __future__ import annotations

import pytest

from src.search.reranker import (
    ResultReranker,
    _domain_tier,
    _freshness_score,
    _get_domain,
    _is_blocked,
    _normalize_url,
)
from src.search.types import SearchResult


# ============================================================
# Helper function tests
# ============================================================

class TestHelperFunctions:
    def test_get_domain(self):
        assert _get_domain("https://www.ethereum.org/grants") == "ethereum.org"
        assert _get_domain("https://solana.org/ecosystem") == "solana.org"
        assert _get_domain("") == ""

    def test_domain_tier(self):
        assert _domain_tier("ethereum.org") == 1
        assert _domain_tier("solana.org") == 1
        assert _domain_tier("mirror.xyz") == 2
        assert _domain_tier("cryptorank.io") == 4
        assert _domain_tier("twitter.com") == 5
        assert _domain_tier("someunknown.com") == 3  # 기본

    def test_is_blocked(self):
        assert _is_blocked("wikipedia.org") is True
        assert _is_blocked("youtube.com") is True
        assert _is_blocked("reddit.com") is True
        assert _is_blocked("ethereum.org") is False
        assert _is_blocked("solana.org") is False

    def test_normalize_url(self):
        assert _normalize_url("https://ethereum.org/grants/") == "https://ethereum.org/grants"
        assert _normalize_url("http://www.solana.org/") == "https://solana.org"

    def test_freshness_score_recent(self):
        score = _freshness_score("2026-03-01")
        assert score >= 0.8  # 최근 30일 이내

    def test_freshness_score_old(self):
        score = _freshness_score("2020-01-01")
        assert score <= 0.3

    def test_freshness_score_none(self):
        assert _freshness_score(None) == 0.5

    def test_freshness_score_invalid(self):
        assert _freshness_score("not-a-date") == 0.5


# ============================================================
# Reranker tests
# ============================================================

class TestResultReranker:
    def test_empty_input(self):
        reranker = ResultReranker()
        assert reranker.rerank([]) == []

    def test_blocked_domains_filtered(self):
        reranker = ResultReranker()
        results = [
            SearchResult(url="https://youtube.com/watch?v=123", engine="serper"),
            SearchResult(url="https://ethereum.org/grants", engine="serper"),
            SearchResult(url="https://wikipedia.org/wiki/grants", engine="serper"),
        ]
        ranked = reranker.rerank(results)
        urls = [r.url for r in ranked]
        assert "https://youtube.com/watch?v=123" not in urls
        assert "https://wikipedia.org/wiki/grants" not in urls
        assert len(ranked) == 1

    def test_dedup_same_url(self):
        """같은 URL이 여러 엔진에서 나오면 하나로 합침."""
        reranker = ResultReranker()
        results = [
            SearchResult(url="https://ethereum.org/grants", engine="tavily", score=0.9),
            SearchResult(url="https://ethereum.org/grants", engine="serper", score=0.8),
            SearchResult(url="https://ethereum.org/grants", engine="brave", score=0.7),
        ]
        ranked = reranker.rerank(results)
        assert len(ranked) == 1
        assert ranked[0].engine_agreement == 3

    def test_authority_ranking(self):
        """Tier 1 도메인이 Tier 3보다 높은 점수."""
        reranker = ResultReranker()
        results = [
            SearchResult(url="https://randomsite.com/grants", engine="serper", score=0.9),
            SearchResult(url="https://ethereum.org/grants", engine="serper", score=0.8),
        ]
        ranked = reranker.rerank(results)
        # ethereum.org (tier 1)이 randomsite.com (tier 3)보다 높아야 함
        assert ranked[0].url == "https://ethereum.org/grants"

    def test_top_k_limit(self):
        """top_k 제한 적용."""
        reranker = ResultReranker()
        results = [
            SearchResult(url=f"https://site{i}.com/grants", engine="serper", score=0.5)
            for i in range(20)
        ]
        ranked = reranker.rerank(results, top_k=5)
        assert len(ranked) == 5

    def test_engine_agreement_boost(self):
        """여러 엔진에서 나온 결과가 더 높은 점수."""
        reranker = ResultReranker()
        results = [
            # URL A: 3 엔진
            SearchResult(url="https://siteA.com/grants", engine="tavily", score=0.5),
            SearchResult(url="https://siteA.com/grants", engine="serper", score=0.5),
            SearchResult(url="https://siteA.com/grants", engine="brave", score=0.5),
            # URL B: 1 엔진, 높은 점수
            SearchResult(url="https://siteB.com/grants", engine="tavily", score=0.9),
        ]
        ranked = reranker.rerank(results)
        # siteA는 3 엔진 합의 → agreement 점수 높음
        site_a = next(r for r in ranked if "siteA" in r.url)
        site_b = next(r for r in ranked if "siteB" in r.url)
        assert site_a.engine_agreement == 3
        assert site_b.engine_agreement == 1

    def test_composite_score_range(self):
        """composite_score는 0-1 범위."""
        reranker = ResultReranker()
        results = [
            SearchResult(url="https://ethereum.org/grants", engine="tavily", score=1.0),
        ]
        ranked = reranker.rerank(results)
        assert 0.0 <= ranked[0].composite_score <= 1.0
