"""
Funding Intelligence Agent — SocialSearchEngine.

LunarCrush API + FxTwitter를 사용해서
트위터/소셜에서 펀딩 관련 발표를 검색하는 엔진.

LunarCrush API: 소셜 검색의 핵심 (Topic_Posts, Search)
FxTwitter: 특정 트윗 ID로 전체 텍스트 fetch (보조, 검색 불가)
"""

from __future__ import annotations

import asyncio
import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

from src.core.config import Config
from src.core.types import CompanyProfile
from src.search.multi_engine import MultiEngineSearch
from src.search.profile_query_planner import (
    generate_social_queries,
    generate_social_watch_terms,
    get_priority_ecosystems,
)
from src.search.types import SearchResult

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
    source: str = "lunarcrush"  # "lunarcrush" | "fxtwitter" | "search_snippet"
    signal_type: str = "unknown"
    matched_account: str = ""
    matched_account_type: str = ""
    matched_ecosystems: list[str] = field(default_factory=list)
    monitoring_round: str = ""


@dataclass(frozen=True)
class TweetRef:
    """검색 결과에서 파싱한 tweet 식별자."""
    screen_name: str
    tweet_id: str
    url: str


@dataclass(frozen=True)
class SocialWatchAccount:
    """우선 추적할 VC / L1 / L2 / ecosystem 계정."""

    organization: str
    handle: str = ""
    search_names: list[str] = field(default_factory=list)
    account_type: str = ""
    priority: str = "tier2"
    ecosystems: list[str] = field(default_factory=list)
    programs: list[str] = field(default_factory=list)
    watch_terms: list[str] = field(default_factory=list)
    official_urls: list[str] = field(default_factory=list)
    region: str = ""


@dataclass(frozen=True)
class SocialMonitoringRound:
    """계정 그룹별 social monitoring round."""

    round_id: str
    queries: list[str] = field(default_factory=list)
    account_count: int = 0
    account_type: str = ""
    region: str = ""


# ============================================================
# Social Search Engine
# ============================================================

LUNARCRUSH_BASE = "https://lunarcrush.com/api4/public"
FXTWITTER_BASE = "https://api.fxtwitter.com"
TWEET_HOSTS = frozenset({
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "mobile.twitter.com",
})
MAX_SOCIAL_QUERIES = 8
MAX_ACCOUNT_WATCH_QUERIES = 18
MAX_TWEET_FETCHES = 20
DEFAULT_SOCIAL_WATCHLIST_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "curated_social_accounts.json"
)
DEFAULT_DISCOVERED_SOCIAL_ACCOUNTS_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "discovered_social_accounts.json"
)
DEFAULT_ECOSYSTEM_GRAPH_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "curated_ecosystem_graph.json"
)
DEFAULT_SOCIAL_REFERENCE_SEED_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "seed_raw.json"
)
DEFAULT_SOCIAL_VC_REGISTRY_CSV_PATH = (
    Path(__file__).resolve().parents[3] / "output" / "spreadsheet" / "vc_list_final.csv"
)
ACCOUNT_PRIORITY_SCORES = {
    "tier1": 1.0,
    "tier2": 0.8,
    "tier3": 0.6,
}
ACTIONABLE_SIGNAL_TYPES = frozenset({
    "applications_open",
    "grant_program",
    "accelerator_program",
    "builder_program",
    "ecosystem_fund",
    "residency_program",
})
SIGNAL_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    (
        "applications_open",
        (
            "applications open",
            "application is open",
            "apply now",
            "accepting applications",
            "open for applications",
        ),
    ),
    (
        "accelerator_program",
        (
            "accelerator",
            "cohort",
            "incubator",
            "demo day",
        ),
    ),
    (
        "residency_program",
        (
            "residency",
            "founder residency",
            "builder residency",
        ),
    ),
    (
        "builder_program",
        (
            "builder program",
            "builder incentive",
            "build program",
        ),
    ),
    (
        "grant_program",
        (
            "grant",
            "grants",
            "community grants",
            "open call",
            "rfp",
        ),
    ),
    (
        "ecosystem_fund",
        (
            "ecosystem fund",
            "fund launch",
            "funding program",
            "ecosystem funding",
        ),
    ),
    (
        "investment_announcement",
        (
            "invested in",
            "backed",
            "led the round",
            "led a",
            "seed round",
            "series a",
            "series b",
            "pre-seed",
            "investment",
            "portfolio",
        ),
    ),
]
APPLY_URL_HINTS = (
    "/apply",
    "apply.",
    "typeform.com",
    "airtable.com",
    "google.com/forms",
    "docs.google.com/forms",
    "hubspot.com",
    "hsforms",
    "form.typeform",
)
REFERENCE_SOCIAL_ACCOUNT_TYPES = frozenset({
    "vc",
    "foundation",
    "ecosystem",
    "accelerator_operator",
    "hybrid",
})
RESEARCH_ONLY_SIGNAL_TYPES = frozenset({
    "investment_announcement",
})


