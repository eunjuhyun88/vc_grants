"""
Funding Intelligence Agent — Discovery Agent.

DuckDuckGo + Tavily 병렬 검색 → httpx fetch → Groq LLM parse.
사실만 추출, deadline 추측 금지.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

from src.agents.base_agent import BaseAgent
from src.core.errors import DiscoveryError
from src.search.fetcher import extract_apply_surface_candidates, format_apply_surface_block
from src.core.types import (
    AgentResult,
    DiscoveryInput,
    DiscoveryOutput,
    ProgramCategory,
)

logger = structlog.get_logger()

# ============================================================
# 카테고리별 검색 쿼리 (간결하게 — DDG 키워드 과다 패널티 방지)
# ============================================================
CATEGORY_QUERIES: dict[str, list[str]] = {
    "grant": [
        "{query} grant program apply 2026",
        "{query} crypto web3 grants open",
    ],
    "accelerator": [
        "{query} accelerator program apply 2026",
        "{query} crypto web3 accelerator cohort open",
    ],
    "vc_cohort": [
        "{query} VC cohort seed funding apply",
        "{query} crypto venture fund open application",
    ],
    "ecosystem_builder": [
        "{query} ecosystem builder program apply",
        "{query} developer program web3 grants",
    ],
}

# ============================================================
# non-funding 도메인 필터 (검색 결과에서 제거)
# ============================================================
BLOCKED_DOMAINS = {
    "wikipedia.org", "namu.wiki", "namu.com",
    "youtube.com", "youtu.be",
    "reddit.com", "twitter.com", "x.com",
    "facebook.com", "instagram.com",
    "tiktok.com", "linkedin.com",
    "medium.com",  # 블로그 → 직접 URL 지정 시에만 허용
    "blog.naver.com", "tistory.com",
    "chatgpt.com", "openai.com",
}

MAX_QUERY_VARIANTS = 4


def _is_valid_funding_url(url: str) -> bool:
    """검색 결과 URL 필터링: non-funding 도메인 제거."""
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
        for blocked in BLOCKED_DOMAINS:
            if blocked in domain:
                return False
        return True
    except Exception:
        return False


def _query_variants(query: str, hint_queries: list[str]) -> list[str]:
    variants: list[str] = []
    seen: set[str] = set()

    for candidate in [query, *(hint_queries or [])]:
        normalized = " ".join((candidate or "").split()).strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        variants.append(candidate.strip())
        if len(variants) >= MAX_QUERY_VARIANTS:
            break

    return variants


def _opportunity_key(opp: dict[str, Any]) -> str:
    for key in ("apply_url", "source_url", "program_url"):
        value = str(opp.get(key) or "").strip().lower()
        if value:
            return f"url::{value}"
    org = str(opp.get("organization") or "").strip().lower()
    program = str(opp.get("program") or "").strip().lower()
    return f"name::{org}::{program}"


# ============================================================
# LLM 프롬프트 (개선됨)
# ============================================================
PARSE_PROMPT = """You are a funding opportunity extraction agent. Extract ALL funding opportunities from the webpage content below.

EXTRACTION RULES:
1. Extract ONLY facts explicitly stated in the content
2. NEVER guess deadlines — if not explicitly stated, set deadline to null
3. For apply_url: Search the "APPLY CANDIDATES" section at the bottom first. Custom Typeform subdomains and other external form hosts are valid even if the URL itself does not contain "apply"
4. Extract the EXACT budget/funding amount as written
5. For focus_areas: Extract the organization's focus sectors (e.g., "DeFi", "Infrastructure", "Gaming", "AI", "ZK")

OUTPUT FORMAT — Return ONLY a valid JSON array:
[
  {
    "organization": "Funding organization name",
    "program": "Specific program name",
    "category": "grant | accelerator | vc_cohort | ecosystem_builder",
    "status": "open | rolling | upcoming | closed | unknown",
    "deadline": "YYYY-MM-DD or null",
    "budget": "Exact amount text (e.g., '$50K-$500K') or null",
    "apply_url": "URL from APPLY CANDIDATES or content, or null if truly not found",
    "description": "One sentence summary of the program",
    "focus_areas": ["sector1", "sector2"]
  }
]

