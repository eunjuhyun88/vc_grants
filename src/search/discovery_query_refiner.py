"""
Funding Intelligence Agent — DiscoveryQueryRefiner.

autoresearch 패턴의 "쿼리 자기수정" 단계.
gap 분석 결과 → 새로운 검색 쿼리 생성.

1차: LLM (Fast model)으로 gap 기반 쿼리 생성
폴백: 템플릿 기반 쿼리 생성
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

import structlog

from src.core.config import Config

if TYPE_CHECKING:
    from src.search.types import DiscoveryContext

logger = structlog.get_logger()

# 라운드당 최대 쿼리 수 — 공격적 탐색
MAX_QUERIES_PER_ROUND = 12

# ============================================================
# LLM 프롬프트
# ============================================================

REFINE_PROMPT = """You are a funding discovery search agent.

CONTEXT:
- Company: {company_name}
- Sectors: {sectors}
- Target Ecosystems: {ecosystems}
- Already found {total_opps} opportunities from {org_count} organizations.
- Already searched with: {previous_queries}

GAPS IDENTIFIED:
{gap_reasons}

KNOWN ORGANIZATIONS (do NOT search for these again):
{known_orgs}

Generate {num_queries} NEW search queries to fill these gaps.
Each query should be 5-10 words, specific, and include action words like "apply", "open", "2026".

RULES:
1. DO NOT generate queries similar to previous ones
2. Target the specific gaps identified above
3. Include the missing ecosystems/categories explicitly
4. Use year "2026" in at least half the queries
5. For missing ecosystems, search for "[ecosystem] grants" and "[ecosystem] accelerator program"
6. For underrepresented categories, try different angles

