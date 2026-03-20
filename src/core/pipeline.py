"""
Funding Intelligence Agent — Pipeline 통합.

Discovery → Entity Resolution(Ingest) → Verification → Matching.
에러 복구: 부분 실패 허용.

실행: python -m src.core.pipeline --query "AI grants" --category grant
"""

from __future__ import annotations

import argparse
import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from src.agents.discovery import DiscoveryAgent
from src.agents.matching import MatchingAgent
from src.agents.verification import VerificationAgent
from src.core.config import Config, config
from src.core.opportunity_ingestor import OpportunityIngestor
from src.core.opportunity_matcher import OpportunityMatcher
from src.core.opportunity_verifier import OpportunityVerifier
from src.core.types import (
    DiscoveryInput,
    ProgramCategory,
    SocialMonitoringEvent,
    generate_id,
)
from src.db.entity_store import EntityStore

logger = structlog.get_logger()


# ============================================================
# Pipeline Result
# ============================================================


@dataclass
class PipelineResult:
    """파이프라인 실행 결과."""
    total_discovered: int = 0
    total_ingested: int = 0
    total_verified: int = 0
    total_matched: int = 0
    ingested_opp_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0

    @property
    def summary(self) -> str:
        """사람이 읽을 수 있는 요약."""
        lines = [
            f"=== Pipeline Result ===",
            f"  Discovered: {self.total_discovered}",
            f"  Ingested:   {self.total_ingested}",
            f"  Verified:   {self.total_verified}",
            f"  Matched:    {self.total_matched}",
            f"  Elapsed:    {self.elapsed_ms:.0f}ms",
        ]
        if self.errors:
            lines.append(f"  Errors:     {len(self.errors)}")
            for err in self.errors[:5]:
                lines.append(f"    - {err}")
        return "\n".join(lines)


# ============================================================
# FundingPipeline
# ============================================================


