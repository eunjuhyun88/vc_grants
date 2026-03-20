"""
Funding Intelligence Agent — FundingSearchOrchestrator.

autoresearch 패턴 적용: 자기수정 Discovery Loop.

흐름:
  Round 0 (Seed):
    1. ProfileQueryPlanner → 쿼리 생성
    2. 3개 소스 병렬 검색 (asyncio.gather: web + social + reference)
    3. 결과 합치기 + 중복 제거
    4. known sets 초기화

  Round 1+ (Discovery Loop):
    1. DiscoveryEvaluator → gap 분석
    2. gap 없으면 BREAK
    3. DiscoveryQueryRefiner → 새 쿼리 생성
    4. 쿼리 없으면 BREAK
    5. SearchOrchestrator.search() → 웹 검색
    6. known set 대비 dedup → novel만 추가
    7. new_programs == 0이면 consecutive_zero_rounds += 1
    8. should_stop이면 BREAK

  최종:
    FundingPipeline.ingest_raw_opportunity() → DB 저장
    OpportunityMatcher.match_batch() → 우선순위 정렬
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from src.agents.matching import MatchingAgent
from src.core.config import Config
from src.core.opportunity_matcher import OpportunityMatcher
from src.core.pipeline import FundingPipeline
from src.core.opportunity_verifier import OpportunityVerifier
from src.core.types import (
    CompanyProfile,
    MatchingOutput,
    normalize_url,
    extract_domain,
    normalize_org_name,
)
from src.db.entity_store import EntityStore
from src.search.discovery_evaluator import DiscoveryEvaluator
from src.search.discovery_query_refiner import DiscoveryQueryRefiner
from src.search.engines.reference_engine import ReferenceDataEngine
from src.search.engines.social_engine import SocialSearchEngine
from src.search.orchestrator import SearchOrchestrator
from src.search.profile_query_planner import generate_queries
from src.search.types import DiscoveryContext, DiscoveryRound

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
    new_discovered: int = 0
    elapsed_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
    # Discovery loop 라운드 로그 (autoresearch results.tsv 대응)
    round_log: list[dict[str, Any]] = field(default_factory=list)


# ============================================================
# Funding Search Orchestrator — Discovery Loop
# ============================================================


class FundingSearchOrchestrator:
    """프로필 기반 펀딩 검색 통합 오케스트레이터.

    autoresearch 패턴:
      Round 0 = Seed (web+social+reference 병렬)
      Round 1+ = Gap 기반 자기수정 웹 검색
    """

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
        self._opportunity_verifier = OpportunityVerifier(
            store=store,
            agent=self._pipeline.verification,
        )
        self._matching = MatchingAgent(store=store, config=config)
        self._opportunity_matcher = OpportunityMatcher(
            store=store,
            agent=self._matching,
        )
        self._evaluator = DiscoveryEvaluator()
        self._refiner = DiscoveryQueryRefiner(config)
        self._log = logger.bind(component="funding_orchestrator")

    async def search_for_project(
        self,
        profile: CompanyProfile,
        intent: str = "default",
        top_n: int = 15,
        mode: str = "fast",
        search_hints: list[str] | None = None,
        bootstrap_terms: list[str] | None = None,
    ) -> FundingSearchResult:
        """프로젝트 기준 통합 펀딩 검색.

        Args:
            profile: CompanyProfile (검색 + 매칭 기준)
            intent: 랭킹 intent (default/urgent/biggest_check/ready_now/best_fit)
            top_n: 최종 반환 결과 수
            mode: "fast" (참조 데이터만, ~1초) | "deep" (웹+참조+Discovery Loop)
            search_hints: benchmark/policy loop이 추가로 주입하는 hint queries

        Returns:
            FundingSearchResult (ranked_results + 통계 + round_log)
        """
        start = time.monotonic()
        result = FundingSearchResult()

        self._log.info(
            "funding_search.start",
            company=profile.company_name,
            sectors=profile.sector_tags[:3],
            ecosystems=(profile.target_ecosystems or [])[:3],
            intent=intent,
            mode=mode,
        )

        # ── Discovery Context 초기화 ──
        ctx = DiscoveryContext(
            profile=profile,
            max_rounds=self._config.discovery_max_rounds,
            stall_threshold=self._config.discovery_stall_threshold,
        )

        # 중간 결과 참조용 (타임아웃 시 handler에서 접근 가능)
        self._partial_result = result

        if mode == "fast":
            # ══════════════════════════════════════════════
            # Fast Mode: 참조 데이터만 (즉시 응답)
            # ══════════════════════════════════════════════
            await self._execute_reference_only(
                ctx,
                result,
                search_hints=search_hints,
                bootstrap_terms=bootstrap_terms,
            )
        else:
            # ══════════════════════════════════════════════
            # Deep Mode: 전체 Discovery Loop
            # ══════════════════════════════════════════════
            await self._execute_seed_round(
                ctx,
                result,
                search_hints=search_hints,
                bootstrap_terms=bootstrap_terms,
            )

        # ══════════════════════════════════════════════
        # Discovery Loop (deep mode만)
        # ══════════════════════════════════════════════
        while mode == "deep" and not ctx.should_stop:
            # 1. gap 분석
            gaps = self._evaluator.evaluate(ctx)
            if not gaps:
                self._log.info("funding_search.discovery.no_gaps")
                break

            # 2. gap 기반 쿼리 생성
            queries = await self._refiner.refine_queries(ctx, gaps)
            if not queries:
                self._log.info("funding_search.discovery.no_queries")
                break

            # 3. 검색 라운드 실행
            new_count = await self._execute_discovery_round(
                ctx, result, queries, gaps
            )

            # 4. stall 판단 (autoresearch: new_programs == 0이면 카운트)
            if new_count == 0:
                ctx.consecutive_zero_rounds += 1
            else:
                ctx.consecutive_zero_rounds = 0

        # ══════════════════════════════════════════════
        # 최종: DB Ingest + 매칭 + 랭킹
        # ══════════════════════════════════════════════
        if ctx.all_raw_opps:
            await self._ingest_and_rank(ctx, result, profile, intent, top_n)

        result.elapsed_seconds = time.monotonic() - start

        self._log.info(
            "funding_search.complete",
            rounds=ctx.current_round,
            ranked=len(result.ranked_results),
            total_opps=len(ctx.all_raw_opps),
            elapsed_s=round(result.elapsed_seconds, 1),
            errors=len(result.errors),
        )

        return result

    # ============================================================
    # Fast Mode: Reference Data Only
    # ============================================================

    async def _execute_reference_only(
        self,
        ctx: DiscoveryContext,
        result: FundingSearchResult,
        search_hints: list[str] | None = None,
        bootstrap_terms: list[str] | None = None,
    ) -> None:
        """Fast mode: 참조 데이터만으로 즉시 매칭 (~1초)."""
        round_start = time.monotonic()
        priority_terms = _merge_seed_queries(
            list(bootstrap_terms or []),
            list(search_hints or []),
        )

        ref_opps = await asyncio.to_thread(
            self._search_reference, ctx.profile, priority_terms
        )

        result.reference_count = len(ref_opps)
        result.total_raw = len(ref_opps)

        deduped = _dedup_opportunities(ref_opps)
        result.total_deduped = len(deduped)

        ctx.all_raw_opps.extend(deduped)
        self._update_known_sets(ctx, deduped)

        elapsed = time.monotonic() - round_start

        rd = DiscoveryRound(
            round_number=0,
            queries_used=[],
            source_type="reference",
            raw_found=len(ref_opps),
            after_dedup=len(deduped),
            new_programs=len(ctx.known_program_keys),
            elapsed_seconds=elapsed,
        )
        ctx.rounds.append(rd)

        result.round_log.append({
            "round": 0,
            "source": "reference",
            "raw": len(ref_opps),
            "new_progs": len(ctx.known_program_keys),
            "elapsed_s": round(elapsed, 1),
        })

        self._log.info(
            "funding_search.fast.complete",
            reference=len(ref_opps),
            deduped=len(deduped),
            priority_terms=len(priority_terms),
            elapsed_s=round(elapsed, 1),
        )

    # ============================================================
    # Round 0: Seed Round (deep mode)
    # ============================================================

    async def _execute_seed_round(
        self,
        ctx: DiscoveryContext,
        result: FundingSearchResult,
        search_hints: list[str] | None = None,
        bootstrap_terms: list[str] | None = None,
    ) -> None:
        """Round 0: 기존 3-source 병렬 검색 (하위호환)."""
        round_start = time.monotonic()

        # 쿼리 생성
        queries = _merge_seed_queries(generate_queries(ctx.profile), search_hints)
        bootstrap_sources = self._reference_engine.bootstrap_sources(
            ctx.profile,
            top_n=10,
            priority_terms=bootstrap_terms,
        )
        self._log.info(
            "funding_search.seed.queries",
            count=len(queries),
            hint_count=len(search_hints or []),
            bootstrap_sources=len(bootstrap_sources),
        )

        # 3개 소스 병렬 검색
        web_task = self._search_web(queries)
        social_task = self._search_social(ctx.profile)
        ref_task = asyncio.to_thread(self._search_reference, ctx.profile)
        bootstrap_task = self._search_bootstrap_sources(bootstrap_sources)

        web_results, social_results, ref_results, bootstrap_results = await asyncio.gather(
            web_task, social_task, ref_task, bootstrap_task,
            return_exceptions=True,
        )

        # 에러 처리 + 결과 수집
        web_opps = self._safe_extract(web_results, "web", result)
        social_opps = self._safe_extract(social_results, "social", result)
        ref_opps = self._safe_extract(ref_results, "reference", result)
        bootstrap_opps = self._safe_extract(bootstrap_results, "bootstrap", result)

        result.web_count = len(web_opps) + len(bootstrap_opps)
        result.social_count = len(social_opps)
        result.reference_count = len(ref_opps)

        # 합치기 + 중복 제거
        all_opps = web_opps + bootstrap_opps + social_opps + ref_opps
        result.total_raw = len(all_opps)

        deduped = _dedup_opportunities(all_opps)
        result.total_deduped = len(deduped)

        # known sets 초기화
        ctx.all_raw_opps.extend(deduped)
        self._update_known_sets(ctx, deduped)

        elapsed = time.monotonic() - round_start

        # 라운드 기록
        rd = DiscoveryRound(
            round_number=0,
            queries_used=queries,
            source_type="mixed",
            raw_found=len(all_opps),
            after_dedup=len(deduped),
            new_programs=len(ctx.known_program_keys),
            elapsed_seconds=elapsed,
        )
        ctx.rounds.append(rd)

        # 라운드 로그 (autoresearch results.tsv 대응)
        result.round_log.append({
            "round": 0,
            "source": "mixed",
            "queries": len(queries),
            "raw": len(all_opps),
            "new_progs": len(ctx.known_program_keys),
            "cumulative": len(ctx.all_raw_opps),
            "gaps": [],
            "elapsed_s": round(elapsed, 1),
        })

        self._log.info(
            "funding_search.seed.complete",
            web=len(web_opps),
            bootstrap=len(bootstrap_opps),
            social=len(social_opps),
            reference=len(ref_opps),
            raw=len(all_opps),
            deduped=len(deduped),
            known_programs=len(ctx.known_program_keys),
            elapsed_s=round(elapsed, 1),
        )

    # ============================================================
    # Round 1+: Discovery Round
    # ============================================================

    async def _execute_discovery_round(
        self,
        ctx: DiscoveryContext,
        result: FundingSearchResult,
        queries: list[str],
        gaps: list[str],
    ) -> int:
        """Discovery loop 단일 라운드.

        Returns:
            이번 라운드에서 새로 발견한 프로그램 수.
        """
        round_start = time.monotonic()
        round_num = ctx.current_round  # rounds에 append 전이므로 현재 인덱스

        self._log.info(
            "funding_search.discovery.round_start",
            round=round_num,
            queries=len(queries),
            gaps=gaps[:3],
        )

        # 웹 검색 (SearchOrchestrator 블랙박스 재사용)
        web_opps = await self._search_web(queries)

        # source_type 태그
        for opp in web_opps:
            opp.setdefault("source_type", "web")

        # known set 대비 dedup → novel만 추출
        novel_opps = self._dedup_against_known(ctx, web_opps)
        new_programs = self._count_novel_programs(ctx, novel_opps)

        # novel 결과 누적
        ctx.all_raw_opps.extend(novel_opps)
        self._update_known_sets(ctx, novel_opps)

        elapsed = time.monotonic() - round_start

        # 라운드 기록
        rd = DiscoveryRound(
            round_number=round_num,
            queries_used=queries,
            source_type="web",
            raw_found=len(web_opps),
            after_dedup=len(novel_opps),
            new_programs=new_programs,
            elapsed_seconds=elapsed,
            gap_reasons=gaps,
        )
        ctx.rounds.append(rd)

        # 라운드 로그
        result.round_log.append({
            "round": round_num,
            "source": "web",
            "queries": len(queries),
            "raw": len(web_opps),
            "new_progs": new_programs,
            "cumulative": len(ctx.all_raw_opps),
            "gaps": gaps[:3],
            "elapsed_s": round(elapsed, 1),
        })

        self._log.info(
            "funding_search.discovery.round_complete",
            round=round_num,
            raw=len(web_opps),
            novel=len(novel_opps),
            new_programs=new_programs,
            cumulative=len(ctx.all_raw_opps),
            elapsed_s=round(elapsed, 1),
        )

        return new_programs

    # ============================================================
    # DB Ingest + 매칭
    # ============================================================

    async def _ingest_and_rank(
        self,
        ctx: DiscoveryContext,
        result: FundingSearchResult,
        profile: CompanyProfile,
        intent: str,
        top_n: int,
    ) -> None:
        """발견된 모든 기회를 DB에 저장하고 매칭 순위를 매긴다."""
        # 기존 DB 프로그램 수 (NEW 판별용)
        existing_count_before = await self._count_existing_programs()

        ingested_ids: list[str] = []
        for raw_opp in ctx.all_raw_opps:
            try:
                opp_id = await self._pipeline.ingest_raw_opportunity(raw_opp)
                if opp_id:
                    ingested_ids.append(opp_id)
            except Exception as e:
                result.errors.append(
                    f"Ingest error: {raw_opp.get('program', '?')}: {e}"
                )

        result.total_ingested = len(ingested_ids)
        ctx.ingested_opp_ids = ingested_ids

        existing_count_after = await self._count_existing_programs()
        result.new_discovered = max(
            0, existing_count_after - existing_count_before
        )

        self._log.info(
            "funding_search.ingested",
            ingested=result.total_ingested,
            new_discovered=result.new_discovered,
        )

        verified_count = await self._verify_ingested_batch(ingested_ids, result)

        self._log.info(
            "funding_search.verified",
            verified=verified_count,
            ingested=result.total_ingested,
        )

        # 매칭 + 랭킹
        rankable_ids = await self._opportunity_matcher.filter_rankable_opportunity_ids(
            ingested_ids
        )

        self._log.info(
            "funding_search.rankable",
            rankable=len(rankable_ids),
            ingested=len(ingested_ids),
        )

        if rankable_ids and profile.id:
            existing_profile = await self._store.get_company_profile(
                profile.id
            )
            if existing_profile is None:
                await self._store.create_company_profile(profile)

            outcomes = await self._opportunity_matcher.match_batch(
                rankable_ids,
                profile.id,
                intent=intent,
                concurrency=1,
            )
            for outcome in outcomes:
                if outcome.error:
                    result.errors.append(
                        f"Matching error: {outcome.opportunity_id}: {outcome.error}"
                    )
            if any(outcome.error for outcome in outcomes):
                self._log.warning(
                    "funding_search.matching_partial_error",
                    errors=sum(1 for outcome in outcomes if outcome.error),
                )
            result.ranked_results = self._opportunity_matcher.rank_outputs(
                outcomes,
                top_n=top_n,
            )

    # ============================================================
    # 개별 검색 소스
    # ============================================================

    async def _search_web(self, queries: list[str]) -> list[dict]:
        """웹 검색 — 기존 SearchOrchestrator 재사용.

        OR로 긴 배치를 만드는 대신, 쿼리를 개별 실행해서 anchor recall을 높인다.
        """
        all_opps: list[dict] = []
        if not self._web_orchestrator.has_available_engines:
            return all_opps

        for i, query in enumerate(queries):
            if not self._web_orchestrator.has_available_engines:
                break
            try:
                opps, _ = await self._web_orchestrator.search(
                    query=query,
                )
                all_opps.extend(opps)
            except Exception as e:
                self._log.warning(
                    "funding_search.web_query_error",
                    query_index=i,
                    query=query,
                    error=str(e),
                )

            if len(all_opps) >= 120:
                break

        # source_type 태그
        for opp in all_opps:
            opp.setdefault("source_type", "web")

        return all_opps

    async def _search_bootstrap_sources(self, sources: list[str]) -> list[dict]:
        """reference registry 기반 공식 페이지 direct fetch."""
        if not sources:
            return []
        try:
            opps, _ = await self._web_orchestrator.search(
                query="reference bootstrap",
                sources=sources,
            )
            for opp in opps:
                opp.setdefault("source_type", "bootstrap")
            return opps
        except Exception as e:
            self._log.warning(
                "funding_search.bootstrap_error",
                error=str(e),
                sources=len(sources),
            )
            return []

    async def _search_social(self, profile: CompanyProfile) -> list[dict]:
        """소셜 검색 — SocialSearchEngine 사용."""
        try:
            return await self._social_engine.search(profile)
        except Exception as e:
            self._log.warning("funding_search.social_error", error=str(e))
            return []

    def _search_reference(
        self,
        profile: CompanyProfile,
        priority_terms: list[str] | None = None,
    ) -> list[dict]:
        """참조 데이터 검색 — ReferenceDataEngine 사용. (sync)"""
        try:
            if not self._reference_engine.loaded:
                self._reference_engine.load()

            results = self._reference_engine.search(
                profile,
                top_n=80,
                priority_terms=priority_terms,
            )
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

    async def _verify_ingested_batch(
        self,
        ingested_ids: list[str],
        result: FundingSearchResult,
    ) -> int:
        """새로 ingest한 기회들을 병렬 검증."""
        outcomes = await self._opportunity_verifier.verify_batch(
            ingested_ids,
            source_limit=5,
            concurrency=6,
        )
        verified_count = 0
        for outcome in outcomes:
            if outcome.verified:
                verified_count += 1
            if outcome.error:
                result.errors.append(
                    f"Verification error: {outcome.opportunity_id}: {outcome.error}"
                )
        return verified_count

    # ============================================================
    # Discovery Loop 헬퍼
    # ============================================================

    @staticmethod
    def _safe_extract(
        result: list[dict] | Exception,
        source: str,
        funding_result: FundingSearchResult,
    ) -> list[dict]:
        """asyncio.gather 결과에서 안전하게 추출."""
        if isinstance(result, list):
            return result
        if isinstance(result, Exception):
            funding_result.errors.append(f"{source} search error: {result}")
        return []

    @staticmethod
    def _update_known_sets(
        ctx: DiscoveryContext,
        opps: list[dict],
    ) -> None:
        """발견된 기회로 known sets 업데이트."""
        for opp in opps:
            org = (opp.get("organization") or "").lower().strip()
            prog = (opp.get("program") or "").lower().strip()
            url = opp.get("apply_url") or opp.get("source_url") or ""

            if org:
                ctx.known_org_names.add(org)
            if org and prog:
                ctx.known_program_keys.add(f"{org}::{prog}")
            if url:
                ctx.known_urls.add(normalize_url(url))

    @staticmethod
    def _dedup_against_known(
        ctx: DiscoveryContext,
        opps: list[dict],
    ) -> list[dict]:
        """known sets 대비 중복 제거 → novel만 반환."""
        novel: list[dict] = []

        for opp in opps:
            org = (opp.get("organization") or "").lower().strip()
            prog = (opp.get("program") or "").lower().strip()
            url = opp.get("apply_url") or opp.get("source_url") or ""
            url_key = normalize_url(url) if url else ""

            # URL 기반 중복 체크
            if url_key and url_key in ctx.known_urls:
                continue

            # org+program 기반 중복 체크
            prog_key = f"{org}::{prog}"
            if org and prog and prog_key in ctx.known_program_keys:
                continue

            novel.append(opp)

        return novel

    @staticmethod
    def _count_novel_programs(
        ctx: DiscoveryContext,
        opps: list[dict],
    ) -> int:
        """novel opps 중 새 프로그램 수 카운트."""
        count = 0
        for opp in opps:
            org = (opp.get("organization") or "").lower().strip()
            prog = (opp.get("program") or "").lower().strip()
            key = f"{org}::{prog}"
            if org and prog and key not in ctx.known_program_keys:
                count += 1
        return count


# ============================================================
# Dedup 로직 (Round 0 내부 dedup)
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
    by_url: dict[str, int] = {}
    by_name: dict[str, int] = {}
    by_domain: dict[str, int] = {}

    result: list[dict] = []

    SOURCE_PRIORITY = {"web": 0, "reference_data": 1, "social": 2}

    for opp in opps:
        apply_url = opp.get("apply_url", "")
        org_name = opp.get("organization", "")
        prog_name = opp.get("program", "")

        url_key = normalize_url(apply_url) if apply_url else ""
        name_key = (
            f"{normalize_org_name(org_name)}::{prog_name.lower().strip()}"
        )
        domain_key = extract_domain(apply_url) or ""

        existing_idx = None

        if url_key and url_key in by_url:
            existing_idx = by_url[url_key]
        elif name_key and name_key in by_name:
            existing_idx = by_name[name_key]
        elif domain_key and domain_key in by_domain:
            existing_idx = by_domain[domain_key]

        if existing_idx is not None:
            existing = result[existing_idx]
            _merge_opportunity(existing, opp, SOURCE_PRIORITY)
        else:
            idx = len(result)
            result.append(opp.copy())

            if url_key:
                by_url[url_key] = idx
            if name_key:
                by_name[name_key] = idx
            if domain_key:
                by_domain[domain_key] = idx

    return result


def _merge_seed_queries(
    base_queries: list[str],
    search_hints: list[str] | None = None,
) -> list[str]:
    """Base profile queries + external hint queries, dedup preserving order."""
    merged: list[str] = []
    seen: set[str] = set()

    for query in [*(base_queries or []), *(search_hints or [])]:
        normalized = query.lower().strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(query)

    return merged


def _combine_query_batch(batch: list[str]) -> str:
    """Join the full query batch for a single web-search call."""
    cleaned = [query.strip() for query in batch if query and query.strip()]
    return " OR ".join(cleaned)


def _merge_opportunity(
    existing: dict,
    new: dict,
    source_priority: dict[str, int],
) -> None:
    """두 raw_opportunity를 merge. existing을 in-place 수정."""
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
        existing_src = source_priority.get(
            existing.get("source_type", ""), 99
        )
        new_src = source_priority.get(new.get("source_type", ""), 99)
        if new_src < existing_src:
            existing["apply_url"] = new["apply_url"]

    # status: open > rolling > unknown
    STATUS_RANK = {
        "open": 0, "rolling": 1, "upcoming": 2,
        "unknown": 3, "closed": 4,
    }
    existing_rank = STATUS_RANK.get(
        existing.get("status", "unknown"), 3
    )
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
