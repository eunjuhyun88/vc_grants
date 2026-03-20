from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from src.agents.matching import calculate_priority_score
from src.core.types import (
    MatchingInput,
    MatchingOutput,
    OpportunityStatus,
    OutputStatus,
)
from src.db.entity_store import EntityStore

ACTIONABLE_STATUSES = {
    OpportunityStatus.OPEN,
    OpportunityStatus.ROLLING,
    OpportunityStatus.UPCOMING,
}


@dataclass
class MatchingOutcome:
    opportunity_id: str
    matched: bool
    output: MatchingOutput | None = None
    error: str | None = None


class OpportunityMatcher:
    """Shared matching execution and rankable filtering for opportunities."""

    def __init__(self, store: EntityStore, agent) -> None:
        self.store = store
        self.agent = agent

    async def filter_rankable_opportunity_ids(
        self,
        opportunity_ids: Sequence[str],
    ) -> list[str]:
        rankable: list[str] = []

        for opportunity_id in opportunity_ids:
            opportunity = await self.store.get_opportunity(opportunity_id)
            if opportunity is None:
                continue
            if opportunity.output_status != OutputStatus.VERIFIED:
                continue
            if opportunity.status not in ACTIONABLE_STATUSES:
                continue
            if (opportunity.fact_confidence or 0.0) < 0.75:
                continue
            if opportunity.days_left is not None and opportunity.days_left < 0:
                continue
            endpoints = await self.store.get_active_endpoints(opportunity_id)
            if not endpoints:
                continue
            rankable.append(opportunity_id)

        return rankable

    async def match_opportunity(
        self,
        opportunity_id: str,
        company_profile_id: str,
        *,
        intent: str = "default",
    ) -> MatchingOutcome:
        try:
            match_result = await self.agent.run(
                MatchingInput(
                    opportunity_id=opportunity_id,
                    company_profile_id=company_profile_id,
                    persist=True,
                )
            )
        except Exception as exc:
            return MatchingOutcome(
                opportunity_id=opportunity_id,
                matched=False,
                error=str(exc),
            )

        if not match_result.success:
            return MatchingOutcome(
                opportunity_id=opportunity_id,
                matched=False,
                error=match_result.error,
            )

        output = MatchingOutput(**match_result.data)
        output.priority_score = round(
            calculate_priority_score(
                output.fit_score,
                output.urgency_score,
                output.actionability_score,
                output.expected_value,
                output.confidence,
                intent,
            ),
            3,
        )

        return MatchingOutcome(
            opportunity_id=opportunity_id,
            matched=True,
            output=output,
        )

    async def match_batch(
        self,
        opportunity_ids: Sequence[str],
        company_profile_id: str,
        *,
        intent: str = "default",
        concurrency: int = 1,
    ) -> list[MatchingOutcome]:
        semaphore = asyncio.Semaphore(max(1, concurrency))

        async def _run(opportunity_id: str) -> MatchingOutcome:
            async with semaphore:
                return await self.match_opportunity(
                    opportunity_id,
                    company_profile_id,
                    intent=intent,
                )

        return await asyncio.gather(
            *[_run(opportunity_id) for opportunity_id in opportunity_ids]
        )

    @staticmethod
    def rank_outputs(
        outcomes: Sequence[MatchingOutcome],
        *,
        top_n: int | None = None,
    ) -> list[MatchingOutput]:
        ranked = [
            outcome.output
            for outcome in outcomes
            if outcome.output is not None
        ]
        ranked.sort(key=lambda output: output.priority_score, reverse=True)
        if top_n is None:
            return ranked
        return ranked[:top_n]
