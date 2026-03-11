"""
Funding Intelligence Agent — FundingSearchOrchestrator.

웹 + 소셜 + 참조 데이터를 병렬로 검색하고 합치는 통합 오케스트레이터.

흐름:
  1. ProfileQueryPlanner → 쿼리 생성
  2. 3개 소스 병렬 검색 (asyncio.gather)
  3. 결과 합치기 + 중복 제거
  4. FundingPipeline._ingest_raw_opportunity() → DB 저장
  5. MatchingAgent.batch_rank() → 우선순위 정렬
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from src.agents.matching import MatchingAgent
from src.core.config import Config
from src.core.pipeline import FundingPipeline
from src.core.types import CompanyProfile, MatchingOutput, normalize_url, extract_domain, normalize_org_name
from src.db.entity_store import EntityStore
from src.search.engines.reference_engine import ReferenceDataEngine
from src.search.engines.social_engine import SocialSearchEngine
from src.search.orchestrator import SearchOrchestrator
from src.search.profile_query_planner import generate_queries

logger = structlog.get_logger()


# ============================================================
# Result Container
# ============================================================

@dataclass
class FundingSearchResult:
    """통합 검색 결과."""
    ranked_results: list[MatchingOutput] = field(default_factory=list)
    web_count: int = 0
    social_count: int = 0
    reference_count: int = 0
    total_raw: int = 0
    total_deduped: int = 0
    total_ingested: int = 0
    new_discovered: int = 0      # 🆕 NEW 개수
    elapsed_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


# ============================================================
# Funding Search Orchestrator
# ============================================================


class FundingSearchOrchestrator:
    """프로필 기반 펀딩 검색 통합 오케스트레이터."""

    def __init__(
        self,
        store: EntityStore,
        config: Config,
        reference_engine: ReferenceDataEngine | None = None,
    ) -> None:
        self._store = store
        self._config = config
        self._web_orchestrator = SearchOrchestrator(config)
        self._social_engine = SocialSearchEngine(config)
        self._reference_engine = reference_engine or ReferenceDataEngine()
        self._pipeline = FundingPipeline(store=store, cfg=config)
        self._matching = MatchingAgent(store=store, config=config)
        self._log = logger.bind(component="funding_orchestrator")

    async def search_for_project(
        self,
        profile: CompanyProfile,
        intent: str = "default",
        top_n: int = 15,
    ) -> FundingSearchResult:
        """프로젝트 기준 통합 펀딩 검색.

        Args:
            profile: CompanyProfile (검색 + 매칭 기준)
            intent: 랭킹 intent (default/urgent/biggest_check/ready_now/best_fit)
            top_n: 최종 반환 결과 수

        Returns:
            FundingSearchResult (ranked_results + 통계)
        """
        start = time.monotonic()
        result = FundingSearchResult()

        self._log.info(
            "funding_search.start",
            company=profile.company_name,
            sectors=profile.sector_tags[:3],
            ecosystems=(profile.target_ecosystems or [])[:3],
            intent=intent,
        )

        # ── Step 1: 쿼리 생성 ──
        queries = generate_queries(profile)
        self._log.info("funding_search.queries_generated", count=len(queries))

        # ── Step 2: 3개 소스 병렬 검색 ──
        web_task = self._search_web(queries)
        social_task = self._search_social(profile)
        ref_task = asyncio.to_thread(self._search_reference, profile)

        web_results, social_results, ref_results = await asyncio.gather(
            web_task, social_task, ref_task,
            return_exceptions=True,
        )

        # 에러 처리
        web_opps: list[dict] = []
        if isinstance(web_results, list):
            web_opps = web_results
        elif isinstance(web_results, Exception):
            result.errors.append(f"Web search error: {web_results}")
            self._log.error("funding_search.web_error", error=str(web_results))

        social_opps: list[dict] = []
        if isinstance(social_results, list):
            social_opps = social_results
        elif isinstance(social_results, Exception):
            result.errors.append(f"Social search error: {social_results}")
            self._log.error("funding_search.social_error", error=str(social_results))

        ref_opps: list[dict] = []
        if isinstance(ref_results, list):
            ref_opps = ref_results
        elif isinstance(ref_results, Exception):
            result.errors.append(f"Reference search error: {ref_results}")
            self._log.error("funding_search.ref_error", error=str(ref_results))

        result.web_count = len(web_opps)
        result.social_count = len(social_opps)
        result.reference_count = len(ref_opps)

        # ── Step 3: 결과 합치기 + 중복 제거 ──
        all_opps = web_opps + social_opps + ref_opps
        result.total_raw = len(all_opps)

        deduped = _dedup_opportunities(all_opps)
        result.total_deduped = len(deduped)

        self._log.info(
            "funding_search.merged",
            web=result.web_count,
            social=result.social_count,
            reference=result.reference_count,
            total_raw=result.total_raw,
            deduped=result.total_deduped,
        )

        if not deduped:
            result.elapsed_seconds = time.monotonic() - start
            return result

        # ── Step 4: DB에 Ingest ──
        # 기존 DB에 있는 프로그램 수 (NEW 판별용)
        existing_count_before = await self._count_existing_programs()

        ingested_ids: list[str] = []
        for raw_opp in deduped:
            try:
                opp_id = await self._pipeline._ingest_raw_opportunity(raw_opp)
                if opp_id:
                    ingested_ids.append(opp_id)
            except Exception as e:
                result.errors.append(
                    f"Ingest error: {raw_opp.get('program', '?')}: {e}"
                )

        result.total_ingested = len(ingested_ids)

        existing_count_after = await self._count_existing_programs()
        result.new_discovered = max(0, existing_count_after - existing_count_before)

        self._log.info(
            "funding_search.ingested",
            ingested=result.total_ingested,
            new_discovered=result.new_discovered,
        )

        # ── Step 5: 매칭 + 랭킹 ──
        if ingested_ids and profile.id:
            # 프로필이 DB에 있는지 확인, 없으면 저장
            existing_profile = await self._store.get_company_profile(profile.id)
            if existing_profile is None:
                await self._store.upsert_company_profile(profile)

            try:
                ranked = await self._matching.batch_rank(
                    opportunity_ids=ingested_ids,
                    profile_id=profile.id,
                    intent=intent,
                    top_n=top_n,
                )
                result.ranked_results = ranked
            except Exception as e:
                result.errors.append(f"Matching error: {e}")
                self._log.error("funding_search.matching_error", error=str(e))

        result.elapsed_seconds = time.monotonic() - start

        self._log.info(
            "funding_search.complete",
            ranked=len(result.ranked_results),
            elapsed_s=round(result.elapsed_seconds, 1),
            errors=len(result.errors),
        )

        return result

    # ============================================================
    # 개별 검색 소스
    # ============================================================

    async def _search_web(self, queries: list[str]) -> list[dict]:
        """웹 검색 — 기존 SearchOrchestrator 재사용.

        모든 쿼리를 하나의 통합 쿼리로 묶어서 검색.
        효율성: 20개 쿼리를 5개 배치로 나눠서 실행.
        """
        all_opps: list[dict] = []
        all_sources: list[str] = []

        # 쿼리를 4개씩 배치로 나눠서 실행
        batch_size = 4
        for i in range(0, len(queries), batch_size):
            batch = queries[i:i + batch_size]
            combined_query = " OR ".join(batch[:2])  # 배치에서 2개만 OR 결합

            try:
                opps, sources = await self._web_orchestrator.search(
                    query=combined_query,
                )
                all_opps.extend(opps)
                all_sources.extend(sources)
            except Exception as e:
                self._log.warning(
                    "funding_search.web_batch_error",
                    batch=i,
                    error=str(e),
                )

            # 이미 충분한 결과가 있으면 중단
            if len(all_opps) >= 30:
                break

        self._log.info(
            "funding_search.web_done",
            opportunities=len(all_opps),
            sources=len(all_sources),
        )

        # source_type 태그 추가
        for opp in all_opps:
            opp.setdefault("source_type", "web")

        return all_opps

    async def _search_social(self, profile: CompanyProfile) -> list[dict]:
        """소셜 검색 — SocialSearchEngine 사용."""
        try:
            return await self._social_engine.search(profile)
        except Exception as e:
            self._log.warning("funding_search.social_error", error=str(e))
            return []

    def _search_reference(self, profile: CompanyProfile) -> list[dict]:
        """참조 데이터 검색 — ReferenceDataEngine 사용. (sync)"""
        try:
            if not self._reference_engine.loaded:
                self._reference_engine.load()

            results = self._reference_engine.search(profile, top_n=25)
            return self._reference_engine.to_raw_opportunities(results)
        except Exception as e:
            self._log.warning("funding_search.ref_error", error=str(e))
            return []

    async def _count_existing_programs(self) -> int:
        """DB에 있는 프로그램 수 카운트 (NEW 판별용)."""
        try:
            rows = await self._store.list_programs(limit=10000)
            return len(rows) if rows else 0
        except Exception:
            return 0


# ============================================================
# Dedup 로직
# ============================================================

def _dedup_opportunities(opps: list[dict]) -> list[dict]:
    """raw_opportunity 리스트 중복 제거.

    우선순위:
    1. apply_url 정규화 비교
    2. organization + program 정규화 비교
    3. domain 비교

    Merge 시:
    - confidence: max
    - source_tier: min (높은 티어)
    - apply_url: non-null 우선, web > reference > social 순
    - status: open > rolling > unknown
    - deadline/budget: non-null 우선
    """
    # URL 기반 인덱스
    by_url: dict[str, int] = {}
    # org+program 기반 인덱스
    by_name: dict[str, int] = {}
    # domain 기반 인덱스
    by_domain: dict[str, int] = {}

    result: list[dict] = []

    SOURCE_PRIORITY = {"web": 0, "reference_data": 1, "social": 2}

    for opp in opps:
        apply_url = opp.get("apply_url", "")
        org_name = opp.get("organization", "")
        prog_name = opp.get("program", "")

        # Key 생성
        url_key = normalize_url(apply_url) if apply_url else ""
        name_key = f"{normalize_org_name(org_name)}::{prog_name.lower().strip()}"
        domain_key = extract_domain(apply_url) or ""

        # 기존 레코드 찾기
        existing_idx = None

        if url_key and url_key in by_url:
            existing_idx = by_url[url_key]
        elif name_key and name_key in by_name:
            existing_idx = by_name[name_key]
        elif domain_key and domain_key in by_domain:
            existing_idx = by_domain[domain_key]

        if existing_idx is not None:
            # Merge
            existing = result[existing_idx]
            _merge_opportunity(existing, opp, SOURCE_PRIORITY)
        else:
            # New
            idx = len(result)
            result.append(opp.copy())

            if url_key:
                by_url[url_key] = idx
            if name_key:
                by_name[name_key] = idx
            if domain_key:
                by_domain[domain_key] = idx

    return result


def _merge_opportunity(
    existing: dict,
    new: dict,
    source_priority: dict[str, int],
) -> None:
    """두 raw_opportunity를 merge.

    existing을 in-place 수정.
    """
    # confidence: max
    existing_conf = existing.get("confidence", 0) or 0
    new_conf = new.get("confidence", 0) or 0
    existing["confidence"] = max(existing_conf, new_conf)
    existing["fact_confidence"] = max(
        existing.get("fact_confidence", 0) or 0,
        new.get("fact_confidence", 0) or 0,
    )

    # source_tier: min (높은 티어)
    existing_tier = existing.get("source_tier")
    new_tier = new.get("source_tier")
    if existing_tier is not None and new_tier is not None:
        existing["source_tier"] = min(existing_tier, new_tier)
    elif new_tier is not None:
        existing["source_tier"] = new_tier

    # apply_url: source 우선순위 기반
    if not existing.get("apply_url") and new.get("apply_url"):
        existing["apply_url"] = new["apply_url"]
    elif existing.get("apply_url") and new.get("apply_url"):
        existing_src = source_priority.get(existing.get("source_type", ""), 99)
        new_src = source_priority.get(new.get("source_type", ""), 99)
        if new_src < existing_src:
            existing["apply_url"] = new["apply_url"]

    # status: open > rolling > unknown
    STATUS_RANK = {"open": 0, "rolling": 1, "upcoming": 2, "unknown": 3, "closed": 4}
    existing_rank = STATUS_RANK.get(existing.get("status", "unknown"), 3)
    new_rank = STATUS_RANK.get(new.get("status", "unknown"), 3)
    if new_rank < existing_rank:
        existing["status"] = new["status"]

    # deadline, budget: non-null 우선
    if not existing.get("deadline") and new.get("deadline"):
        existing["deadline"] = new["deadline"]
    if not existing.get("budget") and new.get("budget"):
        existing["budget"] = new["budget"]

    # description: 더 긴 것
    existing_desc = existing.get("description", "") or ""
    new_desc = new.get("description", "") or ""
    if len(new_desc) > len(existing_desc):
        existing["description"] = new_desc

    # focus_areas: 합치기
    existing_fa = existing.get("focus_areas", []) or []
    new_fa = new.get("focus_areas", []) or []
    merged_fa = list(dict.fromkeys(existing_fa + new_fa))
    existing["focus_areas"] = merged_fa
