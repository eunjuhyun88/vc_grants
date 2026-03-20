"""
Query Planner — LLM 쿼리 분해/확장 + 템플릿 폴백.

1차: Fast LLM으로 쿼리 분해 (4-6 sub-queries)
폴백: 카테고리별 템플릿 쿼리 (LLM 실패 시)
리파인: 기존 결과 갭 기반 보완 쿼리 생성 (2-3 queries)
"""

from __future__ import annotations

import json
import re
import time

import structlog

from src.core.config import Config
from src.search.types import ExtractedOpportunity

logger = structlog.get_logger()

# ============================================================
# 카테고리별 템플릿 쿼리 (폴백용)
# ============================================================

TEMPLATE_QUERIES: dict[str, list[str]] = {
    "grant": [
        "{query} grant program apply 2026",
        "{query} crypto web3 grants open applications",
        "{query} blockchain grant funding deadline",
        "{query} ecosystem grants developer funding",
    ],
    "accelerator": [
        "{query} accelerator program apply 2026",
        "{query} crypto web3 accelerator cohort open",
        "{query} startup accelerator blockchain application",
        "{query} web3 incubator program deadline",
    ],
    "vc_cohort": [
        "{query} VC cohort seed funding apply 2026",
        "{query} crypto venture fund open application",
        "{query} web3 seed round investment program",
        "{query} blockchain venture capital emerging",
    ],
    "ecosystem_builder": [
        "{query} ecosystem builder program apply",
        "{query} developer program web3 grants 2026",
        "{query} blockchain ecosystem support funding",
        "{query} protocol builder program application",
    ],
}

# 범용 쿼리 (카테고리 없을 때)
GENERIC_QUERIES = [
    "{query} grant program apply 2026",
    "{query} accelerator program open application",
    "{query} web3 crypto funding opportunities",
    "{query} blockchain ecosystem grants deadline",
]

# LLM 쿼리 분해 프롬프트
QUERY_DECOMPOSE_PROMPT = """You are a search query planner for finding crypto/web3 funding opportunities.

Given the user's search intent, decompose it into 4-6 specific search queries that will cover different aspects.

RULES:
1. Each query should be 5-8 words maximum
2. Include year "2026" in at least 2 queries
3. Use different angles: grants, accelerators, ecosystem programs, VC cohorts
4. Include action words: "apply", "application", "deadline", "open"
5. If a specific ecosystem is mentioned (e.g., "Ethereum", "Solana"), include it in most queries

USER INTENT: {query}
CATEGORY FOCUS: {category}

Return ONLY a JSON array of strings, no other text:
["query 1", "query 2", "query 3", "query 4"]
"""

# LLM 리파인 프롬프트
QUERY_REFINE_PROMPT = """You are a search query planner refining your search for crypto/web3 funding.

Previous search found {found_count} opportunities but has gaps:
{gap_reasons}

Already covered organizations: {covered_orgs}

Generate 2-3 NEW search queries to fill these gaps. Avoid searching for already-found organizations.

Return ONLY a JSON array of strings:
["query 1", "query 2", "query 3"]
"""


