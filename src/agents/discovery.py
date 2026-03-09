"""
Funding Intelligence Agent — Discovery Agent.

Tavily API 검색 → httpx fetch → Claude Haiku parse.
사실만 추출, deadline 추측 금지.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from bs4 import BeautifulSoup

from src.agents.base_agent import BaseAgent
from src.core.errors import DiscoveryError
from src.core.types import (
    AgentResult,
    DiscoveryInput,
    DiscoveryOutput,
    ProgramCategory,
)

logger = structlog.get_logger()

# ============================================================
# 카테고리별 검색 쿼리 템플릿
# ============================================================
CATEGORY_QUERIES: dict[str, list[str]] = {
    "grant": [
        "{query} crypto blockchain grant program 2026",
        "{query} web3 grant funding application open",
    ],
    "accelerator": [
        "{query} crypto blockchain accelerator program 2026",
        "{query} web3 accelerator cohort application",
    ],
    "vc_cohort": [
        "{query} crypto VC cohort seed investment program",
        "{query} blockchain venture fund open application",
    ],
    "ecosystem_builder": [
        "{query} ecosystem builder program crypto blockchain",
        "{query} developer support program web3 grant",
    ],
}


# ============================================================
# LLM 프롬프트
# ============================================================
PARSE_PROMPT = """You are a data extraction agent. Extract funding opportunities from the webpage content below.

RULES (STRICT):
- Extract ONLY explicitly stated facts
- NEVER guess or infer deadlines — if not explicitly stated, set deadline to null
- NEVER fabricate URLs — if no application URL is found, set apply_url to null
- Extract the EXACT budget/funding amount as written
- If status is not explicitly stated, set to "unknown"

For each opportunity found, return a JSON array of objects with these fields:
{
  "organization": "Name of the funding organization",
  "program": "Name of the specific program",
  "category": "One of: grant, accelerator, vc_cohort, ecosystem_builder",
  "status": "One of: open, rolling, deadline, upcoming, closed, unknown",
  "deadline": "YYYY-MM-DD or null if not explicitly stated",
  "budget": "Exact text as stated (e.g., '$50K-$500K') or null",
  "apply_url": "Direct application URL or null",
  "description": "One sentence summary"
}

Return ONLY a valid JSON array. If no opportunities found, return [].

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

        self.log.info("discovery.start", query=query, category=category)

        # 1. 검색 (Tavily API 또는 직접 URL)
        urls = await self._search(query, category, sources)

        if not urls:
            return AgentResult(
                success=True,
                data=DiscoveryOutput(
                    raw_opportunities=[],
                    source_urls=[],
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                ).__dict__,
            )

        # 2. URL fetch + parse
        all_opportunities: list[dict] = []
        fetched_urls: list[str] = []

        for url in urls[:10]:  # 최대 10개 URL
            try:
                content = await self._fetch_page(url)
                if content:
                    opportunities = await self._parse_opportunities(content, url)
                    all_opportunities.extend(opportunities)
                    fetched_urls.append(url)
            except Exception as e:
                self.log.warning("discovery.fetch_failed", url=url, error=str(e))
                continue  # 개별 URL 실패 시 skip

        output = DiscoveryOutput(
            raw_opportunities=all_opportunities,
            source_urls=fetched_urls,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

        self.log.info(
            "discovery.complete",
            total_urls=len(fetched_urls),
            total_opportunities=len(all_opportunities),
        )

        return AgentResult(success=True, data=output.__dict__)

    async def _search(
        self,
        query: str,
        category: ProgramCategory | None,
        sources: list[str],
    ) -> list[str]:
        """Tavily API로 검색 → URL 목록 반환."""
        # 직접 URL이 주어진 경우
        if sources:
            return sources

        # Tavily API 검색
        if not self.config.tavily_key:
            self.log.warning("discovery.no_tavily_key")
            return []

        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=self.config.tavily_key)

            # 카테고리별 쿼리 구성
            cat_key = category.value if category else "grant"
            queries = CATEGORY_QUERIES.get(cat_key, CATEGORY_QUERIES["grant"])
            search_query = queries[0].format(query=query)

            response = client.search(
                query=search_query,
                max_results=5,
                search_depth="advanced",
            )

            urls = [r["url"] for r in response.get("results", [])]
            self.log.info("discovery.search_done", urls_found=len(urls))
            return urls

        except Exception as e:
            self.log.error("discovery.search_error", error=str(e))
            return []

    async def _fetch_page(self, url: str) -> str | None:
        """URL에서 텍스트 콘텐츠 추출."""
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={"User-Agent": "FundingBot/1.0"},
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "lxml")

            # 불필요한 태그 제거
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)

            # 너무 긴 경우 잘라냄 (LLM 컨텍스트 제한)
            if len(text) > 8000:
                text = text[:8000]

            return text if len(text) > 100 else None

        except Exception as e:
            self.log.warning("discovery.fetch_error", url=url, error=str(e))
            return None

    async def _parse_opportunities(
        self, content: str, source_url: str
    ) -> list[dict]:
        """LLM (Claude Haiku)으로 페이지 콘텐츠에서 기회 추출."""
        if not self.config.anthropic_key:
            self.log.warning("discovery.no_anthropic_key")
            return []

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.config.anthropic_key)

            response = client.messages.create(
                model=self.config.llm_model_fast,
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": PARSE_PROMPT + content,
                    }
                ],
            )

            # 응답에서 JSON 추출
            raw_text = response.content[0].text.strip()
            # JSON 배열 추출 (markdown 코드블록 안에 있을 수 있음)
            if "```" in raw_text:
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()

            opportunities = json.loads(raw_text)

            if not isinstance(opportunities, list):
                return []

            # source_url 추가
            for opp in opportunities:
                opp["source_url"] = source_url

            self.log.info(
                "discovery.parsed",
                url=source_url,
                count=len(opportunities),
            )
            return opportunities

        except (json.JSONDecodeError, IndexError) as e:
            self.log.warning("discovery.parse_error", error=str(e))
            return []
        except Exception as e:
            self.log.error("discovery.llm_error", error=str(e))
            return []
