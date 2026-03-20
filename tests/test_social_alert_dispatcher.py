from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from src.core.types import (
    CompanyProfile,
    CompanyStage,
    Opportunity,
    OpportunityStatus,
    Organization,
    OrgType,
    OutputStatus,
    Program,
    ProgramCategory,
    SocialMonitoringEvent,
    generate_id,
)
from src.db.entity_store import EntityStore
from src.interface.social_alert_dispatcher import dispatch_pending_social_alerts


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)
        return True


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    db_path = tmp_path / "test.db"
    async with EntityStore(db_path) as s:
        await s.init_schema()
        yield s


async def _seed_verified_social_alert(store: EntityStore) -> str:
    org = Organization(
        id=generate_id("org_"),
        normalized_name="monad",
        display_name="Monad",
        domain="monad.xyz",
        org_type=OrgType.ECOSYSTEM,
        website_url="https://monad.xyz",
    )
    await store.create_organization(org)

    program = Program(
        id=generate_id("prg_"),
        org_id=org.id,
        normalized_name="nitro accelerator",
        display_name="Nitro Accelerator",
        category=ProgramCategory.VC_COHORT,
        program_url="https://nitroacc.xyz",
        description="12-week ecosystem accelerator",
    )
    await store.create_program(program)

    opp = Opportunity(
        id=generate_id("opp_"),
        program_id=program.id,
        status=OpportunityStatus.OPEN,
        apply_url="https://nitroacc.xyz/apply",
        output_status=OutputStatus.VERIFIED,
        fact_confidence=0.91,
        source_tier=1,
        days_left=2,
    )
    await store.create_opportunity(opp)

    event = SocialMonitoringEvent(
        id=generate_id("sme_"),
        source_url="https://x.com/monad/status/2021278828484567142",
        matched_account="monad",
        matched_account_type="ecosystem",
        monitoring_round="ecosystem-operators",
        organization="Monad",
        program="Nitro Accelerator",
        category="vc_cohort",
        signal_type="applications_open",
        apply_url="https://nitroacc.xyz/apply",
        confidence=0.52,
        promoted_opportunity_id=opp.id,
        verification_status="verified",
    )
    await store.upsert_social_monitoring_event(event)
    return event.id


@pytest.mark.asyncio
async def test_dispatch_pending_social_alerts_sends_and_marks_notified(store: EntityStore):
    event_id = await _seed_verified_social_alert(store)
    await store.create_company_profile(
        CompanyProfile(
            id=generate_id("cp_"),
            company_name="HOOT",
            stage=CompanyStage.MVP,
            telegram_user_id=12345,
        )
    )

    bot = FakeBot()
    result = await dispatch_pending_social_alerts(bot=bot, store=store, limit=5)

    assert result["checked"] == 1
    assert result["sent"] == 1
    assert result["notified"] == 1
    assert len(bot.messages) == 1
    assert bot.messages[0]["chat_id"] == 12345
    assert "Nitro Accelerator" in bot.messages[0]["text"]

    events = await store.list_social_monitoring_events(limit=5)
    sent_event = next(event for event in events if event.id == event_id)
    assert sent_event.notified is True


@pytest.mark.asyncio
async def test_dispatch_pending_social_alerts_skips_when_no_recipients(store: EntityStore):
    await _seed_verified_social_alert(store)

    bot = FakeBot()
    result = await dispatch_pending_social_alerts(bot=bot, store=store, limit=5)

    assert result["checked"] == 0
    assert result["sent"] == 0
    assert result["recipients"] == 0
    assert bot.messages == []
