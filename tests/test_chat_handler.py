from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import src.interface.handlers.chat_handler as chat_module
from src.core.types import CompanyProfile, CompanyStage
from src.interface.handlers.chat_handler import (
    _detect_structured_route,
    _extract_urls,
    _infer_ranking_intent,
    _looks_like_funding_lead_message,
)


def _profile() -> CompanyProfile:
    return CompanyProfile(
        id="cp_test",
        company_name="Holo Studio Co., Ltd.",
        stage=CompanyStage.MVP,
        sector_tags=["ai_infra"],
        projects=[
            {"name": "HOOT", "priority": 1, "tags": ["ai_infra"]},
            {"name": "StockClaw", "priority": 2, "tags": ["analytics"]},
        ],
        telegram_user_id=1,
    )


def test_infer_ranking_intent():
    assert _infer_ranking_intent("급한 것부터 보여줘") == "urgent"
    assert _infer_ranking_intent("지금 바로 낼 수 있는 것") == "ready_now"
    assert _infer_ranking_intent("가장 잘 맞는 것") == "best_fit"
    assert _infer_ranking_intent("추천해줘") == "default"


def test_detect_structured_route_for_project_funding():
    route = _detect_structured_route(
        "HOOT 기준 지금 낼 수 있는 것 정리해줘",
        _profile(),
    )
    assert route is not None
    assert route.intent == "funding_for_project"
    assert route.project_name == "HOOT"
    assert route.ranking_intent == "ready_now"


def test_detect_structured_route_for_funding_map():
    route = _detect_structured_route(
        "HOOT funding map 보여줘",
        _profile(),
    )
    assert route is not None
    assert route.intent == "funding_map"
    assert route.project_name == "HOOT"


def test_detect_structured_route_for_org_dossier():
    route = _detect_structured_route(
        "Monad 어떤 곳이야 정리해줘",
        _profile(),
    )
    assert route is not None
    assert route.intent == "org"
    assert route.organization_name == "Monad"


def test_detect_structured_route_returns_none_for_plain_chat():
    route = _detect_structured_route(
        "안녕 도와줘",
        _profile(),
    )
    assert route is None


def test_extract_urls_dedups_and_trims_trailing_punctuation():
    urls = _extract_urls(
        "Apply https://tally.so/r/aQdj2W, details https://tally.so/r/aQdj2W)."
    )
    assert urls == ["https://tally.so/r/aQdj2W"]


def test_looks_like_funding_lead_message_for_form_link():
    text = "Venture League Pitch Competition Application https://docs.google.com/forms/d/e/test/viewform"
    urls = _extract_urls(text)
    assert _looks_like_funding_lead_message(text, urls) is True


def test_looks_like_funding_lead_message_ignores_generic_article_link():
    text = "https://a16zcrypto.com/posts/article/build-world-class-sales-team/"
    urls = _extract_urls(text)
    assert _looks_like_funding_lead_message(text, urls) is False


@pytest.mark.asyncio
async def test_chat_handler_routes_pasted_funding_urls_to_source_intake(monkeypatch):
    mocked_intake = AsyncMock()
    monkeypatch.setattr(chat_module, "send_source_lead_intake", mocked_intake)

    update = SimpleNamespace(
        message=SimpleNamespace(
            text=(
                "Venture League Pitch Competition Application - March 18th - $1.5M check size\n"
                "https://docs.google.com/forms/d/e/test/viewform"
            ),
            reply_text=AsyncMock(),
        ),
        effective_user=SimpleNamespace(id=1),
    )
    context = SimpleNamespace(
        bot_data={
            "store": SimpleNamespace(
                get_profile_by_telegram_user=AsyncMock(return_value=_profile())
            )
        }
    )

    await chat_module.chat_handler(update, context)

    mocked_intake.assert_awaited_once()
    _, kwargs = mocked_intake.await_args
    assert kwargs["source_urls"] == [
        "https://docs.google.com/forms/d/e/test/viewform"
    ]