class FundingPipeline:
    """Discovery → Ingest → Verification → Matching 오케스트레이션."""

    def __init__(
        self,
        store: EntityStore,
        cfg: Config | None = None,
    ) -> None:
        self.store = store
        self.config = cfg or config
        self.discovery = DiscoveryAgent(store, self.config)
        self.verification = VerificationAgent(store, self.config)
        self.matching = MatchingAgent(store, self.config)
        self.ingestor = OpportunityIngestor(store)
        self.opportunity_matcher = OpportunityMatcher(store, self.matching)
        self.opportunity_verifier = OpportunityVerifier(store, self.verification)
        self.log = logger.bind(component="pipeline")

    async def run_discovery_pipeline(
        self,
        query: str,
        category: ProgramCategory | None = None,
        company_profile_id: str | None = None,
        sources: list[str] | None = None,
        hint_queries: list[str] | None = None,
    ) -> PipelineResult:
        """전체 파이프라인 실행."""
        start = time.monotonic()
        result = PipelineResult()

        self.log.info(
            "pipeline.start",
            query=query,
            category=category,
        )

        raw_opps = await self._discover_raw_opportunities(
            query=query,
            category=category,
            sources=sources or [],
            hint_queries=hint_queries or [],
            result=result,
        )
        ingested_opp_ids = await self._ingest_raw_opportunities(
            raw_opps=raw_opps,
            category=category,
            result=result,
        )
        await self._verify_ingested_opportunities(
            ingested_opp_ids=ingested_opp_ids,
            result=result,
        )

        if company_profile_id:
            await self._match_ingested_opportunities(
                ingested_opp_ids=ingested_opp_ids,
                company_profile_id=company_profile_id,
                result=result,
            )

        result.elapsed_ms = (time.monotonic() - start) * 1000
        self.log.info(
            "pipeline.complete",
            discovered=result.total_discovered,
            ingested=result.total_ingested,
            verified=result.total_verified,
            matched=result.total_matched,
            errors=len(result.errors),
            elapsed_ms=round(result.elapsed_ms, 1),
        )

        return result

    async def _discover_raw_opportunities(
        self,
        *,
        query: str,
        category: ProgramCategory | None,
        sources: list[str],
        hint_queries: list[str],
        result: PipelineResult,
    ) -> list[dict]:
        try:
            discovery_result = await self.discovery.run(
                DiscoveryInput(
                    query=query,
                    category=category,
                    sources=sources,
                    hint_queries=hint_queries,
                )
            )
        except Exception as exc:
            result.errors.append(f"Discovery error: {exc}")
            return []

        if not discovery_result.success:
            result.errors.append(f"Discovery failed: {discovery_result.error}")
            return []

        raw_opportunities = discovery_result.data.get("raw_opportunities", [])
        result.total_discovered = len(raw_opportunities)
        self.log.info("pipeline.discovery_done", count=len(raw_opportunities))
        return raw_opportunities

    async def _ingest_raw_opportunities(
        self,
        *,
        raw_opps: list[dict],
        category: ProgramCategory | None,
        result: PipelineResult,
    ) -> list[str]:
        ingested_opp_ids: list[str] = []
        for raw_opp in raw_opps:
            try:
                opp_id = await self.ingest_raw_opportunity(raw_opp, category)
                if opp_id:
                    await self._record_social_monitoring_event(raw_opp, opp_id)
                    ingested_opp_ids.append(opp_id)
                    result.total_ingested += 1
            except Exception as exc:
                result.errors.append(
                    f"Ingest error for {raw_opp.get('program', '?')}: {exc}"
                )

        result.ingested_opp_ids = ingested_opp_ids.copy()
        self.log.info("pipeline.ingest_done", count=result.total_ingested)
        return ingested_opp_ids

    async def _verify_ingested_opportunities(
        self,
        *,
        ingested_opp_ids: list[str],
        result: PipelineResult,
    ) -> None:
        outcomes = await self.opportunity_verifier.verify_batch(
            ingested_opp_ids,
            sync_social_status=True,
            concurrency=1,
        )
        for outcome in outcomes:
            if outcome.verified:
                result.total_verified += 1
            elif outcome.error:
                result.errors.append(
                    f"Verification failed for {outcome.opportunity_id}: {outcome.error}"
                )

        self.log.info("pipeline.verification_done", count=result.total_verified)

    async def _match_ingested_opportunities(
        self,
        *,
        ingested_opp_ids: list[str],
        company_profile_id: str,
        result: PipelineResult,
    ) -> None:
        outcomes = await self.opportunity_matcher.match_batch(
            ingested_opp_ids,
            company_profile_id,
            concurrency=1,
        )
        for outcome in outcomes:
            if outcome.matched:
                result.total_matched += 1
            elif outcome.error:
                result.errors.append(
                    f"Matching failed for {outcome.opportunity_id}: {outcome.error}"
                )

        self.log.info("pipeline.matching_done", count=result.total_matched)

    async def ingest_raw_opportunity(
        self,
        raw: dict,
        default_category: ProgramCategory | None = None,
    ) -> str | None:
        return await self.ingestor.ingest_raw_opportunity(
            raw,
            default_category=default_category,
        )

    async def _record_social_monitoring_event(
        self,
        raw: dict,
        opportunity_id: str,
    ) -> None:
        if raw.get("source_type") != "social":
            return
        source_url = str(raw.get("source_url", "") or "").strip()
        if not source_url:
            return
        event = SocialMonitoringEvent(
            id=generate_id("sme_"),
            source_url=source_url,
            matched_account=str(raw.get("matched_account", "") or ""),
            matched_account_type=str(raw.get("matched_account_type", "") or ""),
            monitoring_round=str(raw.get("social_monitoring_round", "") or ""),
            organization=str(raw.get("organization", "") or ""),
            program=str(raw.get("program", "") or ""),
            category=str(raw.get("category", "") or ""),
            signal_type=str(raw.get("social_signal_type", "") or ""),
            apply_url=raw.get("apply_url"),
            source_tier=int(raw.get("source_tier", 5) or 5),
            confidence=float(raw.get("confidence", 0.0) or 0.0),
            promoted_opportunity_id=opportunity_id,
            verification_status="pending",
        )
        await self.store.upsert_social_monitoring_event(event)

    async def _ingest_raw_opportunity(
        self,
        raw: dict,
        default_category: ProgramCategory | None = None,
    ) -> str | None:
        return await self.ingest_raw_opportunity(raw, default_category)

    @staticmethod
    def _infer_sector_tags(raw: dict) -> list[str]:
        return OpportunityIngestor.infer_sector_tags(raw)

    @staticmethod
    def _guess_org_type(raw: dict):
        return OpportunityIngestor.guess_org_type(raw)

    @staticmethod
    def _parse_category(
        cat_str: str,
        default: ProgramCategory | None,
    ) -> ProgramCategory:
        return OpportunityIngestor.parse_category(cat_str, default)

    @staticmethod
    def _parse_deadline(deadline_str: str | None):
        return OpportunityIngestor.parse_deadline(deadline_str)

    @staticmethod
    def _parse_source_tier(value):
        return OpportunityIngestor.parse_source_tier(value)

    @staticmethod
    def _parse_confidence(value) -> float:
        return OpportunityIngestor.parse_confidence(value)

    @staticmethod
    def _parse_budget_amount(budget_text: str | None) -> float | None:
        return OpportunityIngestor.parse_budget_amount(budget_text)


