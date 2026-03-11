"""
Funding Intelligence Agent — SocialSearchEngine.

LunarCrush API + FxTwitter를 사용해서
트위터/소셜에서 펀딩 관련 발표를 검색하는 엔진.

LunarCrush API: 소셜 검색의 핵심 (Topic_Posts, Search)
FxTwitter: 특정 트윗 ID로 전체 텍스트 fetch (보조, 검색 불가)
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

from src.core.config import Config
from src.core.types import CompanyProfile
from src.search.profile_query_planner import generate_social_queries

logger = structlog.get_logger()


# ============================================================
# 필터 키워드
# ============================================================

FUNDING_KEYWORDS = frozenset({
    "grant", "grants", "funding", "accelerator", "cohort",
    "apply", "application", "builder program", "residency",
    "incubator", "incubation", "seed round", "demo day",
    "ecosystem fund", "builder incentive", "open call",
    "applications open", "accepting applications",
})

EXCLUDE_KEYWORDS = frozenset({
    "price prediction", "buy now", "airdrop", "token sale",
    "pump", "moon", "100x", "presale", "whitelist",
})

# ============================================================
# Social Result
# ============================================================


@dataclass
class SocialPost:
    """소셜 검색에서 발견된 포스트."""
    text: str
    url: str = ""
    author: str = ""
    engagement: int = 0
    extracted_urls: list[str] = field(default_factory=list)
    source: str = "lunarcrush"  # "lunarcrush" | "fxtwitter"


# ============================================================
# Social Search Engine
# ============================================================

LUNARCRUSH_BASE = "https://lunarcrush.com/api4/public"
FXTWITTER_BASE = "https://api.fxtwitter.com"


class SocialSearchEngine:
    """LunarCrush + FxTwitter 기반 소셜 검색 엔진.

    LunarCrush API 키가 없으면 graceful하게 빈 결과 반환.
    FxTwitter는 API 키 불필요.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._lunarcrush_key = getattr(config, "lunarcrush_key", "")
        self._log = logger.bind(component="social_engine")

    async def search(
        self, profile: CompanyProfile
    ) -> list[dict[str, Any]]:
        """프로필 기반 소셜 검색.

        Returns:
            raw_opportunity dict 리스트 (FundingPipeline 호환)
        """
        queries = generate_social_queries(profile)
        all_posts: list[SocialPost] = []

        # LunarCrush 검색 시도
        lc_posts = await self._search_lunarcrush(queries)
        all_posts.extend(lc_posts)

        self._log.info(
            "social.search_complete",
            lunarcrush_posts=len(lc_posts),
            total_posts=len(all_posts),
        )

        # 펀딩 관련 필터링
        funding_posts = _filter_funding_posts(all_posts)

        # SocialPost → raw_opportunity 변환
        return _posts_to_raw_opportunities(funding_posts)

    async def _search_lunarcrush(
        self, queries: list[str]
    ) -> list[SocialPost]:
        """LunarCrush API로 소셜 검색."""
        if not self._lunarcrush_key:
            self._log.info("social.lunarcrush_no_key")
            return []

        posts: list[SocialPost] = []
        headers = {
            "Authorization": f"Bearer {self._lunarcrush_key}",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            tasks = []
            for q in queries[:10]:
                tasks.append(self._lc_topic_search(client, headers, q))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, list):
                    posts.extend(result)
                elif isinstance(result, Exception):
                    self._log.warning(
                        "social.lunarcrush_error",
                        error=str(result),
                    )

        return posts

    async def _lc_topic_search(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        query: str,
    ) -> list[SocialPost]:
        """LunarCrush Topic 검색 단일 쿼리."""
        try:
            url = f"{LUNARCRUSH_BASE}/topic/{query}/posts/1w"
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return []

            data = resp.json()
            posts_data = data.get("data", [])

            results: list[SocialPost] = []
            for p in posts_data[:10]:
                text = p.get("text", "") or p.get("body", "")
                post_url = p.get("url", "") or p.get("post_url", "")
                author = p.get("creator_display_name", "") or p.get("screen_name", "")
                engagement = p.get("interactions", 0) or 0

                if not text:
                    continue

                results.append(SocialPost(
                    text=text,
                    url=post_url,
                    author=author,
                    engagement=engagement,
                    extracted_urls=_extract_urls(text),
                    source="lunarcrush",
                ))

            return results

        except Exception as e:
            self._log.debug("social.lc_query_error", query=query, error=str(e))
            return []

    async def fetch_tweet(self, screen_name: str, tweet_id: str) -> SocialPost | None:
        """FxTwitter로 특정 트윗 fetch.

        API 키 불필요. 레이트 리밋 관대.
        """
        url = f"{FXTWITTER_BASE}/{screen_name}/status/{tweet_id}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return None

                data = resp.json()
                tweet = data.get("tweet", {})
                text = tweet.get("text", "")
                tweet_url = tweet.get("url", "")

                return SocialPost(
                    text=text,
                    url=tweet_url,
                    author=screen_name,
                    engagement=tweet.get("likes", 0) + tweet.get("retweets", 0),
                    extracted_urls=_extract_urls(text),
                    source="fxtwitter",
                )

        except Exception as e:
            self._log.debug(
                "social.fxtwitter_error",
                tweet_id=tweet_id,
                error=str(e),
            )
            return None


