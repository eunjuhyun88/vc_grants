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
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from src.agents.discovery import DiscoveryAgent
from src.agents.matching import MatchingAgent
from src.agents.verification import VerificationAgent
from src.core.config import Config, config
from src.core.errors import PipelineError
from src.core.types import (
    DiscoveryInput,
    MatchingInput,
    Opportunity,
    OpportunityStatus,
    Organization,
    OrgType,
    OutputStatus,
    Program,
    ProgramCategory,
    VerificationInput,
    generate_id,
    normalize_org_name,
    normalize_url,
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
        self.log = logger.bind(component="pipeline")

    async def run_discovery_pipeline(
        self,
        query: str,
        category: ProgramCategory | None = None,
        company_profile_id: str | None = None,
        sources: list[str] | None = None,
    ) -> PipelineResult:
        """전체 파이프라인 실행."""
        start = time.monotonic()
        result = PipelineResult()

        self.log.info(
            "pipeline.start",
            query=query,
            category=category,
        )

        # ============================================================
        # Phase 1: Discovery
        # ============================================================
        try:
            discovery_input = DiscoveryInput(
                query=query,
                category=category,
                sources=sources or [],
            )
            discovery_result = await self.discovery.run(discovery_input)

            if discovery_result.success:
                raw_opps = discovery_result.data.get("raw_opportunities", [])
                result.total_discovered = len(raw_opps)
                self.log.info("pipeline.discovery_done", count=len(raw_opps))
            else:
                result.errors.append(
                    f"Discovery failed: {discovery_result.error}"
                )
                raw_opps = []

        except Exception as e:
            result.errors.append(f"Discovery error: {e}")
            raw_opps = []

        # ============================================================
        # Phase 2: Ingest (Entity Resolution)
        # ============================================================
        ingested_opp_ids: list[str] = []
        for raw_opp in raw_opps:
            try:
                opp_id = await self._ingest_raw_opportunity(raw_opp, category)
                if opp_id:
                    ingested_opp_ids.append(opp_id)
                    result.total_ingested += 1
            except Exception as e:
                result.errors.append(
                    f"Ingest error for {raw_opp.get('program', '?')}: {e}"
                )
                continue

        self.log.info("pipeline.ingest_done", count=result.total_ingested)

        # ============================================================
        # Phase 3: Verification
        # ============================================================
        for opp_id in ingested_opp_ids:
            try:
                opp = await self.store.get_opportunity(opp_id)
                if opp is None:
                    continue

                sources_for_verify: list[str] = []
                if opp.apply_url:
                    sources_for_verify.append(opp.apply_url)

                # source_chain에서 추가 source
                for src_url in opp.source_chain:
                    if src_url not in sources_for_verify:
                        sources_for_verify.append(src_url)

                verify_input = VerificationInput(
                    opportunity_id=opp_id,
                    sources=sources_for_verify,
                )
                verify_result = await self.verification.run(verify_input)

                if verify_result.success:
                    result.total_verified += 1
                else:
                    result.errors.append(
                        f"Verification failed for {opp_id}: {verify_result.error}"
                    )

            except Exception as e:
                result.errors.append(f"Verification error for {opp_id}: {e}")
                continue

        self.log.info("pipeline.verification_done", count=result.total_verified)

        # ============================================================
        # Phase 4: Matching (프로필이 있을 때만)
        # ============================================================
        if company_profile_id:
            for opp_id in ingested_opp_ids:
                try:
                    match_input = MatchingInput(
                        opportunity_id=opp_id,
                        company_profile_id=company_profile_id,
                        persist=True,
                    )
                    match_result = await self.matching.run(match_input)

                    if match_result.success:
                        result.total_matched += 1
                    else:
                        result.errors.append(
                            f"Matching failed for {opp_id}: {match_result.error}"
                        )

                except Exception as e:
                    result.errors.append(f"Matching error for {opp_id}: {e}")
                    continue

            self.log.info("pipeline.matching_done", count=result.total_matched)

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

    async def _ingest_raw_opportunity(
        self,
        raw: dict,
        default_category: ProgramCategory | None = None,
    ) -> str | None:
        """raw opportunity dict → Organization + Program + Opportunity 레코드."""
        org_name = raw.get("organization", "").strip()
        prog_name = raw.get("program", "").strip()

        if not org_name or not prog_name:
            return None

        # 1. Organization 해결 (dedup by normalized name)
        normalized = normalize_org_name(org_name)
        org = await self.store.get_organization_by_name(normalized)

        if org is None:
            org = Organization(
                id=generate_id("org_"),
                normalized_name=normalized,
                display_name=org_name,
                org_type=self._guess_org_type(raw),
            )
            await self.store.create_organization(org)

        # 2. Program 해결 (dedup by org + normalized name)
        prog_normalized = prog_name.lower().strip()
        program = await self.store.get_program_by_org_and_name(
            org.id, prog_normalized
        )

        if program is None:
            # 카테고리 결정
            cat_str = raw.get("category", "")
            category = self._parse_category(cat_str, default_category)

            program = Program(
                id=generate_id("prg_"),
                org_id=org.id,
                normalized_name=prog_normalized,
                display_name=prog_name,
                category=category,
                program_url=raw.get("apply_url"),
            )
            await self.store.create_program(program)

        # 3. Opportunity 생성
        status = self._parse_status(raw.get("status", "unknown"))
        deadline_at = self._parse_deadline(raw.get("deadline"))
        apply_url = raw.get("apply_url")
        budget_text = raw.get("budget")
        budget_amount = self._parse_budget_amount(budget_text)
        source_url = raw.get("source_url", "")

        opp = Opportunity(
            id=generate_id("opp_"),
            program_id=program.id,
            status=status,
            deadline_at=deadline_at,
            budget_amount=budget_amount,
            budget_note=budget_text,
            apply_url=apply_url,
            output_status=OutputStatus.PENDING,
            fact_confidence=0.0,
            source_chain=[source_url] if source_url else [],
        )
        await self.store.create_opportunity(opp)

        return opp.id

    def _guess_org_type(self, raw: dict) -> OrgType:
        """raw data에서 조직 유형 추측."""
        cat = raw.get("category", "").lower()
        if "vc" in cat or "cohort" in cat or "venture" in cat:
            return OrgType.VC
        if "accelerator" in cat:
            return OrgType.ACCELERATOR
        if "ecosystem" in cat:
            return OrgType.ECOSYSTEM
        return OrgType.FOUNDATION

    def _parse_category(
        self,
        cat_str: str,
        default: ProgramCategory | None,
    ) -> ProgramCategory:
        """카테고리 문자열 → ProgramCategory."""
        cat_map = {
            "grant": ProgramCategory.GRANT,
            "accelerator": ProgramCategory.ACCELERATOR,
            "vc_cohort": ProgramCategory.VC_COHORT,
            "ecosystem_builder": ProgramCategory.ECOSYSTEM_BUILDER,
        }
        return cat_map.get(cat_str.lower(), default or ProgramCategory.GRANT)

    def _parse_status(self, status_str: str) -> OpportunityStatus:
        """상태 문자열 → OpportunityStatus."""
        status_map = {
            "open": OpportunityStatus.OPEN,
            "rolling": OpportunityStatus.ROLLING,
            "deadline": OpportunityStatus.DEADLINE,
            "upcoming": OpportunityStatus.UPCOMING,
            "closed": OpportunityStatus.CLOSED,
        }
        return status_map.get(status_str.lower(), OpportunityStatus.UNKNOWN)

    def _parse_deadline(self, deadline_str: str | None) -> datetime | None:
        """마감일 문자열 → datetime."""
        if not deadline_str:
            return None
        try:
            return datetime.fromisoformat(deadline_str)
        except (ValueError, TypeError):
            return None

    def _parse_budget_amount(self, budget_text: str | None) -> float | None:
        """예산 텍스트에서 숫자 추출."""
        if not budget_text:
            return None

        import re

        # $500K, $50K-$500K, $1M 등 패턴
        amounts: list[float] = []
        for match in re.finditer(r"\$?([\d,.]+)\s*([KkMm])?", budget_text):
            num_str = match.group(1).replace(",", "")
            try:
                num = float(num_str)
            except ValueError:
                continue

            multiplier = match.group(2)
            if multiplier and multiplier.upper() == "K":
                num *= 1000
            elif multiplier and multiplier.upper() == "M":
                num *= 1000000
            amounts.append(num)

        # 최대값 반환 (범위의 경우)
        return max(amounts) if amounts else None


# ============================================================
# CLI
# ============================================================


async def main() -> None:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(
        description="Funding Intelligence Pipeline"
    )
    parser.add_argument(
        "--query", type=str, required=True, help="검색 쿼리"
    )
    parser.add_argument(
        "--category",
        type=str,
        choices=["grant", "accelerator", "vc_cohort", "ecosystem_builder"],
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
            seed_path = Path("data/seed/hoot_profile.json")
            if seed_path.exists():
                profile_id = await store.load_seed_profile(seed_path)
                print(f"Seed profile loaded: {profile_id}")
            else:
                print(f"Seed file not found: {seed_path}")

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
