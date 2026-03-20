from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import src.interface.handlers.search_handler as search_module
from src.interface.discovery_runtime import DiscoveryExecution
from src.core.pipeline import PipelineResult
from src.search.research_reflection import ReflectionSeeds


@pytest.mark.asyncio
async def test_search_command_delegates_to_shared_runtime(monkeypatch):
    mocked_runtime = AsyncMock(
        return_value=DiscoveryExecution(
            result=PipelineResult(total_discovered=1, total_ingested=1),
            elapsed_seconds=0.8,
            status_message=SimpleNamespace(edit_text=AsyncMock()),
        )
    )
    mocked_send_results = AsyncMock()
    monkeypatch.setattr(search_module, "run_discovery_with_status", mocked_runtime)
    monkeypatch.setattr(search_module, "send_search_results", mocked_send_results)
    monkeypatch.setattr(
        search_module,
        "resolve_runtime_reflection_seeds",
        lambda **kwargs: ReflectionSeeds(
            search_hints=["Nitro Accelerator apply official"],
            bootstrap_terms=["Nitro Accelerator"],
        ),
    )

    class DummyReferenceEngine:
        def bootstrap_sources(self, profile, top_n=8, priority_terms=None):
            return ["https://nitroacc.xyz/apply"]

    monkeypatch.setattr(search_module, "ReferenceDataEngine", DummyReferenceEngine)

    store = SimpleNamespace(
        get_profile_by_telegram_user=AsyncMock(
            return_value=SimpleNamespace(
                id="cp_1",
                target_ecosystems=["Monad"],
                projects=[{"name": "HOOT"}],
                company_name="HOOT Labs",
            )
        )
    )
    update = SimpleNamespace(
        message=SimpleNamespace(reply_text=AsyncMock()),
        effective_user=SimpleNamespace(id=1),
    )
    context = SimpleNamespace(args=["AI", "grants"], bot_data={"store": store})

    await search_module.search_command(update, context)

    mocked_runtime.assert_awaited_once()
    _, kwargs = mocked_runtime.await_args
    assert kwargs["query"] == "AI grants"
    assert kwargs["hint_queries"] == ["Nitro Accelerator apply official"]
    assert kwargs["source_urls"] == ["https://nitroacc.xyz/apply"]
    mocked_send_results.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_command_shows_usage_without_args():
    update = SimpleNamespace(
        message=SimpleNamespace(reply_text=AsyncMock()),
        effective_user=SimpleNamespace(id=1),
    )
    context = SimpleNamespace(args=[], bot_data={"store": SimpleNamespace()})

    await search_module.search_command(update, context)

    update.message.reply_text.assert_awaited_once()
