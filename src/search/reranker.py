"""
Result Reranker — LLM 없는 결정적 점수 계산.

composite = domain_authority(0.4) + engine_agreement(0.3) + relevance(0.2) + freshness(0.1)

verification.py의 TIER_1~5 도메인 리스트를 재사용한다.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse

import structlog

from src.search.types import RankedResult, SearchResult

logger = structlog.get_logger()

# ============================================================
# 도메인 권위 점수 (verification.py의 TIER 도메인 재사용)
# ============================================================

AUTHORITY_TIER_1 = {
    "ethereum.org", "solana.org", "near.org", "polygon.technology",
    "arbitrum.foundation", "optimism.io", "a16zcrypto.com",
    "paradigm.xyz", "polychain.capital", "sequoia.com",
    "alliancedao.com", "ycombinator.com", "binance.com",
    "esp.ethereum.foundation", "solana.com", "foundation.app",
    "aave.com", "uniswap.org", "compound.finance",
}

AUTHORITY_TIER_2 = {
    "mirror.xyz", "medium.com", "blog.chain.link",
    "docs.alchemy.com", "thegraph.com", "gitcoin.co",
    "questbook.app", "superteam.fun",
}

AUTHORITY_TIER_4 = {
    "cryptorank.io", "rootdata.com", "coinmarketcap.com",
    "coingecko.com", "defillama.com",
}

AUTHORITY_TIER_5 = {
    "twitter.com", "x.com", "t.me", "discord.com",
    "reddit.com", "farcaster.xyz",
}

# 차단 도메인 (discovery.py BLOCKED_DOMAINS 확장)
BLOCKED_DOMAINS = {
    "wikipedia.org", "namu.wiki", "namu.com",
    "youtube.com", "youtu.be",
    "reddit.com", "twitter.com", "x.com",
    "facebook.com", "instagram.com",
    "tiktok.com", "linkedin.com",
    "blog.naver.com", "tistory.com",
    "chatgpt.com", "openai.com",
}

# Tier → 점수 매핑
DOMAIN_SCORE = {1: 1.0, 2: 0.8, 3: 0.5, 4: 0.3, 5: 0.1}


def _get_domain(url: str) -> str:
    """URL → 도메인 (www. 제거)."""
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _domain_tier(domain: str) -> int:
    """도메인 → 권위 tier (1-5)."""
    if any(d in domain for d in AUTHORITY_TIER_1):
        return 1
    if any(d in domain for d in AUTHORITY_TIER_2):
        return 2
    if any(d in domain for d in AUTHORITY_TIER_4):
        return 4
    if any(d in domain for d in AUTHORITY_TIER_5):
        return 5
    return 3  # 기본: 블로그 수준


def _is_blocked(domain: str) -> bool:
    """차단 도메인 여부."""
    return any(b in domain for b in BLOCKED_DOMAINS)


def _freshness_score(published_date: str | None) -> float:
    """발행일 기반 freshness 점수 (0-1)."""
    if not published_date:
        return 0.5  # 날짜 없으면 중간값

    try:
        # ISO date 파싱 시도 (다양한 형식 허용)
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                dt = datetime.strptime(published_date[:19], fmt)
                break
            except ValueError:
                continue
        else:
            return 0.5

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        days_old = (now - dt).days

        if days_old <= 30:
            return 1.0
        elif days_old <= 90:
            return 0.8
        elif days_old <= 180:
            return 0.6
        elif days_old <= 365:
            return 0.4
        else:
            return 0.2

    except Exception:
        return 0.5


def _normalize_url(url: str) -> str:
    """URL 정규화 (dedup 용)."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")
    path = parsed.path.rstrip("/")
    return f"https://{domain}{path}"


class ResultReranker:
    """검색 결과 리랭킹 + dedup.

    공식: composite = authority×0.4 + agreement×0.3 + relevance×0.2 + freshness×0.1
    """

    def rerank(
        self,
        results: list[SearchResult],
        top_k: int = 15,
    ) -> list[RankedResult]:
        """SearchResult 리스트 → RankedResult 리스트 (정렬됨).

        1. 차단 도메인 필터
        2. URL 정규화 + dedup (같은 URL, 다른 엔진 → 합산)
        3. 4-factor 점수 계산
        4. 상위 top_k 선택
        """
        if not results:
            return []

        # Step 1: 차단 도메인 필터
        filtered = [
            r for r in results
            if r.url and not _is_blocked(_get_domain(r.url))
        ]

        # Step 2: URL 정규화 + 그룹화
        url_groups: dict[str, list[SearchResult]] = defaultdict(list)
        for r in filtered:
            key = _normalize_url(r.url)
            url_groups[key].append(r)

        # Step 3: 그룹별 점수 계산
        ranked: list[RankedResult] = []
        max_engines = max(
            len({r.engine for r in group}) for group in url_groups.values()
        ) if url_groups else 1

        for norm_url, group in url_groups.items():
            original_url = group[0].url  # 원본 URL 유지
            domain = _get_domain(original_url)
            tier = _domain_tier(domain)
            engines = list({r.engine for r in group})

            # domain_authority (0-1)
            authority = DOMAIN_SCORE.get(tier, 0.5)

            # engine_agreement (0-1)
            agreement = len(engines) / max(max_engines, 1)

            # relevance: 각 엔진 점수의 평균 (0-1)
            scores = [r.score for r in group if r.score > 0]
            relevance = sum(scores) / len(scores) if scores else 0.5

            # freshness (0-1)
            dates = [r.published_date for r in group if r.published_date]
            freshness = (
                max(_freshness_score(d) for d in dates) if dates
                else 0.5
            )

            # 종합 점수
            composite = (
                authority * 0.4
                + agreement * 0.3
                + relevance * 0.2
                + freshness * 0.1
            )

            # title, snippet은 첫 결과에서 가져옴
            ranked.append(
                RankedResult(
                    url=original_url,
                    title=group[0].title,
                    snippet=group[0].snippet,
                    composite_score=round(composite, 4),
                    domain_authority=authority,
                    engine_agreement=len(engines),
                    relevance=round(relevance, 4),
                    freshness=freshness,
                    engines=engines,
                )
            )

        # Step 4: 점수 순 정렬 + top_k
        ranked.sort(key=lambda r: r.composite_score, reverse=True)

        logger.info(
            "search.reranker.done",
            input_count=len(results),
            filtered=len(filtered),
            unique_urls=len(url_groups),
            output_count=min(len(ranked), top_k),
        )

        return ranked[:top_k]
