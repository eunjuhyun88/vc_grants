from __future__ import annotations

from datetime import date, timedelta

from src.core.types import OpportunityCard
from src.interface.opportunity_filters import filter_current_cards


def test_filter_current_cards_excludes_past_exact_deadline():
    past = (date.today() - timedelta(days=1)).isoformat()
    stale = OpportunityCard(
        organization="Old Org",
        program="Closed Batch",
        category="accelerator",
        status="open",
        apply_url="https://old.example/apply",
        confidence=0.8,
        deadline=past,
        days_left=-1,
    )

    assert filter_current_cards([stale]) == []


def test_filter_current_cards_keeps_rolling_rows():
    rolling = OpportunityCard(
        organization="Ethereum Foundation",
        program="Ethereum ESP",
        category="grant",
        status="rolling",
        apply_url="https://esp.ethereum.foundation",
        confidence=0.9,
        deadline="Rolling",
    )

    assert filter_current_cards([rolling]) == [rolling]


def test_filter_current_cards_excludes_unknown_status_rows():
    unknown = OpportunityCard(
        organization="Cardano",
        program="Cardano Catalyst",
        category="grant",
        status="unknown",
        apply_url="https://cardanocataly.st/",
        confidence=0.95,
    )

    assert filter_current_cards([unknown]) == []


def test_filter_current_cards_excludes_low_confidence_rows():
    weak = OpportunityCard(
        organization="Alliance",
        program="Alliance Accelerator",
        category="accelerator",
        status="open",
        apply_url="https://alliance.xyz/apply",
        confidence=0.60,
    )

    assert filter_current_cards([weak]) == []