# ============================================================
# CLI
# ============================================================


async def main() -> None:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(
        description="Funding Intelligence Pipeline"
    )
    parser.add_argument(
        "--query", type=str, default="", help="검색 쿼리"
    )
    parser.add_argument(
        "--category",
        type=str,
        choices=[
            "grant",
            "accelerator",
            "vc_cohort",
            "fund",
            "builder_program",
            "residency",
            "hackathon_pipeline",
            "ecosystem_builder",
        ],
        default=None,
        help="프로그램 카테고리",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Company profile ID (매칭용)",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="DB 스키마 초기화",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="시드 데이터 로드",
    )

    args = parser.parse_args()
    if not args.query and not args.seed:
        parser.error("--query is required unless --seed is set")

    db_path = config.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with EntityStore(db_path) as store:
        # DB 초기화
        if args.init_db:
            await store.init_schema()
            print(f"DB initialized: {db_path}")

        # 시드 데이터
        if args.seed:
            await store.init_schema()
            # seed_raw.json에서 프로그램 데이터 인제스트
            seed_path = Path("data/seed_raw.json")
            if seed_path.exists():
                import json
                with open(seed_path, encoding="utf-8") as f:
                    seed_records = json.load(f)

                pipeline = FundingPipeline(store=store)
                ingested = 0
                for rec in seed_records:
                    # seed_raw.json 필드 → raw_opportunity 형식으로 변환
                    raw_opp = {
                        "organization": rec.get("organization", ""),
                        "program": rec.get("program", ""),
                        "category": rec.get("category", "grant"),
                        "status": rec.get("status", "unknown"),
                        "deadline": rec.get("deadline"),
                        "budget": rec.get("funding_range") or rec.get("max_amount"),
                        "apply_url": rec.get("apply_url"),
                        "program_url": rec.get("program_url") or rec.get("website"),
                        "description": rec.get("description", ""),
                        "focus_areas": rec.get("sector_tags", []),
                        "source_url": rec.get("website") or rec.get("apply_url") or "",
                        "org_type": rec.get("org_type"),
                        "source_tier": rec.get("source_tier"),
                        "fact_confidence": rec.get("fact_confidence"),
                    }
                    try:
                        cat = pipeline._parse_category(
                            rec.get("category", "grant"), None
                        )
                        opp_id = await pipeline._ingest_raw_opportunity(
                            raw_opp, cat
                        )
                        if opp_id:
                            ingested += 1
                    except Exception as e:
                        print(f"  [WARN] Seed ingest failed: {rec.get('program', '?')}: {e}")

                print(f"Seed data loaded: {ingested}/{len(seed_records)} records ingested")
            else:
                print(f"Seed file not found: {seed_path}")
                print("Run: python scripts/seed_importer.py --curated-csv output/spreadsheet/funding_sources_resolved.csv --output data/seed_raw.json")

            if not args.query:
                return

        # 파이프라인 실행
        category = ProgramCategory(args.category) if args.category else None

        pipeline = FundingPipeline(store=store)
        result = await pipeline.run_discovery_pipeline(
            query=args.query,
            category=category,
            company_profile_id=args.profile,
        )

        print(result.summary)


if __name__ == "__main__":
    asyncio.run(main())