Return ONLY a JSON array of strings:
["query 1", "query 2", ...]
"""

# ============================================================
# 템플릿 폴백
# ============================================================

CATEGORY_TEMPLATES: dict[str, list[str]] = {
    "grant": [
        "{eco} grant program apply 2026",
        "{sector} grants open deadline 2026",
        "new {eco} developer grants funding",
        "blockchain {sector} grant application open now",
        "web3 grants for {sector} startups 2026",
    ],
    "accelerator": [
        "{eco} accelerator cohort 2026 apply",
        "{sector} startup accelerator program open",
        "web3 {eco} incubator application deadline",
        "crypto accelerator batch 2026 application",
        "{sector} {eco} accelerator program cohort",
    ],
    "vc_cohort": [
        "{eco} VC cohort seed funding 2026",
        "{sector} venture fund open application",
        "crypto VC accelerator cohort {eco} apply",
        "web3 venture capital cohort program 2026",
        "{eco} seed investment program open application",
    ],
    "ecosystem_builder": [
        "{eco} ecosystem builder program 2026",
        "{sector} protocol builder program apply",
        "{eco} developer support program open",
    ],
    "builder_program": [
        "{eco} builder program application 2026",
        "{sector} developer builder program grants",
        "web3 {eco} builder residency program open",
    ],
    "hackathon_pipeline": [
        "{eco} hackathon grants funding pipeline 2026",
        "{sector} hackathon to funding program",
        "blockchain {eco} hackathon investment track",
    ],
    "fund": [
        "{eco} fund open application 2026",
        "{sector} crypto investment fund apply",
        "web3 {eco} venture fund portfolio apply",
    ],
}

DIVERSITY_TEMPLATES = [
    "new {sector} funding program 2026 apply",
    "{sector} emerging grants program open",
    "new crypto {eco} builder funding apply 2026",
]

APPLY_URL_TEMPLATES = [
    "{eco} grants application form 2026",
    "{sector} accelerator program apply now",
    "how to apply {eco} grants 2026",
]


class DiscoveryQueryRefiner:
    """Discovery loop 쿼리 자기수정 엔진.

    autoresearch의 "train.py 수정" 에 해당.
    이전 실험 결과(gap)를 보고 다음 실험(쿼리)을 설계한다.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._log = logger.bind(component="discovery_query_refiner")
        self._llm_cooldown_until = 0.0

    async def refine_queries(
        self,
        ctx: DiscoveryContext,
        gaps: list[str],
    ) -> list[str]:
        """gap 기반 새 검색 쿼리 생성.

        Args:
            ctx: DiscoveryContext — 누적 상태
            gaps: DiscoveryEvaluator가 식별한 gap 리스트

        Returns:
            새 검색 쿼리 리스트 (최대 MAX_QUERIES_PER_ROUND개)
        """
        if not gaps:
            return []

        # 이전 라운드에서 사용한 모든 쿼리 수집
        previous_queries = self._collect_previous_queries(ctx)

        # 1차: LLM 시도
        if self._config.groq_key and not self._llm_rate_limited:
            queries = await self._refine_with_llm(ctx, gaps, previous_queries)
            if queries:
                deduped = self._dedup_against_previous(
                    queries, previous_queries
                )
                if deduped:
                    self._log.info(
                        "discovery.refine.llm",
                        generated=len(queries),
                        after_dedup=len(deduped),
                    )
                    return deduped[:MAX_QUERIES_PER_ROUND]

        # 폴백: 템플릿 기반
        queries = self._template_fallback(ctx, gaps)
        deduped = self._dedup_against_previous(queries, previous_queries)

        self._log.info(
            "discovery.refine.template_fallback",
            generated=len(queries),
            after_dedup=len(deduped),
        )

        return deduped[:MAX_QUERIES_PER_ROUND]

    # ============================================================
    # LLM 기반 쿼리 생성
    # ============================================================

    async def _refine_with_llm(
        self,
        ctx: DiscoveryContext,
        gaps: list[str],
        previous_queries: set[str],
    ) -> list[str]:
        """Fast LLM으로 gap 기반 쿼리 생성."""
        try:
            from groq import Groq

            client = Groq(api_key=self._config.groq_key)

            # 프로필 정보
            sectors = ", ".join(ctx.profile.sector_tags[:5])
            ecosystems = ", ".join(ctx.profile.target_ecosystems or [])
            known_orgs = ", ".join(list(ctx.known_org_names)[:15])
            prev_q_str = "; ".join(list(previous_queries)[:10])

            prompt = REFINE_PROMPT.format(
                company_name=ctx.profile.company_name,
                sectors=sectors,
                ecosystems=ecosystems,
                total_opps=len(ctx.all_raw_opps),
                org_count=len(ctx.known_org_names),
                previous_queries=prev_q_str or "none",
                gap_reasons="\n".join(f"- {g}" for g in gaps),
                known_orgs=known_orgs or "none",
                num_queries=min(MAX_QUERIES_PER_ROUND, len(gaps) * 2),
            )

            response = client.chat.completions.create(
                model=self._config.llm_model_fast,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.4,
            )

            raw = response.choices[0].message.content.strip()
            return self._extract_query_list(raw)

        except Exception as e:
            self._log.warning(
                "discovery.refine.llm_error", error=str(e)
            )
            if _is_quota_error(e):
                self._llm_cooldown_until = time.monotonic() + 300
            return []

    # ============================================================
    # 템플릿 폴백
    # ============================================================

    def _template_fallback(
        self,
        ctx: DiscoveryContext,
        gaps: list[str],
    ) -> list[str]:
        """gap 유형별 템플릿으로 쿼리 생성."""
        queries: list[str] = []

        # 기본 변수
        sectors = ctx.profile.sector_tags[:3]
        ecosystems = ctx.profile.target_ecosystems or []
        default_sector = sectors[0].replace("_", " ") if sectors else "crypto"
        default_eco = ecosystems[0] if ecosystems else "ethereum"

        for gap in gaps:
            if gap.startswith("underrepresented_category:"):
                # "underrepresented_category:vc_cohort:found=0"
                parts = gap.split(":")
                cat = parts[1] if len(parts) > 1 else "grant"
                templates = CATEGORY_TEMPLATES.get(cat, [])

                for tmpl in templates[:2]:
                    queries.append(tmpl.format(
                        eco=default_eco,
                        sector=default_sector,
                    ))

            elif gap.startswith("missing_ecosystems:"):
                # "missing_ecosystems:monad,bittensor"
                missing_str = gap.split(":", 1)[1] if ":" in gap else ""
                missing_ecos = [
                    e.strip() for e in missing_str.split(",") if e.strip()
                ]
                for eco in missing_ecos[:3]:
                    queries.append(
                        f"{eco} grants funding program open 2026"
                    )
                    queries.append(
                        f"{eco} accelerator builder program apply"
                    )

            elif gap.startswith("low_org_diversity"):
                for tmpl in DIVERSITY_TEMPLATES[:2]:
                    queries.append(tmpl.format(
                        sector=default_sector,
                        eco=default_eco,
                    ))

            elif gap.startswith("low_apply_urls"):
                for tmpl in APPLY_URL_TEMPLATES[:2]:
                    queries.append(tmpl.format(
                        sector=default_sector,
                        eco=default_eco,
                    ))

        return queries

    # ============================================================
    # 유틸리티
    # ============================================================

    @property
    def _llm_rate_limited(self) -> bool:
        return time.monotonic() < self._llm_cooldown_until

    @staticmethod
    def _collect_previous_queries(ctx: DiscoveryContext) -> set[str]:
        """이전 라운드에서 사용한 모든 쿼리 수집."""
        previous: set[str] = set()
        for rd in ctx.rounds:
            for q in rd.queries_used:
                previous.add(q.lower().strip())
        return previous

    @staticmethod
    def _dedup_against_previous(
        queries: list[str],
        previous: set[str],
    ) -> list[str]:
        """이전 쿼리와 중복되는 것 제거."""
        result: list[str] = []
        seen: set[str] = set()

        for q in queries:
            q_lower = q.lower().strip()
            if q_lower not in previous and q_lower not in seen:
                seen.add(q_lower)
                result.append(q)

        return result


def _is_quota_error(error: Exception) -> bool:
    text = str(error).lower()
    return (
        "rate limit" in text
        or "rate_limit_exceeded" in text
        or "quota" in text
        or "tokens per day" in text
    )

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
                return [
                    q.strip() for q in queries
                    if isinstance(q, str) and q.strip()
                ]

        except (json.JSONDecodeError, IndexError):
            pass

        return []