class QueryPlanner:
    """쿼리 분해 + 확장 + 리파인."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._llm_cooldown_until = 0.0

    async def plan(
        self,
        query: str,
        category: str | None = None,
    ) -> list[str]:
        """초기 쿼리 분해 → 4-6 sub-queries.

        1차: Fast LLM으로 분해
        폴백: 카테고리별 템플릿
        """
        # LLM 분해 시도
        if self._config.groq_key and not self._llm_rate_limited:
            llm_queries = await self._decompose_with_llm(query, category)
            if llm_queries:
                logger.info(
                    "search.query_planner.llm_plan",
                    query=query[:40],
                    sub_queries=len(llm_queries),
                )
                return llm_queries

        # 템플릿 폴백
        return self._template_fallback(query, category)

    async def refine(
        self,
        query: str,
        existing_opportunities: list[ExtractedOpportunity],
        gap_reasons: list[str],
    ) -> list[str]:
        """기존 결과 기반 보완 쿼리 생성 (2-3 queries).

        이미 찾은 조직은 제외하고, 갭을 채우는 쿼리 생성.
        """
        covered_orgs = list({
            o.organization for o in existing_opportunities
            if o.organization
        })[:20]  # 최대 20개만 표시

        # LLM 리파인 시도
        if self._config.groq_key and not self._llm_rate_limited:
            refined = await self._refine_with_llm(
                query, len(existing_opportunities),
                gap_reasons, covered_orgs,
            )
            if refined:
                logger.info(
                    "search.query_planner.llm_refine",
                    query=query[:40],
                    refined_queries=len(refined),
                )
                return refined

        # 단순 폴백: 카테고리 교차 쿼리
        return self._refine_fallback(query, covered_orgs)

    def _template_fallback(
        self, query: str, category: str | None
    ) -> list[str]:
        """카테고리별 템플릿 쿼리 생성."""
        cat_key = category or "grant"
        templates = TEMPLATE_QUERIES.get(cat_key, GENERIC_QUERIES)
        queries = [t.format(query=query) for t in templates]
        logger.info(
            "search.query_planner.template_fallback",
            query=query[:40],
            sub_queries=len(queries),
        )
        return queries

    def _refine_fallback(
        self, query: str, covered_orgs: list[str]
    ) -> list[str]:
        """리파인 폴백: 다른 카테고리로 교차 검색."""
        exclude = " ".join(f"-{org}" for org in covered_orgs[:5])
        return [
            f"{query} new grants funding 2026 {exclude}".strip(),
            f"{query} ecosystem builder program open apply",
        ]

    async def _decompose_with_llm(
        self, query: str, category: str | None
    ) -> list[str]:
        """Fast LLM (8b)으로 쿼리 분해."""
        try:
            from groq import Groq

            client = Groq(api_key=self._config.groq_key)

            prompt = QUERY_DECOMPOSE_PROMPT.format(
                query=query,
                category=category or "all funding types",
            )

            response = client.chat.completions.create(
                model=self._config.llm_model_fast,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3,
            )

            raw = response.choices[0].message.content.strip()
            return self._extract_query_list(raw)

        except Exception as e:
            logger.warning("search.query_planner.llm_error", error=str(e))
            if _is_quota_error(e):
                self._llm_cooldown_until = time.monotonic() + 300
            return []

    async def _refine_with_llm(
        self,
        query: str,
        found_count: int,
        gap_reasons: list[str],
        covered_orgs: list[str],
    ) -> list[str]:
        """Fast LLM (8b)으로 보완 쿼리 생성."""
        try:
            from groq import Groq

            client = Groq(api_key=self._config.groq_key)

            prompt = QUERY_REFINE_PROMPT.format(
                found_count=found_count,
                gap_reasons=", ".join(gap_reasons) if gap_reasons else "insufficient results",
                covered_orgs=", ".join(covered_orgs[:10]) if covered_orgs else "none",
            )

            response = client.chat.completions.create(
                model=self._config.llm_model_fast,
                messages=[
                    {"role": "system", "content": f"Original query: {query}"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=300,
                temperature=0.3,
            )

            raw = response.choices[0].message.content.strip()
            return self._extract_query_list(raw)

        except Exception as e:
            logger.warning("search.query_planner.refine_llm_error", error=str(e))
            if _is_quota_error(e):
                self._llm_cooldown_until = time.monotonic() + 300
            return []

    @property
    def _llm_rate_limited(self) -> bool:
        return time.monotonic() < self._llm_cooldown_until

    @staticmethod
    def _extract_query_list(raw_text: str) -> list[str]:
        """LLM 응답에서 JSON 문자열 배열 추출."""
        try:
            text = raw_text
            # markdown 코드블록 제거
            if "```" in text:
                blocks = text.split("```")
                for block in blocks[1:]:
                    cleaned = block.strip()
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:].strip()
                    if cleaned.startswith("["):
                        text = cleaned
                        break

            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1 and end > start:
                text = text[start:end + 1]

            queries = json.loads(text)
            if isinstance(queries, list):
                return [q.strip() for q in queries if isinstance(q, str) and q.strip()]

        except (json.JSONDecodeError, IndexError):
            pass

        return []


def _is_quota_error(error: Exception) -> bool:
    text = str(error).lower()
    return (
        "rate limit" in text
        or "rate_limit_exceeded" in text
        or "quota" in text
        or "tokens per day" in text
    )
