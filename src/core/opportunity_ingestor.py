from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from src.core.types import (
    Opportunity,
    OpportunityStatus,
    Organization,
    OrgType,
    OutputStatus,
    Program,
    ProgramCategory,
    extract_domain,
    generate_id,
    normalize_org_name,
)
from src.db.entity_store import EntityStore


class OpportunityIngestor:
    """Resolve raw opportunities into Organization, Program, and Opportunity rows."""

    def __init__(self, store: EntityStore) -> None:
        self.store = store

    async def ingest_raw_opportunity(
        self,
        raw: dict,
        default_category: ProgramCategory | None = None,
    ) -> str | None:
        org_name = raw.get("organization", "").strip()
        prog_name = raw.get("program", "").strip()

        if not org_name or not prog_name:
            return None

        source_url = raw.get("source_url", "")
        apply_url_raw = raw.get("apply_url")
        program_url_raw = raw.get("program_url") or source_url or apply_url_raw or ""
        canonical_url = apply_url_raw or program_url_raw or source_url or ""

        normalized = normalize_org_name(org_name)
        domain = (
            extract_domain(program_url_raw)
            or extract_domain(apply_url_raw)
            or extract_domain(source_url)
        )

        org = None
        if domain:
            org = await self.store.get_organization_by_domain(domain)
        if org is None:
            org = await self.store.get_organization_by_name(normalized)

        focus_areas = raw.get("focus_areas", [])
        if not focus_areas or not isinstance(focus_areas, list):
            focus_areas = self.infer_sector_tags(raw)

        if org is None:
            org = Organization(
                id=generate_id("org_"),
                normalized_name=normalized,
                display_name=org_name,
                domain=domain,
                org_type=self.guess_org_type(raw),
                sector_tags=focus_areas,
                website_url=program_url_raw or None,
            )
            await self.store.create_organization(org)
        else:
            updates: dict[str, Any] = {}
            if not org.domain and domain:
                updates["domain"] = domain
            if not org.sector_tags and focus_areas:
                updates["sector_tags"] = focus_areas
            if not org.website_url and program_url_raw:
                updates["website_url"] = program_url_raw
            if updates:
                await self.store.update_organization(org.id, **updates)
                if focus_areas:
                    org.sector_tags = focus_areas

        prog_normalized = prog_name.lower().strip()
        program = await self.store.get_program_by_org_and_name(org.id, prog_normalized)

        category = self.parse_category(raw.get("category", ""), default_category)
        description = (raw.get("description") or "").strip() or None

        if program is None:
            program = Program(
                id=generate_id("prg_"),
                org_id=org.id,
                normalized_name=prog_normalized,
                display_name=prog_name,
                category=category,
                program_url=program_url_raw or None,
                description=description,
            )
            await self.store.create_program(program)
        else:
            program_updates: dict[str, Any] = {}
            if program.category != category:
                program_updates["category"] = category
            if not program.program_url and program_url_raw:
                program_updates["program_url"] = program_url_raw
            if not program.description and description:
                program_updates["description"] = description
            if program_updates:
                await self.store.update_program(program.id, **program_updates)
                if "category" in program_updates:
                    program.category = category
                if "program_url" in program_updates:
                    program.program_url = program_url_raw or None
                if "description" in program_updates:
                    program.description = description

        status = self.parse_status(raw.get("status", "unknown"))
        deadline_at = self.parse_deadline(raw.get("deadline"))
        budget_text = raw.get("budget")
        budget_amount = self.parse_budget_amount(budget_text)
        source_tier = self.parse_source_tier(raw.get("source_tier"))
        fact_confidence = self.parse_confidence(raw.get("fact_confidence"))

        source_chain: list[str] = []
        if source_url:
            source_chain.append(source_url)
        if program_url_raw and program_url_raw not in source_chain:
            source_chain.append(program_url_raw)
        if apply_url_raw and apply_url_raw not in source_chain:
            source_chain.append(apply_url_raw)
        if program.program_url and program.program_url not in source_chain:
            source_chain.append(program.program_url)

        if apply_url_raw:
            existing = await self.store.get_latest_opportunity_by_program_and_apply_url(
                program.id,
                canonical_url,
            )
        elif not raw.get("cycle_key"):
            existing = await self.store.get_latest_opportunity_by_program(program.id)
        else:
            existing = None

        if existing is not None:
            updates: dict[str, Any] = {}
            if status != OpportunityStatus.UNKNOWN and existing.status != status:
                updates["status"] = status
            if deadline_at and existing.deadline_at != deadline_at:
                updates["deadline_at"] = deadline_at
            if budget_amount is not None and existing.budget_amount is None:
                updates["budget_amount"] = budget_amount
            if budget_text and not existing.budget_note:
                updates["budget_note"] = budget_text
            if apply_url_raw and not existing.apply_url:
                updates["apply_url"] = apply_url_raw
            if source_tier is not None:
                existing_tier = existing.source_tier
                best_tier = source_tier if existing_tier is None else min(existing_tier, source_tier)
                if best_tier != existing_tier:
                    updates["source_tier"] = best_tier
            if fact_confidence > existing.fact_confidence:
                updates["fact_confidence"] = fact_confidence
            merged_chain = list(dict.fromkeys(existing.source_chain + source_chain))
            if merged_chain != existing.source_chain:
                updates["source_chain"] = merged_chain
            if updates:
                await self.store.update_opportunity(existing.id, **updates)
            return existing.id

        opp = Opportunity(
            id=generate_id("opp_"),
            program_id=program.id,
            status=status,
            deadline_at=deadline_at,
            budget_amount=budget_amount,
            budget_note=budget_text,
            apply_url=apply_url_raw,
            output_status=OutputStatus.PENDING,
            fact_confidence=fact_confidence,
            source_tier=source_tier,
            source_chain=source_chain,
        )
        await self.store.create_opportunity(opp)
        return opp.id

    @staticmethod
    def infer_sector_tags(raw: dict) -> list[str]:
        tags: list[str] = []
        combined = " ".join(
            str(part or "")
            for part in [
                raw.get("category", ""),
                raw.get("description", ""),
                raw.get("program", ""),
                raw.get("organization", ""),
            ]
        ).lower()

        keyword_map = {
            "crypto": "crypto",
            "blockchain": "blockchain",
            "web3": "web3",
            "defi": "defi",
            "nft": "nft",
            "ai": "ai",
            "gaming": "gaming",
            "infrastructure": "infrastructure",
            "developer": "developer_tools",
            "zk": "zero_knowledge",
            "layer": "layer",
            "dao": "dao",
            "wallet": "wallets",
        }

        for keyword, tag in keyword_map.items():
            if keyword in combined:
                tags.append(tag)

        return list(dict.fromkeys(tags))

    @staticmethod
    def guess_org_type(raw: dict) -> OrgType:
        raw_org_type = raw.get("org_type")
        if raw_org_type:
            try:
                return OrgType(str(raw_org_type).lower())
            except ValueError:
                pass

        category = raw.get("category", "").lower()
        if category in {"fund", "vc_cohort"} or "vc" in category or "venture" in category:
            return OrgType.VC
        if category in {"accelerator", "residency", "hackathon_pipeline"} or "accelerator" in category:
            return OrgType.ACCELERATOR
        if category in {"builder_program", "ecosystem_builder"} or "ecosystem" in category:
            return OrgType.ECOSYSTEM
        return OrgType.FOUNDATION

    @staticmethod
    def parse_category(
        category: str,
        default: ProgramCategory | None,
    ) -> ProgramCategory:
        category_map = {
            "grant": ProgramCategory.GRANT,
            "accelerator": ProgramCategory.ACCELERATOR,
            "vc_cohort": ProgramCategory.VC_COHORT,
            "fund": ProgramCategory.FUND,
            "vc_fund": ProgramCategory.FUND,
            "builder_program": ProgramCategory.BUILDER_PROGRAM,
            "residency": ProgramCategory.RESIDENCY,
            "hackathon_pipeline": ProgramCategory.HACKATHON_PIPELINE,
            "ecosystem_builder": ProgramCategory.ECOSYSTEM_BUILDER,
        }
        return category_map.get(category.lower(), default or ProgramCategory.GRANT)

    @staticmethod
    def parse_status(status: str) -> OpportunityStatus:
        status_map = {
            "open": OpportunityStatus.OPEN,
            "rolling": OpportunityStatus.ROLLING,
            "deadline": OpportunityStatus.OPEN,
            "upcoming": OpportunityStatus.UPCOMING,
            "closed": OpportunityStatus.CLOSED,
        }
        return status_map.get(status.lower(), OpportunityStatus.UNKNOWN)

    @staticmethod
    def parse_deadline(deadline: str | None) -> datetime | None:
        if not deadline:
            return None
        try:
            return datetime.fromisoformat(deadline)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def parse_source_tier(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def parse_confidence(value: Any) -> float:
        if value in (None, ""):
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def parse_budget_amount(budget_text: str | None) -> float | None:
        if not budget_text:
            return None

        amounts: list[float] = []
        for match in re.finditer(r"\$?([\d,.]+)\s*([KkMm])?", budget_text):
            number = match.group(1).replace(",", "")
            try:
                amount = float(number)
            except ValueError:
                continue

            multiplier = match.group(2)
            if multiplier and multiplier.upper() == "K":
                amount *= 1000
            elif multiplier and multiplier.upper() == "M":
                amount *= 1000000
            amounts.append(amount)

        return max(amounts) if amounts else None