# ============================================================
# 필터 + 변환 함수
# ============================================================

def _filter_funding_posts(posts: list[SocialPost]) -> list[SocialPost]:
    """펀딩 관련 포스트만 필터링."""
    filtered: list[SocialPost] = []

    for post in posts:
        text_lower = post.text.lower()

        # 제외 키워드 체크
        if any(kw in text_lower for kw in EXCLUDE_KEYWORDS):
            continue

        # 펀딩 키워드 포함 체크
        if any(kw in text_lower for kw in FUNDING_KEYWORDS):
            filtered.append(post)

    # engagement 순 정렬
    filtered.sort(key=lambda p: p.engagement, reverse=True)
    return filtered


def _posts_to_raw_opportunities(
    posts: list[SocialPost],
) -> list[dict[str, Any]]:
    """SocialPost → raw_opportunity dict 변환."""
    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for post in posts:
        # URL이 있는 포스트를 우선
        apply_url = ""
        for url in post.extracted_urls:
            if url not in seen_urls:
                apply_url = url
                seen_urls.add(url)
                break

        # 포스트 텍스트에서 프로그램 정보 추출 (간단 패턴 매칭)
        org_name, prog_name = _extract_names_from_text(post.text)

        if not org_name:
            org_name = post.author or "Unknown"

        if not prog_name:
            # 텍스트가 너무 짧으면 건너뛰기
            if len(post.text) < 30:
                continue
            prog_name = f"{org_name} Program"

        category = _guess_category_from_text(post.text)

        results.append({
            "organization": org_name,
            "program": prog_name,
            "category": category,
            "status": "unknown",
            "apply_url": apply_url,
            "source_url": post.url or apply_url,
            "source_type": "social",
            "description": post.text[:500],
            "confidence": 0.40,       # 소셜 소스 기본 신뢰도 (낮게)
            "source_tier": 5,         # SNS
            "fact_confidence": 0.40,
        })

    return results


def _extract_urls(text: str) -> list[str]:
    """텍스트에서 URL 추출."""
    url_pattern = re.compile(
        r'https?://[^\s<>"\')\]]+',
        re.IGNORECASE,
    )
    urls = url_pattern.findall(text)
    # 트위터/소셜 링크가 아닌 외부 URL만 반환
    external = [
        u for u in urls
        if not any(d in u for d in ["twitter.com", "t.co", "x.com"])
    ]
    return external or urls[:3]


def _extract_names_from_text(text: str) -> tuple[str, str]:
    """소셜 포스트 텍스트에서 조직명/프로그램명 추출.

    간단 패턴:
    - "@org_name" → org_name
    - "XYZ Accelerator" / "XYZ Grants" → program_name
    """
    org_name = ""
    prog_name = ""

    # @mention에서 org 추출
    mention_match = re.search(r'@(\w+)', text)
    if mention_match:
        org_name = mention_match.group(1)

    # "XYZ Accelerator/Grant/Program" 패턴
    prog_patterns = [
        r'(\w[\w\s]{1,30})\s+(?:Accelerator|accelerator)',
        r'(\w[\w\s]{1,30})\s+(?:Grants?|grants?)\s+(?:Program|program)',
        r'(\w[\w\s]{1,30})\s+(?:Builder\s+Program|builder\s+program)',
        r'(\w[\w\s]{1,30})\s+(?:Cohort|cohort)',
    ]
    for pattern in prog_patterns:
        match = re.search(pattern, text)
        if match:
            prog_name = match.group(0).strip()
            if not org_name:
                org_name = match.group(1).strip()
            break

    return org_name, prog_name


def _guess_category_from_text(text: str) -> str:
    """텍스트에서 카테고리 추측."""
    text_lower = text.lower()
    if "accelerator" in text_lower or "cohort" in text_lower:
        return "accelerator"
    if "grant" in text_lower:
        return "grant"
    if "builder program" in text_lower:
        return "builder_program"
    if "residency" in text_lower:
        return "residency"
    if "seed" in text_lower or "investment" in text_lower:
        return "vc_cohort"
    return "grant"