EXAMPLES of valid apply_url:
- "https://esp.ethereum.foundation/applicants"
- "https://airtable.com/shrXYZ"
- "https://form.typeform.com/to/abc123"
- "https://taverncommunity.typeform.com/to/RW1j6BMu"
- "https://solana.org/grants#apply"

If no opportunities found, return [].

WEBPAGE CONTENT:
"""


class DiscoveryAgent(BaseAgent):
    """펀딩 기회 검색 + 수집 Agent."""

    async def _execute(self, input_data: Any) -> AgentResult:
        if not isinstance(input_data, DiscoveryInput):
            raise DiscoveryError(
                message="input_data must be DiscoveryInput",
                fix="DiscoveryInput(query='...') 형태로 전달",
                context={"received": type(input_data).__name__},
            )

        query = input_data.query
        category = input_data.category
        sources = input_data.sources
        hint_queries = input_data.hint_queries

        self.log.info("discovery.start", query=query, category=category)

        # Agentic RAG 검색 시도 (3엔진 중 1개라도 키가 있으면)
        from src.search.multi_engine import MultiEngineSearch

        multi = MultiEngineSearch(self.config)
        if multi.available_count > 0 or sources:
            return await self._execute_agentic(query, category, sources, hint_queries)

        # 폴백: 기존 DDG 단일 검색
        self.log.info("discovery.fallback_ddg")
        return await self._execute_legacy(query, category, sources, hint_queries)

    async def _execute_agentic(
        self,
        query: str,
        category: ProgramCategory | None,
        sources: list[str],
        hint_queries: list[str],
    ) -> AgentResult:
        """Agentic RAG 검색 — SearchOrchestrator 위임."""
        from src.search.orchestrator import SearchOrchestrator

        orchestrator = SearchOrchestrator(self.config)
        cat_str = category.value if category else None
        queries = _query_variants(query, hint_queries)
        all_opportunities: list[dict[str, Any]] = []
        fetched_urls: list[str] = []
        seen_urls: set[str] = set()
        seen_opportunities: set[str] = set()

        for index, current_query in enumerate(queries):
            current_sources = sources if index == 0 and sources else None
            opportunities, urls = await orchestrator.search(
                query=current_query,
                category=cat_str,
                sources=current_sources,
            )
            for url in urls:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                fetched_urls.append(url)
            for opportunity in opportunities:
                key = _opportunity_key(opportunity)
                if key in seen_opportunities:
                    continue
                seen_opportunities.add(key)
                all_opportunities.append(opportunity)

        output = DiscoveryOutput(
            raw_opportunities=all_opportunities,
            source_urls=fetched_urls,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

        self.log.info(
            "discovery.agentic_complete",
            total_urls=len(fetched_urls),
            total_opportunities=len(all_opportunities),
        )

        return AgentResult(success=True, data=output.__dict__)

    async def _execute_legacy(
        self,
        query: str,
        category: ProgramCategory | None,
        sources: list[str],
        hint_queries: list[str],
    ) -> AgentResult:
        """기존 DDG 검색 폴백 (deprecated)."""
        all_urls: list[str] = []
        seen_urls: set[str] = set()
        for index, current_query in enumerate(_query_variants(query, hint_queries)):
            urls = await self._search(
                current_query,
                category,
                sources if index == 0 else [],
            )
            for url in urls:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                all_urls.append(url)

        if not all_urls:
            return AgentResult(
                success=True,
                data=DiscoveryOutput(
                    raw_opportunities=[],
                    source_urls=[],
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                ).__dict__,
            )

        all_opportunities: list[dict] = []
        fetched_urls: list[str] = []

        for url in all_urls[:10]:
            try:
                content = await self._fetch_page(url)
                if content:
                    opportunities = await self._parse_opportunities(content, url)
                    all_opportunities.extend(opportunities)
                    fetched_urls.append(url)
            except Exception as e:
                self.log.warning("discovery.fetch_failed", url=url, error=str(e))
                continue

        output = DiscoveryOutput(
            raw_opportunities=all_opportunities,
            source_urls=fetched_urls,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

        self.log.info(
            "discovery.legacy_complete",
            total_urls=len(fetched_urls),
            total_opportunities=len(all_opportunities),
        )

        return AgentResult(success=True, data=output.__dict__)

    # ============================================================
    # 검색
    # ============================================================

    async def _search(
        self,
        query: str,
        category: ProgramCategory | None,
        sources: list[str],
    ) -> list[str]:
        """DDG + Tavily 병렬 검색 → 합친 URL 목록."""
        if sources:
            return sources

        all_urls: list[str] = []
        seen: set[str] = set()

        def _add_urls(urls: list[str]) -> None:
            for u in urls:
                if u not in seen and _is_valid_funding_url(u):
                    seen.add(u)
                    all_urls.append(u)

        # DDG (항상 시도)
        ddg_urls = await self._search_ddg(query, category)
        _add_urls(ddg_urls)

        # Tavily (키가 있으면 같이 사용)
        if self.config.tavily_key:
            tavily_urls = await self._search_tavily(query, category)
            _add_urls(tavily_urls)

        self.log.info(
            "discovery.search_combined",
            ddg=len(ddg_urls),
            tavily=len(all_urls) - len(ddg_urls),
            total=len(all_urls),
        )

        return all_urls

    async def _search_ddg(
        self, query: str, category: ProgramCategory | None
    ) -> list[str]:
        """DuckDuckGo HTML 직접 호출 (kl=us-en). 라이브러리 locale 문제 회피."""
        try:
            cat_key = category.value if category else "grant"
            queries = CATEGORY_QUERIES.get(cat_key, CATEGORY_QUERIES["grant"])

            all_urls: list[str] = []
            seen: set[str] = set()

            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/120.0.0.0 Safari/537.36"
                },
            ) as client:
                for q_template in queries:
                    search_query = q_template.format(query=query)
                    resp = await client.post(
                        "https://html.duckduckgo.com/html/",
                        data={"q": search_query, "kl": "us-en"},
                    )
                    resp.raise_for_status()

                    soup = BeautifulSoup(resp.text, "lxml")
                    for a_tag in soup.find_all("a", class_="result__a"):
                        href = a_tag.get("href", "")
                        if href and href.startswith("http") and href not in seen:
                            seen.add(href)
                            all_urls.append(href)

            self.log.info("discovery.ddg_done", urls_found=len(all_urls))
            return all_urls

        except Exception as e:
            self.log.error("discovery.ddg_error", error=str(e))
            return []

    async def _search_tavily(
        self, query: str, category: ProgramCategory | None
    ) -> list[str]:
        """Tavily API 검색."""
        if not self.config.tavily_key:
            return []

        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=self.config.tavily_key)

            cat_key = category.value if category else "grant"
            queries = CATEGORY_QUERIES.get(cat_key, CATEGORY_QUERIES["grant"])
            search_query = queries[0].format(query=query)

            response = client.search(
                query=search_query,
                max_results=5,
                search_depth="advanced",
            )

            urls = [r["url"] for r in response.get("results", [])]
            self.log.info("discovery.tavily_done", urls_found=len(urls))
            return urls

        except Exception as e:
            self.log.error("discovery.tavily_error", error=str(e))
            return []

    # ============================================================
    # Fetch
    # ============================================================

    async def _fetch_page(self, url: str) -> str | None:
        """URL에서 텍스트 + 링크 추출."""
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/120.0.0.0 Safari/537.36"
                },
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "lxml")
            apply_candidates = extract_apply_surface_candidates(
                soup,
                base_url=str(resp.url),
                limit=20,
            )

            # 불필요한 태그 제거
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)

            apply_block = format_apply_surface_block(apply_candidates)
            if apply_block:
                text += "\n\n" + apply_block

            # 12000자로 확대 (하단 CTA 보존)
            if len(text) > 12000:
                text = text[:12000]

            return text if len(text) > 100 else None

        except Exception as e:
            self.log.warning("discovery.fetch_error", url=url, error=str(e))
            return None

    # ============================================================
    # LLM Parse
    # ============================================================

    async def _parse_opportunities(
        self, content: str, source_url: str
    ) -> list[dict]:
        """LLM으로 기회 추출. Groq 기본, Anthropic 폴백."""
        provider = self.config.llm_provider

        if provider == "groq":
            return await self._parse_with_groq(content, source_url)
        elif provider == "anthropic":
            return await self._parse_with_anthropic(content, source_url)
        else:
            return await self._parse_with_groq(content, source_url)

    async def _parse_with_groq(
        self, content: str, source_url: str
    ) -> list[dict]:
        """Groq (Llama) 로 파싱."""
        if not self.config.groq_key:
            self.log.warning("discovery.no_groq_key")
            return []

        try:
            from groq import Groq

            client = Groq(api_key=self.config.groq_key)

            response = client.chat.completions.create(
                model=self.config.llm_model_fast,
                messages=[
                    {
                        "role": "user",
                        "content": PARSE_PROMPT + content,
                    }
                ],
                max_tokens=3000,
                temperature=0.1,
            )

            raw_text = response.choices[0].message.content.strip()
            return self._extract_json(raw_text, source_url)

        except Exception as e:
            self.log.error("discovery.groq_error", error=str(e))
            return []

    async def _parse_with_anthropic(
        self, content: str, source_url: str
    ) -> list[dict]:
        """Anthropic (Claude) 로 파싱 (폴백)."""
        if not self.config.anthropic_key:
            self.log.warning("discovery.no_anthropic_key")
            return []

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.config.anthropic_key)

            response = client.messages.create(
                model=self.config.llm_model_fast,
                max_tokens=3000,
                messages=[
                    {
                        "role": "user",
                        "content": PARSE_PROMPT + content,
                    }
                ],
            )

            raw_text = response.content[0].text.strip()
            return self._extract_json(raw_text, source_url)

        except Exception as e:
            self.log.error("discovery.anthropic_error", error=str(e))
            return []

    def _extract_json(self, raw_text: str, source_url: str) -> list[dict]:
        """LLM 응답에서 JSON 배열 추출 (강화됨)."""
        try:
            text = raw_text

            # markdown 코드블록 추출
            if "```" in text:
                blocks = text.split("```")
                for block in blocks[1:]:
                    cleaned = block
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:]
                    cleaned = cleaned.strip()
                    if cleaned.startswith("["):
                        text = cleaned
                        break

            # JSON 배열 시작점 찾기
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1 and end > start:
                text = text[start:end + 1]

            opportunities = json.loads(text)

            if not isinstance(opportunities, list):
                return []

            # source_url 추가 + 유효성 검사
            valid: list[dict] = []
            for opp in opportunities:
                if not isinstance(opp, dict):
                    continue
                if not opp.get("organization") or not opp.get("program"):
                    continue
                opp["source_url"] = source_url
                # apply_url 검증: "example.com" 같은 가짜 URL 제거
                apply = opp.get("apply_url", "")
                if apply and ("example.com" in apply or not apply.startswith("http")):
                    opp["apply_url"] = None
                valid.append(opp)

            self.log.info(
                "discovery.parsed",
                url=source_url,
                count=len(valid),
            )
            return valid

        except (json.JSONDecodeError, IndexError) as e:
            self.log.warning("discovery.parse_error", error=str(e), raw=raw_text[:200])
            return []
