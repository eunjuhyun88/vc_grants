from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.opportunity_matcher import MatchingOutcome, OpportunityMatcher


@pytest.mark.asyncio
async def test_filter_rankable_opportunity_ids_keeps_only_verified_actionable_rows():
    opportunities = {
        "opp_good": SimpleNamespace(
            output_status="verified",
            status="open",
            fact_confidence=0.9,
            days_left=3,
        ),
        "opp_pending": SimpleNamespace(
            output_status="pending",
            status="open",
            fact_confidence=0.9,
            days_left=3,
        ),
        "opp_closed": SimpleNamespace(
            output_status="verified",
            status="closed",
            fact_confidence=0.9,
            days_left=3,
        ),
        "opp_low_conf": SimpleNamespace(
            output_status="verified",
            status="open",
            fact_confidence=0.6,
            days_left=3,
        ),
        "opp_expired": SimpleNamespace(
            output_status="verified",
            status="open",
            fact_confidence=0.9,
            days_left=-1,
        ),
        "opp_no_endpoint": SimpleNamespace(
            output_status="verified",
            status="open",
            fact_confidence=0.9,
            days_left=3,
        ),
    }
    endpoints = {
        "opp_good": [SimpleNamespace(url="https://example.com/apply")],
        "opp_no_endpoint": [],
    }
    store = SimpleNamespace(
        get_opportunity=AsyncMock(side_effect=lambda opportunity_id: opportunities.get(opportunity_id)),
        get_active_endpoints=AsyncMock(side_effect=lambda opportunity_id: endpoints.get(opportunity_id, [])),
    )
    matcher = OpportunityMatcher(store=store, agent=SimpleNamespace())

    rankable = await matcher.filter_rankable_opportunity_ids(
        [
            "opp_good",
            "opp_pending",
            "opp_closed",
            "opp_low_conf",
            "opp_expired",
            "opp_no_endpoint",
        ]
    )

    assert rankable == ["opp_good"]


@pytest.mark.asyncio
async def test_match_batch_returns_errors_and_ranked_outputs():
    agent = SimpleNamespace(
        run=AsyncMock(
            side_effect=[
                SimpleNamespace(
                    success=True,
                    data={
                        "opportunity_id": "opp_1",
                        "project_name": "Proj 1",
                        "fit_score": 0.4,
                        "priority_score": 0.0,
                        "why_fit": "why 1",
                        "next_action": "act 1",
                        "urgency_score": 0.3,
                        "actionability_score": 0.5,
                        "expected_value": 0.2,
                        "confidence": 0.8,
                    },
                ),
                SimpleNamespace(success=False, error="timeout"),
                SimpleNamespace(
                    success=True,
                    data={
                        "opportunity_id": "opp_3",
                        "project_name": "Proj 3",
                        "fit_score": 0.8,
                        "priority_score": 0.0,
                        "why_fit": "why 3",
                        "next_action": "act 3",
                        "urgency_score": 0.8,
                        "actionability_score": 0.9,
                        "expected_value": 0.6,
                        "confidence": 0.9,
                    },
                ),
            ]
        )
    )
    matcher = OpportunityMatcher(store=SimpleNamespace(), agent=agent)

    outcomes = await matcher.match_batch(
        ["opp_1", "opp_2", "opp_3"],
        "cp_test",
        intent="best_fit",
        concurrency=2,
    )
    ranked = matcher.rank_outputs(outcomes, top_n=2)

    assert [outcome.matched for outcome in outcomes] == [True, False, True]
    assert outcomes[1] == MatchingOutcome(
        opportunity_id="opp_2",
        matched=False,
        error="timeout",
    )
    assert [output.opportunity_id for output in ranked] == ["opp_3", "opp_1"]
