from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from src.core.types import VerificationInput
from src.db.entity_store import EntityStore


@dataclass
class VerificationOutcome:
    opportunity_id: str
    verified: bool
    error: str | None = None


class OpportunityVerifier:
    """Shared verification execution for ingested opportunities."""

    def __init__(self, store: EntityStore, agent) -> None:
        self.store = store
        self.agent = agent

    @staticmethod
    def build_sources(opportunity, *, source_limit: int | None = None) -> list[str]:
        sources: list[str] = []
        if opportunity.apply_url:
            sources.append(opportunity.apply_url)
        for source_url in opportunity.source_chain:
            if source_url and source_url not in sources:
                sources.append(source_url)
        if source_limit is not None:
            return sources[:source_limit]
        return sources

    async def verify_opportunity(
        self,
        opportunity_id: str,
        *,
        source_limit: int | None = None,
        sync_social_status: bool = False,
    ) -> VerificationOutcome:
        opportunity = await self.store.get_opportunity(opportunity_id)
        if opportunity is None:
            return VerificationOutcome(opportunity_id=opportunity_id, verified=False)

        sources = self.build_sources(opportunity, source_limit=source_limit)
        if not sources:
            return VerificationOutcome(opportunity_id=opportunity_id, verified=False)

        try:
            verify_result = await self.agent.run(
                VerificationInput(
                    opportunity_id=opportunity_id,
                    sources=sources,
                )
            )
        except Exception as exc:
            return VerificationOutcome(
                opportunity_id=opportunity_id,
                verified=False,
                error=str(exc),
            )

        if not verify_result.success:
            return VerificationOutcome(
                opportunity_id=opportunity_id,
                verified=False,
                error=verify_result.error,
            )

        if sync_social_status:
            await self.store.sync_social_monitoring_status_for_opportunity(opportunity_id)

        return VerificationOutcome(opportunity_id=opportunity_id, verified=True)

    async def verify_batch(
        self,
        opportunity_ids: Sequence[str],
        *,
        source_limit: int | None = None,
        sync_social_status: bool = False,
        concurrency: int = 1,
    ) -> list[VerificationOutcome]:
        semaphore = asyncio.Semaphore(max(1, concurrency))

        async def _run(opportunity_id: str) -> VerificationOutcome:
            async with semaphore:
                return await self.verify_opportunity(
                    opportunity_id,
                    source_limit=source_limit,
                    sync_social_status=sync_social_status,
                )

        return await asyncio.gather(*[_run(opportunity_id) for opportunity_id in opportunity_ids])