class SocialSearchEngine:
    """LunarCrush + FxTwitter 기반 소셜 검색 엔진.

    LunarCrush API 키가 없으면 graceful하게 빈 결과 반환.
    FxTwitter는 API 키 불필요.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._lunarcrush_key = config.lunarcrush_key
        self._web_search = MultiEngineSearch(config)
        org_official_urls = _load_org_official_urls(DEFAULT_ECOSYSTEM_GRAPH_PATH)
        curated_accounts = _load_social_watch_accounts(config.social_watchlist_path)
        discovered_accounts = _load_social_watch_accounts(
            config.discovered_social_accounts_path
        )
        vc_registry_accounts = _load_vc_csv_watch_accounts(
            config.social_vc_registry_csv_path,
            limit=config.social_reference_watch_limit,
        )
        reference_accounts = _load_reference_watch_accounts(
            config.social_reference_seed_path,
            limit=config.social_reference_watch_limit,
        )
        merged_accounts = _merge_watch_accounts(curated_accounts, discovered_accounts)
        merged_accounts = _merge_watch_accounts(merged_accounts, vc_registry_accounts)
        merged_accounts = _merge_watch_accounts(merged_accounts, reference_accounts)
        self._watch_accounts = _augment_watch_accounts_with_official_urls(
            merged_accounts,
            org_official_urls,
        )
        self._discovered_accounts_path = config.discovered_social_accounts_path
        self._site_handle_cache: dict[str, list[str]] = {}
        self._log = logger.bind(component="social_engine")

    async def search(
        self, profile: CompanyProfile
    ) -> list[dict[str, Any]]:
        """프로필 기반 소셜 검색.

        Returns:
            raw_opportunity dict 리스트 (FundingPipeline 호환)
        """
        queries = generate_social_queries(profile)
        dynamic_watch_accounts = await self._discover_site_watch_accounts(profile)
        self._persist_discovered_accounts(dynamic_watch_accounts)
        watch_accounts = _merge_watch_accounts(self._watch_accounts, dynamic_watch_accounts)
        watch_rounds = _build_monitoring_rounds(
            profile,
            watch_accounts,
            account_limit=self._config.social_watchlist_limit,
            terms_per_account=self._config.social_watch_terms_per_account,
        )
        lunar_task = self._search_lunarcrush(queries)
        x_task = self._search_x_via_web(queries, watch_rounds=watch_rounds)

        lunar_result, x_result = await asyncio.gather(
            lunar_task,
            x_task,
            return_exceptions=True,
        )

        lc_posts = self._safe_posts(lunar_result, "lunarcrush")
        x_posts = self._safe_posts(x_result, "x_search")
        all_posts = _dedup_posts(lc_posts + x_posts)
        annotated_posts = [
            _annotate_post(post, watch_accounts)
            for post in all_posts
        ]

        self._log.info(
            "social.search_complete",
            lunarcrush_posts=len(lc_posts),
            x_posts=len(x_posts),
            total_posts=len(all_posts),
            watch_queries=sum(len(round_item.queries) for round_item in watch_rounds),
            monitoring_rounds=len(watch_rounds),
            watch_accounts=len(watch_accounts),
            dynamic_accounts=len(dynamic_watch_accounts),
        )

        # 펀딩 관련 필터링
        funding_posts = _filter_funding_posts(annotated_posts)

        # SocialPost → raw_opportunity 변환
        return _posts_to_raw_opportunities(
            funding_posts,
            watch_accounts=watch_accounts,
        )

    async def analyze_tweet_url(
        self,
        tweet_url: str,
    ) -> tuple[SocialPost | None, list[dict[str, Any]]]:
        """단일 tweet URL을 FxTwitter로 읽고 funding candidate 여부를 분석."""
        post = await self.fetch_tweet_from_url(tweet_url)
        if post is None:
            return None, []

        annotated = _annotate_post(post, self._watch_accounts)
        funding_posts = _filter_funding_posts([annotated])
        if not funding_posts:
            return annotated, []

        raw = _posts_to_raw_opportunities(
            funding_posts,
            watch_accounts=self._watch_accounts,
        )
        return annotated, raw

    async def _discover_site_watch_accounts(
        self,
        profile: CompanyProfile,
    ) -> list[SocialWatchAccount]:
        """공식 사이트에서 X/Twitter profile 링크를 추출해 watchlist를 보강."""
        ranked_accounts = sorted(
            self._watch_accounts,
            key=lambda account: _watch_account_score(
                account,
                priority_ecosystems={eco.lower() for eco in get_priority_ecosystems(profile)},
                profile_terms=generate_social_watch_terms(profile),
            ),
            reverse=True,
        )
        candidates = ranked_accounts[: max(self._config.social_watchlist_limit, 6)]
        tasks = [
            self._discover_handles_for_account(account)
            for account in candidates
            if account.official_urls
        ]
        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        discovered: list[SocialWatchAccount] = []
        for item in results:
            if isinstance(item, list):
                discovered.extend(item)
        return discovered

    async def _discover_handles_for_account(
        self,
        account: SocialWatchAccount,
    ) -> list[SocialWatchAccount]:
        discovered: list[SocialWatchAccount] = []
        for official_url in account.official_urls[:2]:
            handles = await self._extract_handles_from_official_url(official_url)
            handles = _filter_handles_for_account(handles, account)
            for handle in handles:
                normalized = handle.lstrip("@").lower()
                if not normalized or normalized == account.handle.lstrip("@").lower():
                    continue
                discovered.append(
                    SocialWatchAccount(
                        organization=account.organization,
                        handle=normalized,
                        search_names=list(dict.fromkeys([*account.search_names, account.handle])),
                        account_type=account.account_type,
                        priority=account.priority,
                        ecosystems=account.ecosystems,
                        programs=account.programs,
                        watch_terms=account.watch_terms,
                        official_urls=account.official_urls,
                        region=account.region,
                    )
                )
        return discovered

    def _persist_discovered_accounts(
        self,
        discovered_accounts: list[SocialWatchAccount],
    ) -> None:
        if not discovered_accounts:
            return
        try:
            existing = _load_social_watch_accounts(self._discovered_accounts_path)
            merged = _merge_watch_accounts(existing, discovered_accounts)
            _save_social_watch_accounts(self._discovered_accounts_path, merged)
        except Exception as exc:
            self._log.warning(
                "social.persist_discovered_accounts_error",
                path=str(self._discovered_accounts_path),
                error=str(exc),
            )

    async def _extract_handles_from_official_url(self, official_url: str) -> list[str]:
        cached = self._site_handle_cache.get(official_url)
        if cached is not None:
            return cached

        handles: list[str] = []
        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                },
            ) as client:
                resp = await client.get(official_url)
                if resp.status_code == 200 and resp.text:
                    handles = _extract_social_handles_from_html(resp.text)
        except Exception as exc:
            self._log.debug(
                "social.official_handle_discovery_error",
                url=official_url,
                error=str(exc),
            )

        self._site_handle_cache[official_url] = handles
        return handles

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

    async def _search_x_via_web(
        self,
        queries: list[str],
        watch_queries: list[str] | None = None,
        watch_rounds: list[SocialMonitoringRound] | None = None,
    ) -> list[SocialPost]:
        """검색 엔진으로 X/Twitter status URL을 찾고 FxTwitter로 본문 확장."""
        generic_queries = _build_x_search_queries(queries, limit=MAX_SOCIAL_QUERIES)
        search_rounds: list[SocialMonitoringRound] = []
        if generic_queries:
            search_rounds.append(
                SocialMonitoringRound(
                    round_id="topic-discovery",
                    queries=generic_queries,
                )
            )
        if watch_queries:
            fallback_queries = _build_x_search_queries(
                watch_queries,
                limit=MAX_ACCOUNT_WATCH_QUERIES,
            )
            if fallback_queries:
                search_rounds.append(
                    SocialMonitoringRound(
                        round_id="watch-fallback",
                        queries=fallback_queries,
                    )
                )
        if watch_rounds:
            search_rounds.extend(round_item for round_item in watch_rounds if round_item.queries)

        if not search_rounds:
            return []

        posts: list[SocialPost] = []
        round_metrics: list[dict[str, Any]] = []
        for round_item in search_rounds:
            round_posts, round_metric = await self._execute_monitoring_round(round_item)
            posts.extend(round_posts)
            round_metrics.append(round_metric)

        self._log.info(
            "social.x_search_complete",
            queries=sum(len(round_item.queries) for round_item in search_rounds),
            rounds=len(search_rounds),
            posts=len(posts),
            round_metrics=round_metrics,
        )
        return posts

    async def _execute_monitoring_round(
        self,
        round_item: SocialMonitoringRound,
    ) -> tuple[list[SocialPost], dict[str, Any]]:
        search_results: list[SearchResult] = []
        if self._web_search.available_count > 0:
            search_results = await self._web_search.search_all(
                round_item.queries,
                max_results_per_query=5,
            )
        else:
            self._log.info("social.x_search_no_engines", round_id=round_item.round_id)

        if not search_results:
            search_results = await self._search_x_via_ddg(round_item.queries)

        tweet_results = _extract_tweet_results(search_results)
        if not tweet_results:
            return [], {
                "round_id": round_item.round_id,
                "queries": len(round_item.queries),
                "account_count": round_item.account_count,
                "account_type": round_item.account_type,
                "region": round_item.region,
                "search_results": len(search_results),
                "tweets": 0,
                "posts": 0,
            }

        tasks = [self._expand_tweet_result(result) for result in tweet_results]
        expanded = await asyncio.gather(*tasks, return_exceptions=True)

        posts: list[SocialPost] = []
        for item in expanded:
            if isinstance(item, SocialPost):
                item.monitoring_round = round_item.round_id
                posts.append(item)
            elif isinstance(item, Exception):
                self._log.warning(
                    "social.x_expand_error",
                    round_id=round_item.round_id,
                    error=str(item),
                )

        return posts, {
            "round_id": round_item.round_id,
            "queries": len(round_item.queries),
            "account_count": round_item.account_count,
            "account_type": round_item.account_type,
            "region": round_item.region,
            "search_results": len(search_results),
            "tweets": len(tweet_results),
            "posts": len(posts),
        }

    async def _search_x_via_ddg(
        self,
        x_queries: list[str],
    ) -> list[SearchResult]:
        """검색 provider가 없거나 quota에 막혔을 때 DDG HTML fallback."""
        results: list[SearchResult] = []
        seen: set[str] = set()

        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                },
            ) as client:
                for query in x_queries[:MAX_SOCIAL_QUERIES + MAX_ACCOUNT_WATCH_QUERIES]:
                    resp = await client.post(
                        "https://html.duckduckgo.com/html/",
                        data={"q": query, "kl": "us-en"},
                    )
                    if resp.status_code != 200:
                        continue
                    if "result__a" not in resp.text:
                        continue

                    soup = BeautifulSoup(resp.text, "lxml")
                    for a_tag in soup.find_all("a", class_="result__a"):
                        href = (a_tag.get("href") or "").strip()
                        if not href or href in seen:
                            continue
                        seen.add(href)
                        results.append(
                            SearchResult(
                                url=href,
                                title=a_tag.get_text(" ", strip=True),
                                snippet="",
                                score=0.5,
                                engine="ddg",
                            )
                        )
        except Exception as exc:
            self._log.warning("social.ddg_fallback_error", error=str(exc))
            return []

        self._log.info("social.ddg_fallback_done", results=len(results))
        return results

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
                tweet = data.get("tweet", {}) if isinstance(data, dict) else {}
                if not tweet and isinstance(data, dict):
                    tweet = data

                author_data = tweet.get("author", {}) or data.get("author", {})
                text = tweet.get("text", "") or data.get("text", "")
                tweet_url = (
                    tweet.get("url", "")
                    or data.get("url", "")
                    or f"https://x.com/{screen_name}/status/{tweet_id}"
                )
                author = (
                    author_data.get("screen_name", "")
                    or author_data.get("name", "")
                    or screen_name
                )
                extracted_urls = _unique_urls(
                    _extract_urls(text) + _extract_urls_from_payload(tweet)
                )

                return SocialPost(
                    text=text,
                    url=tweet_url,
                    author=author,
                    engagement=(
                        _safe_int(tweet.get("likes"))
                        + _safe_int(tweet.get("retweets"))
                        + _safe_int(tweet.get("replies"))
                    ),
                    extracted_urls=extracted_urls,
                    source="fxtwitter",
                )

        except Exception as e:
            self._log.debug(
                "social.fxtwitter_error",
                tweet_id=tweet_id,
                error=str(e),
            )
            return None

    async def fetch_tweet_from_url(self, tweet_url: str) -> SocialPost | None:
        """tweet URL을 파싱해 FxTwitter로 fetch."""
        ref = _parse_tweet_ref(tweet_url)
        if ref is None:
            return None
        return await self.fetch_tweet(ref.screen_name, ref.tweet_id)

    async def _expand_tweet_result(
        self,
        result: SearchResult,
    ) -> SocialPost | None:
        """검색 결과의 tweet URL을 FxTwitter로 확장하고, 실패 시 snippet으로 폴백."""
        ref = _parse_tweet_ref(result.url)
        if ref is None:
            return None

        post = await self.fetch_tweet(ref.screen_name, ref.tweet_id)
        if post is not None:
            if not post.url:
                post.url = ref.url
            if not post.author:
                post.author = ref.screen_name
            if not post.text:
                post.text = result.snippet or result.title
            if not post.extracted_urls:
                post.extracted_urls = _extract_urls(result.snippet)
            return post

        snippet_text = " ".join(
            part.strip() for part in [result.title, result.snippet] if part
        ).strip()
        if not snippet_text:
            return None

        return SocialPost(
            text=snippet_text,
            url=ref.url,
            author=ref.screen_name,
            engagement=max(int(result.score * 100), 0),
            extracted_urls=_extract_urls(snippet_text),
            source="search_snippet",
        )

    def _safe_posts(
        self,
        result: list[SocialPost] | Exception,
        source: str,
    ) -> list[SocialPost]:
        """gather 결과에서 post 리스트를 안전하게 추출."""
        if isinstance(result, list):
            return result

        self._log.warning(
            "social.source_error",
            source=source,
            error=str(result),
        )
        return []


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

        signal_type = post.signal_type or _classify_signal_type(post.text)
        if signal_type == "unknown":
            if not any(kw in text_lower for kw in FUNDING_KEYWORDS):
                continue
            signal_type = "generic_funding"

        post.signal_type = signal_type
        filtered.append(post)

    # engagement 순 정렬
    filtered.sort(
        key=lambda p: (
            1 if p.matched_account else 0,
            1 if p.signal_type in ACTIONABLE_SIGNAL_TYPES else 0,
            p.engagement,
        ),
        reverse=True,
    )
    return filtered


def _dedup_posts(posts: list[SocialPost]) -> list[SocialPost]:
    """URL/text 기준 중복 제거."""
    deduped: list[SocialPost] = []
    seen_urls: set[str] = set()
    seen_texts: set[str] = set()

    for post in posts:
        url_key = post.url.strip().lower()
        text_key = post.text.strip().lower()[:240]

        if url_key and url_key in seen_urls:
            continue
        if text_key and text_key in seen_texts:
            continue

        if url_key:
            seen_urls.add(url_key)
        if text_key:
            seen_texts.add(text_key)
        deduped.append(post)

    return deduped


def _posts_to_raw_opportunities(
    posts: list[SocialPost],
    watch_accounts: list[SocialWatchAccount] | None = None,
) -> list[dict[str, Any]]:
    """SocialPost → raw_opportunity dict 변환."""
    results: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    watch_accounts = watch_accounts or []

    for post in posts:
        matched_account = _match_watch_account(post, watch_accounts)
        signal_type = post.signal_type or _classify_signal_type(post.text)
        apply_url = _select_apply_url(post.extracted_urls)
        source_url = _select_source_url(post.extracted_urls, post.url)
        if not _is_actionable_social_candidate(
            post,
            apply_url=apply_url,
            source_url=source_url,
        ):
            continue

        # 포스트 텍스트에서 프로그램 정보 추출 (간단 패턴 매칭)
        org_name, prog_name = _extract_names_from_text(post.text)

        if matched_account and not org_name:
            org_name = matched_account.organization
        if not org_name:
            org_name = post.author or "Unknown"

        prog_name = _resolve_program_name(
            post.text,
            org_name,
            prog_name,
            signal_type,
            matched_account,
        )
        if not prog_name or len(post.text) < 30:
            continue

        category = _guess_category_from_signal(signal_type, post.text)
        key = (
            normalize_social_value(org_name),
            normalize_social_value(prog_name),
            normalize_social_value(apply_url or source_url),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)

        results.append({
            "organization": org_name,
            "program": prog_name,
            "category": category,
            "status": "unknown",
            "apply_url": apply_url,
            "source_url": source_url,
            "source_type": "social",
            "description": post.text[:500],
            "confidence": 0.45 if matched_account else 0.40,
            "source_tier": 5,         # SNS
            "fact_confidence": 0.45 if matched_account else 0.40,
            "social_signal_type": signal_type,
            "matched_account": matched_account.organization if matched_account else "",
            "matched_account_type": (
                matched_account.account_type if matched_account else ""
            ),
            "matched_ecosystems": (
                matched_account.ecosystems if matched_account else []
            ),
            "social_monitoring_round": post.monitoring_round,
        })

    return results


def _is_actionable_social_candidate(
    post: SocialPost,
    *,
    apply_url: str,
    source_url: str,
) -> bool:
    signal_type = post.signal_type or _classify_signal_type(post.text)
    text_lower = post.text.lower()

    if signal_type in RESEARCH_ONLY_SIGNAL_TYPES:
        return False
    if signal_type in ACTIONABLE_SIGNAL_TYPES:
        return True
    if signal_type == "ecosystem_fund":
        return bool(apply_url) or any(
            marker in text_lower
            for marker in ("applications open", "apply", "open call", "submit")
        )
    if signal_type == "generic_funding":
        return bool(apply_url or source_url)
    return bool(apply_url)


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


def _extract_urls_from_payload(tweet: dict[str, Any]) -> list[str]:
    """FxTwitter payload에서 외부 URL 후보 추출."""
    urls: list[str] = []

    entities = tweet.get("entities", {}) if isinstance(tweet, dict) else {}
    entity_urls = entities.get("urls", []) if isinstance(entities, dict) else []
    if isinstance(entity_urls, list):
        for item in entity_urls:
            if not isinstance(item, dict):
                continue
            expanded = item.get("expanded_url") or item.get("url")
            if expanded:
                urls.append(expanded)

    links = tweet.get("links", [])
    if isinstance(links, list):
        for item in links:
            if isinstance(item, str):
                urls.append(item)
            elif isinstance(item, dict):
                expanded = item.get("expanded_url") or item.get("url")
                if expanded:
                    urls.append(expanded)

    return _unique_urls(urls)


def _build_x_search_queries(
    queries: list[str],
    limit: int = MAX_SOCIAL_QUERIES,
) -> list[str]:
    """일반 검색 엔진으로 X/Twitter status를 찾기 위한 쿼리."""
    x_queries: list[str] = []

    for query in queries[:limit]:
        x_queries.append(f'site:x.com "{query}"')
        x_queries.append(f'site:twitter.com "{query}"')

    seen: set[str] = set()
    unique: list[str] = []
    for query in x_queries:
        key = query.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        unique.append(query)

    return unique


def _merge_queries(*query_sets: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for query_set in query_sets:
        for query in query_set:
            key = query.lower().strip()
            if key in seen:
                continue
            seen.add(key)
            merged.append(query)
    return merged


def _extract_tweet_results(
    search_results: list[SearchResult],
) -> list[SearchResult]:
    """검색 결과에서 tweet URL만 추출."""
    seen: set[tuple[str, str]] = set()
    tweet_results: list[SearchResult] = []

    ranked_results = sorted(
        search_results,
        key=lambda item: item.score,
        reverse=True,
    )

    for result in ranked_results:
        ref = _parse_tweet_ref(result.url)
        if ref is None:
            continue

        key = (ref.screen_name.lower(), ref.tweet_id)
        if key in seen:
            continue
        seen.add(key)
        tweet_results.append(result)

        if len(tweet_results) >= MAX_TWEET_FETCHES:
            break

    return tweet_results


def _parse_tweet_ref(url: str) -> TweetRef | None:
    """X/Twitter status URL → TweetRef."""
    if not url:
        return None

    parsed = urlparse(url)
    if parsed.netloc.lower() not in TWEET_HOSTS:
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 3:
        return None
    if parts[1] != "status":
        return None
    if parts[0].lower() in {"i", "status"}:
        return None

    tweet_id = parts[2]
    if not tweet_id.isdigit():
        return None

    normalized_url = f"https://{parsed.netloc}{'/'.join([''] + parts[:3])}"
    return TweetRef(
        screen_name=parts[0],
        tweet_id=tweet_id,
        url=normalized_url,
    )


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


def _guess_category_from_signal(signal_type: str, text: str) -> str:
    if signal_type in {"applications_open", "accelerator_program"}:
        return "accelerator"
    if signal_type == "residency_program":
        return "residency"
    if signal_type == "builder_program":
        return "builder_program"
    if signal_type == "grant_program":
        return "grant"
    if signal_type in {"ecosystem_fund", "investment_announcement"}:
        return "fund"
    return _guess_category_from_text(text)


def _load_social_watch_accounts(path: Path | str) -> list[SocialWatchAccount]:
    filepath = Path(path) if path else DEFAULT_SOCIAL_WATCHLIST_PATH
    if not filepath.exists():
        return []

    try:
        with filepath.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return []

    accounts: list[SocialWatchAccount] = []
    for item in payload.get("accounts", []):
        if not isinstance(item, dict):
            continue
        accounts.append(
            SocialWatchAccount(
                organization=item.get("organization", ""),
                handle=item.get("handle", ""),
                search_names=list(item.get("search_names", []) or []),
                account_type=item.get("account_type", ""),
                priority=item.get("priority", "tier2"),
                ecosystems=list(item.get("ecosystems", []) or []),
                programs=list(item.get("programs", []) or []),
                watch_terms=list(item.get("watch_terms", []) or []),
                official_urls=list(item.get("official_urls", []) or []),
                region=item.get("region", "") or "",
            )
        )
    return accounts


def _save_social_watch_accounts(
    path: Path | str,
    accounts: list[SocialWatchAccount],
) -> None:
    filepath = Path(path) if path else DEFAULT_DISCOVERED_SOCIAL_ACCOUNTS_PATH
    filepath.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "accounts": [
            {
                "organization": account.organization,
                "handle": account.handle,
                "search_names": account.search_names,
                "account_type": account.account_type,
                "priority": account.priority,
                "ecosystems": account.ecosystems,
                "programs": account.programs,
                "watch_terms": account.watch_terms,
                "official_urls": account.official_urls,
                "region": account.region,
            }
            for account in sorted(
                accounts,
                key=lambda item: (
                    normalize_social_value(item.organization),
                    normalize_social_value(item.handle),
                ),
            )
        ],
    }
    filepath.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_reference_watch_accounts(
    path: Path | str,
    *,
    limit: int = 120,
) -> list[SocialWatchAccount]:
    filepath = Path(path) if path else DEFAULT_SOCIAL_REFERENCE_SEED_PATH
    if not filepath.exists():
        return []

    try:
        payload = json.loads(filepath.read_text(encoding="utf-8"))
    except Exception:
        return []

    if not isinstance(payload, list):
        return []

    grouped: dict[str, SocialWatchAccount] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        organization = str(item.get("organization", "")).strip()
        if not organization:
            continue
        account_type = _infer_reference_account_type(item)
        if account_type not in REFERENCE_SOCIAL_ACCOUNT_TYPES:
            continue

        official_urls = _reference_official_urls(item)
        if not official_urls:
            continue

        key = normalize_social_value(organization)
        current = grouped.get(key)
        watch_terms = _default_watch_terms_for_account_type(account_type, item)
        programs = [str(item.get("program", "")).strip()] if str(item.get("program", "")).strip() else []
        raw_ecosystems = (
            item.get("target_ecosystems")
            or item.get("matched_ecosystems")
            or []
        )
        if isinstance(raw_ecosystems, str):
            ecosystems = [raw_ecosystems] if raw_ecosystems.strip() else []
        else:
            ecosystems = [str(value).strip() for value in raw_ecosystems if str(value).strip()]

        candidate = SocialWatchAccount(
            organization=organization,
            handle="",
            search_names=[organization],
            account_type=account_type,
            priority=_reference_priority_for_item(item, account_type),
            ecosystems=ecosystems,
            programs=programs,
            watch_terms=watch_terms,
            official_urls=official_urls,
            region=str(item.get("industry_category", "")).strip(),
        )
        if current is None:
            grouped[key] = candidate
            continue
        grouped[key] = _merge_watch_accounts([current], [candidate])[0]

    ranked = sorted(
        grouped.values(),
        key=lambda account: (
            ACCOUNT_PRIORITY_SCORES.get(account.priority, 0.5),
            len(account.programs),
            len(account.official_urls),
        ),
        reverse=True,
    )
    return ranked[:limit]


def _load_vc_csv_watch_accounts(
    path: Path | str,
    *,
    limit: int = 120,
) -> list[SocialWatchAccount]:
    filepath = Path(path) if path else DEFAULT_SOCIAL_VC_REGISTRY_CSV_PATH
    if not filepath.exists():
        return []

    grouped: dict[str, SocialWatchAccount] = {}
    try:
        with filepath.open(encoding="utf-8") as f:
            rows = csv.DictReader(f)
            for row in rows:
                organization = str(row.get("organization", "")).strip()
                website = str(row.get("website", "")).strip()
                if not organization or not website:
                    continue
                key = normalize_social_value(organization)
                candidate = SocialWatchAccount(
                    organization=organization,
                    handle="",
                    search_names=[organization],
                    account_type="vc",
                    priority="tier2",
                    ecosystems=[],
                    programs=[str(row.get("program", "")).strip()] if str(row.get("program", "")).strip() else [],
                    watch_terms=_default_watch_terms_for_account_type("vc", row),
                    official_urls=_expand_official_urls([website]),
                    region=str(row.get("industry_category", "")).strip(),
                )
                if key not in grouped:
                    grouped[key] = candidate
                else:
                    grouped[key] = _merge_watch_accounts([grouped[key]], [candidate])[0]
    except Exception:
        return []

    ranked = sorted(
        grouped.values(),
        key=lambda account: (
            ACCOUNT_PRIORITY_SCORES.get(account.priority, 0.5),
            len(account.official_urls),
            len(account.programs),
        ),
        reverse=True,
    )
    return ranked[:limit]


def _load_org_official_urls(path: Path | str) -> dict[str, list[str]]:
    filepath = Path(path)
    if not filepath.exists():
        return {}

    try:
        with filepath.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return {}

    urls_by_org: dict[str, list[str]] = {}
    for item in payload.get("organizations", []):
        if not isinstance(item, dict):
            continue
        org_name = normalize_social_value(item.get("name", ""))
        if not org_name:
            continue
        urls = [str(url).strip() for url in (item.get("official_urls") or []) if str(url).strip()]
        if urls:
            urls_by_org[org_name] = urls
    return urls_by_org


def _augment_watch_accounts_with_official_urls(
    accounts: list[SocialWatchAccount],
    org_official_urls: dict[str, list[str]],
) -> list[SocialWatchAccount]:
    augmented: list[SocialWatchAccount] = []
    for account in accounts:
        official_urls = list(account.official_urls)
        if not official_urls:
            official_urls = org_official_urls.get(
                normalize_social_value(account.organization),
                [],
            )
        official_urls = _expand_official_urls(official_urls)
        augmented.append(
            SocialWatchAccount(
                organization=account.organization,
                handle=account.handle,
                search_names=account.search_names,
                account_type=account.account_type,
                priority=account.priority,
                ecosystems=account.ecosystems,
                programs=account.programs,
                watch_terms=account.watch_terms,
                official_urls=official_urls,
                region=account.region,
            )
        )
    return augmented


def _expand_official_urls(urls: list[str]) -> list[str]:
    expanded: list[str] = []
    for url in urls:
        cleaned = (url or "").strip()
        if not cleaned:
            continue
        if cleaned not in expanded:
            expanded.append(cleaned)
        parsed = urlparse(cleaned)
        if parsed.scheme and parsed.netloc:
            root = f"{parsed.scheme}://{parsed.netloc}/"
            if root not in expanded:
                expanded.append(root)
    return expanded


def _reference_official_urls(item: dict[str, Any]) -> list[str]:
    urls = [
        str(item.get("website", "")).strip(),
        str(item.get("program_url", "")).strip(),
    ]
    filtered: list[str] = []
    for url in urls:
        if not url or not url.startswith("http"):
            continue
        lowered = url.lower()
        if any(host in lowered for host in (
            "typeform.com",
            "airtable.com",
            "google.com/forms",
            "docs.google.com/forms",
            "hubspot.com",
        )):
            continue
        if url not in filtered:
            filtered.append(url)
    return filtered


def _infer_reference_account_type(item: dict[str, Any]) -> str:
    org_type = normalize_social_value(str(item.get("org_type", "")))
    category = normalize_social_value(str(item.get("category", "")))
    program_type = normalize_social_value(str(item.get("program_type", "")))

    if org_type in REFERENCE_SOCIAL_ACCOUNT_TYPES:
        return org_type
    if category == "fund" or program_type in {"fund", "vc_fund"}:
        return "vc"
    if program_type in {"accelerator", "vc_cohort", "residency"}:
        return "accelerator_operator"
    if category in {"grant", "builder_program"}:
        return "foundation"
    return ""


def _default_watch_terms_for_account_type(
    account_type: str,
    item: dict[str, Any],
) -> list[str]:
    program = str(item.get("program", "")).strip()
    program_type = normalize_social_value(str(item.get("program_type", "")))
    terms_by_type = {
        "vc": ["applications open", "accelerator", "cohort", "founder residency", "builder program"],
        "accelerator_operator": ["applications open", "accelerator", "cohort", "apply", "demo day"],
        "foundation": ["grant", "grants", "open call", "builder program", "funding"],
        "ecosystem": ["grant", "builder program", "applications open", "accelerator"],
        "hybrid": ["applications open", "grant", "accelerator", "builder program", "cohort"],
    }
    terms = [*terms_by_type.get(account_type, [])]
    if program:
        terms.append(program.lower())
    if program_type in {"vc_cohort", "accelerator"}:
        terms.append("applications open")
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        key = normalize_social_value(term)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(term)
    return unique


def _reference_priority_for_item(item: dict[str, Any], account_type: str) -> str:
    category = normalize_social_value(str(item.get("category", "")))
    if account_type in {"vc", "accelerator_operator"} and category in {"fund", "accelerator"}:
        return "tier2"
    if account_type in {"foundation", "ecosystem"} and category in {"grant", "builder_program"}:
        return "tier2"
    return "tier3"


def _build_watch_queries(
    profile: CompanyProfile,
    watch_accounts: list[SocialWatchAccount],
    account_limit: int = 10,
    terms_per_account: int = 3,
) -> list[str]:
    """프로필 관련 VC/L1/L2 계정 위주로 타게팅 query 생성."""
    rounds = _build_monitoring_rounds(
        profile,
        watch_accounts,
        account_limit=account_limit,
        terms_per_account=terms_per_account,
    )
    return _merge_queries(*[round_item.queries for round_item in rounds])


def _build_monitoring_rounds(
    profile: CompanyProfile,
    watch_accounts: list[SocialWatchAccount],
    account_limit: int = 10,
    terms_per_account: int = 3,
) -> list[SocialMonitoringRound]:
    """프로필 우선 + 나라/지역별 VC + ecosystem operator 별 monitoring round."""
    if not watch_accounts:
        return []

    priority_ecosystems = {eco.lower() for eco in get_priority_ecosystems(profile)}
    profile_terms = generate_social_watch_terms(profile)
    ranked_accounts = sorted(
        watch_accounts,
        key=lambda account: _watch_account_score(
            account,
            priority_ecosystems=priority_ecosystems,
            profile_terms=profile_terms,
        ),
        reverse=True,
    )

    rounds: list[SocialMonitoringRound] = []
    selected_accounts = _select_watch_accounts(
        ranked_accounts,
        account_limit=account_limit,
    )
    selected_queries = _build_account_queries(
        selected_accounts,
        profile_terms,
        terms_per_account=terms_per_account,
    )
    if selected_queries:
        rounds.append(
            SocialMonitoringRound(
                round_id="profile-priority",
                queries=selected_queries,
                account_count=len(selected_accounts),
                account_type="mixed",
            )
        )

    per_region_limit = max(2, min(4, account_limit // 2 or 2))
    vc_accounts = [account for account in ranked_accounts if account.account_type == "vc"]
    region_groups: dict[str, list[SocialWatchAccount]] = {}
    for account in vc_accounts:
        region_key = normalize_social_value(account.region) or "unknown"
        region_groups.setdefault(region_key, []).append(account)

    for region_key in sorted(
        region_groups,
        key=lambda value: (
            value == "unknown",
            value == "web2",
            value,
        ),
    ):
        region_accounts = region_groups[region_key][:per_region_limit]
        region_queries = _build_account_queries(
            region_accounts,
            profile_terms,
            terms_per_account=max(1, min(terms_per_account, 2)),
        )
        if not region_queries:
            continue
        rounds.append(
            SocialMonitoringRound(
                round_id=f"vc-{region_key}",
                queries=region_queries,
                account_count=len(region_accounts),
                account_type="vc",
                region=region_key,
            )
        )

    ecosystem_accounts = [
        account
        for account in ranked_accounts
        if account.account_type in {"foundation", "ecosystem", "accelerator_operator", "hybrid"}
    ][: max(4, account_limit // 2)]
    ecosystem_queries = _build_account_queries(
        ecosystem_accounts,
        profile_terms,
        terms_per_account=terms_per_account,
    )
    if ecosystem_queries:
        rounds.append(
            SocialMonitoringRound(
                round_id="ecosystem-operators",
                queries=ecosystem_queries,
                account_count=len(ecosystem_accounts),
                account_type="ecosystem",
            )
        )

    return rounds


def _build_account_queries(
    accounts: list[SocialWatchAccount],
    profile_terms: list[str],
    *,
    terms_per_account: int,
) -> list[str]:
    queries: list[str] = []
    for account in accounts:
        identifiers = [
            identifier
            for identifier in [
                account.handle,
                *account.search_names[:2],
                account.organization,
            ]
            if identifier
        ]
        terms = _prioritize_watch_terms(
            account,
            profile_terms,
            terms_per_account=terms_per_account,
        )

        if account.handle:
            handle = account.handle.lstrip("@")
            for term in terms[:terms_per_account]:
                queries.append(f'site:x.com/{handle}/status "{term}"')
                queries.append(f'site:twitter.com/{handle}/status "{term}"')

        for identifier in identifiers[:2]:
            for term in terms[:terms_per_account]:
                queries.append(f"{identifier} {term}")

    return _merge_queries(queries)


def _select_watch_accounts(
    ranked_accounts: list[SocialWatchAccount],
    *,
    account_limit: int,
) -> list[SocialWatchAccount]:
    if len(ranked_accounts) <= account_limit:
        return ranked_accounts

    selected: list[SocialWatchAccount] = []
    seen: set[tuple[str, str]] = set()

    def add_account(account: SocialWatchAccount) -> None:
        key = (
            normalize_social_value(account.organization),
            normalize_social_value(account.handle),
        )
        if key in seen:
            return
        seen.add(key)
        selected.append(account)

    primary_budget = max(1, account_limit // 2)
    for account in ranked_accounts[:primary_budget]:
        add_account(account)

    vc_by_region: dict[str, SocialWatchAccount] = {}
    for account in ranked_accounts:
        if account.account_type != "vc":
            continue
        region = normalize_social_value(account.region) or "unknown"
        if region not in vc_by_region:
            vc_by_region[region] = account
    for region in sorted(
        vc_by_region,
        key=lambda value: (
            value == "unknown",
            value == "web2",
            value,
        ),
    ):
        if len(selected) >= account_limit:
            break
        add_account(vc_by_region[region])

    for account in ranked_accounts:
        if len(selected) >= account_limit:
            break
        add_account(account)

    return selected[:account_limit]


def _prioritize_watch_terms(
    account: SocialWatchAccount,
    profile_terms: list[str],
    *,
    terms_per_account: int,
) -> list[str]:
    actionable_by_type = {
        "vc": [
            "applications open",
            "accelerator",
            "cohort",
            "founder residency",
            "builder program",
            "apply",
        ],
        "accelerator_operator": [
            "applications open",
            "accelerator",
            "cohort",
            "apply",
            "demo day",
        ],
        "foundation": [
            "grant",
            "grants",
            "open call",
            "builder program",
            "applications open",
            "funding program",
        ],
        "ecosystem": [
            "grant",
            "builder program",
            "ecosystem funding",
            "applications open",
            "accelerator",
        ],
        "hybrid": [
            "applications open",
            "grant",
            "accelerator",
            "builder program",
            "cohort",
        ],
    }
    prioritized = [
        *actionable_by_type.get(account.account_type, []),
        *account.watch_terms,
        *profile_terms,
    ]
    seen: set[str] = set()
    merged: list[str] = []
    for term in prioritized:
        key = normalize_social_value(term)
        if not key or key in seen:
            continue
        if key in {"investment", "invested", "backed", "portfolio"}:
            continue
        seen.add(key)
        merged.append(term)
        if len(merged) >= max(terms_per_account, 1) * 2:
            break
    return merged or profile_terms[:terms_per_account]


def _merge_watch_accounts(
    base_accounts: list[SocialWatchAccount],
    discovered_accounts: list[SocialWatchAccount],
) -> list[SocialWatchAccount]:
    merged: dict[tuple[str, str], SocialWatchAccount] = {}
    for account in [*base_accounts, *discovered_accounts]:
        org_key = normalize_social_value(account.organization)
        handle_key = normalize_social_value(account.handle)
        key = (org_key, handle_key)
        if handle_key:
            org_fallback_key = (org_key, "")
            if org_fallback_key in merged:
                key = org_fallback_key
        else:
            non_empty_key = next(
                (existing_key for existing_key in merged if existing_key[0] == org_key and existing_key[1]),
                None,
            )
            if non_empty_key is not None:
                key = non_empty_key
        if key not in merged:
            merged[key] = account
            continue
        existing = merged[key]
        merged[key] = SocialWatchAccount(
            organization=existing.organization or account.organization,
            handle=existing.handle or account.handle,
            search_names=list(dict.fromkeys([*existing.search_names, *account.search_names])),
            account_type=existing.account_type or account.account_type,
            priority=existing.priority if ACCOUNT_PRIORITY_SCORES.get(existing.priority, 0) >= ACCOUNT_PRIORITY_SCORES.get(account.priority, 0) else account.priority,
            ecosystems=list(dict.fromkeys([*existing.ecosystems, *account.ecosystems])),
            programs=list(dict.fromkeys([*existing.programs, *account.programs])),
            watch_terms=list(dict.fromkeys([*existing.watch_terms, *account.watch_terms])),
            official_urls=list(dict.fromkeys([*existing.official_urls, *account.official_urls])),
            region=existing.region or account.region,
        )
    return list(merged.values())


def _watch_account_score(
    account: SocialWatchAccount,
    *,
    priority_ecosystems: set[str],
    profile_terms: list[str],
) -> float:
    score = ACCOUNT_PRIORITY_SCORES.get(account.priority, 0.5)
    if priority_ecosystems.intersection({eco.lower() for eco in account.ecosystems}):
        score += 0.75

    account_text = " ".join([
        account.organization,
        account.handle,
        *account.search_names,
        *account.watch_terms,
        *account.programs,
    ]).lower()
    if any(term.lower() in account_text for term in profile_terms[:8]):
        score += 0.25

    if account.account_type in {"vc", "foundation", "ecosystem", "accelerator_operator"}:
        score += 0.05
    if account.official_urls:
        score += 0.05
    return score


def _annotate_post(
    post: SocialPost,
    watch_accounts: list[SocialWatchAccount],
) -> SocialPost:
    matched_account = _match_watch_account(post, watch_accounts)
    signal_type = _classify_signal_type(post.text)

    if matched_account:
        post.matched_account = matched_account.organization
        post.matched_account_type = matched_account.account_type
        post.matched_ecosystems = list(matched_account.ecosystems)
    post.signal_type = signal_type
    return post


def _match_watch_account(
    post: SocialPost,
    watch_accounts: list[SocialWatchAccount],
) -> SocialWatchAccount | None:
    text = f"{post.text} {post.url}".lower()
    author = (post.author or "").lower().lstrip("@")
    best: tuple[float, SocialWatchAccount] | None = None

    for account in watch_accounts:
        score = 0.0
        handle = account.handle.lower().lstrip("@")
        if handle and author == handle:
            score += 2.0
        if handle and f"/{handle}/status/" in text:
            score += 1.5
        if any(name.lower() in text for name in [account.organization, *account.search_names]):
            score += 1.0
        if score == 0.0:
            continue
        if best is None or score > best[0]:
            best = (score, account)

    return best[1] if best else None


def _classify_signal_type(text: str) -> str:
    text_lower = text.lower()
    for signal_type, patterns in SIGNAL_PATTERNS:
        if any(pattern in text_lower for pattern in patterns):
            return signal_type
    return "unknown"


def _select_apply_url(urls: list[str]) -> str:
    for url in urls:
        cleaned = (url or "").strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if any(hint in lowered for hint in APPLY_URL_HINTS):
            return cleaned
    return ""


def _select_source_url(urls: list[str], fallback_url: str) -> str:
    for url in urls:
        cleaned = (url or "").strip()
        if cleaned:
            return cleaned
    return fallback_url


def _resolve_program_name(
    text: str,
    org_name: str,
    existing_program: str,
    signal_type: str,
    matched_account: SocialWatchAccount | None,
) -> str:
    if existing_program:
        return existing_program

    text_lower = text.lower()
    if matched_account:
        for program in matched_account.programs:
            if program.lower() in text_lower:
                return program

    if signal_type == "applications_open" and "accelerator" in text_lower:
        return f"{org_name} Accelerator"
    if signal_type == "grant_program":
        return f"{org_name} Grants"
    if signal_type == "builder_program":
        return f"{org_name} Builder Program"
    if signal_type == "residency_program":
        return f"{org_name} Residency"
    if signal_type == "ecosystem_fund":
        return f"{org_name} Ecosystem Fund"
    if signal_type == "investment_announcement":
        return f"{org_name} Investment Activity"
    if matched_account and matched_account.programs:
        return matched_account.programs[0]
    return f"{org_name} Program"


def normalize_social_value(value: str) -> str:
    return (value or "").strip().lower()


def _extract_social_handles_from_html(html: str) -> list[str]:
    """공식 사이트 HTML에서 x.com/twitter.com profile handle 추출."""
    handles: list[str] = []
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return []

    for anchor in soup.find_all("a", href=True):
        href = (anchor.get("href") or "").strip()
        handle = _extract_social_handle_from_url(href)
        if handle and handle not in handles:
            handles.append(handle)
    return handles


def _extract_social_handle_from_url(url: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host not in TWEET_HOSTS:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 1:
        return None
    handle = parts[0].strip().lstrip("@")
    if not handle:
        return None
    if handle.lower() in {"share", "home", "intent", "search"}:
        return None
    return handle


def _filter_handles_for_account(
    handles: list[str],
    account: SocialWatchAccount,
) -> list[str]:
    """공식 사이트에서 발견한 handle 중 조직과 닮은 것만 유지."""
    tokens: set[str] = set()
    for value in [account.organization, *account.search_names]:
        cleaned = normalize_social_value(value).replace("-", " ").replace("_", " ")
        for token in cleaned.split():
            token = token.strip()
            if len(token) >= 4:
                tokens.add(token)

    filtered: list[str] = []
    for handle in handles:
        normalized = normalize_social_value(handle).replace("-", "").replace("_", "")
        if any(token.replace(" ", "") in normalized for token in tokens):
            filtered.append(handle)

    return filtered or handles[:1]


def _unique_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        cleaned = (url or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        unique.append(cleaned)
    return unique


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
