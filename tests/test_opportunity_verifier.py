from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.opportunity_verifier import OpportunityVerifier


def test_build_sources_dedups_and_limits():
    opportunity = SimpleNamespace(
        apply_url="https://example.com/apply",
        source_chain=[
            "https://example.com/apply",
            "https://example.com/program",
            "https://example.com/social",
        ],
    )

    assert OpportunityVerifier.build_sources(opportunity) == [
        "https://example.com/apply",
        "https://example.com/program",
        "https://example.com/social",
    ]
    assert OpportunityVerifier.build_sources(opportunity, source_limit=2) == [
        "https://example.com/apply",
        "https://example.com/program",
    ]


@pytest.mark.asyncio
async def test_verify_opportunity_syncs_social_status_on_success():
    store = SimpleNamespace(
        get_opportunity=AsyncMock(
            return_value=SimpleNamespace(
                apply_url="https://example.com/apply",
                source_chain=["https://example.com/source"],
            )
        ),
        sync_social_monitoring_status_for_opportunity=AsyncMock(),
    )
    agent = SimpleNamespace(
        run=AsyncMock(return_value=SimpleNamespace(success=True, error=None))
    )
    verifier = OpportunityVerifier(store=store, agent=agent)

    outcome = await verifier.verify_opportunity(
        "opp_1",
        sync_social_status=True,
    )

    assert outcome.verified is True
    store.sync_social_monitoring_status_for_opportunity.assert_awaited_once_with("opp_1")


@pytest.mark.asyncio
async def test_verify_batch_returns_errors_from_agent():
    store = SimpleNamespace(
        get_opportunity=AsyncMock(
            side_effect=[
                SimpleNamespace(apply_url="https://example.com/apply", source_chain=[]),
                SimpleNamespace(apply_url="https://example.com/apply2", source_chain=[]),
            ]
        ),
        sync_social_monitoring_status_for_opportunity=AsyncMock(),
    )
    agent = SimpleNamespace(
        run=AsyncMock(
            side_effect=[
                SimpleNamespace(success=True, error=None),
                SimpleNamespace(success=False, error="timeout"),
            ]
        )
    )
    verifier = OpportunityVerifier(store=store, agent=agent)

    outcomes = await verifier.verify_batch(["opp_1", "opp_2"], concurrency=2)

    assert [outcome.verified for outcome in outcomes] == [True, False]
    assert outcomes[1].error == "timeout"
