from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import src.interface.discovery_runtime as runtime
from src.core.pipeline import PipelineResult


def test_build_source_query_hint_strips_urls():
    hint = runtime.build_source_query_hint(
        "Apply here https://tally.so/r/aQdj2W for Alliance accelerator"
    )
    assert "https://tally.so/r/aQdj2W" not in hint
    assert "Alliance accelerator" in hint


@pytest.mark.asyncio
async def test_run_discovery_with_status_returns_execution(monkeypatch):
    status_message = SimpleNamespace(edit_text=AsyncMock())
    update = SimpleNamespace(
        message=SimpleNamespace(reply_text=AsyncMock(return_value=status_message))
    )
    captured: dict[str, object] = {}

    class DummyPipeline:
        def __init__(self, store, cfg=None):
            self.store = store
            self.cfg = cfg

        async def run_discovery_pipeline(self, **kwargs):
            captured.update(kwargs)
            return PipelineResult(
                total_discovered=2,
                total_ingested=1,
                total_verified=1,
            )

    monkeypatch.setattr(runtime, "FundingPipeline", DummyPipeline)

    execution = await runtime.run_discovery_with_status(
        update,
        store=SimpleNamespace(),
        query="ai grants",
        hint_queries=["Nitro Accelerator apply official"],
        start_text="searching",
        success_text_builder=lambda result, elapsed: f"done {result.total_discovered}",
        error_prefix="검색 중 오류 발생",
    )

    assert execution is not None
    assert execution.result.total_discovered == 2
    assert captured["hint_queries"] == ["Nitro Accelerator apply official"]
    status_message.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_discovery_with_status_handles_pipeline_error(monkeypatch):
    status_message = SimpleNamespace(edit_text=AsyncMock())
    update = SimpleNamespace(
        message=SimpleNamespace(reply_text=AsyncMock(return_value=status_message))
    )

    class DummyPipeline:
        def __init__(self, store, cfg=None):
            self.store = store
            self.cfg = cfg

        async def run_discovery_pipeline(self, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(runtime, "FundingPipeline", DummyPipeline)

    execution = await runtime.run_discovery_with_status(
        update,
        store=SimpleNamespace(),
        query="ai grants",
        start_text="searching",
        success_text_builder=lambda result, elapsed: "done",
        error_prefix="검색 중 오류 발생",
    )

    assert execution is None
    status_message.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_source_lead_intake_reports_no_extractable_programs(monkeypatch):
    status_message = SimpleNamespace(edit_text=AsyncMock())
    reply_text = AsyncMock()
    update = SimpleNamespace(
        message=SimpleNamespace(reply_text=reply_text),
        effective_user=SimpleNamespace(id=1),
    )
    store = SimpleNamespace(
        get_profile_by_telegram_user=AsyncMock(return_value=None)
    )
    context = SimpleNamespace(bot_data={"store": store})

    async def fake_run_discovery_with_status(*args, **kwargs):
        return runtime.DiscoveryExecution(
            result=PipelineResult(total_discovered=0),
            elapsed_seconds=0.4,
            status_message=status_message,
        )

    monkeypatch.setattr(
        runtime,
        "run_discovery_with_status",
        fake_run_discovery_with_status,
    )

    await runtime.send_source_lead_intake(
        update,
        context,
        source_urls=["https://docs.google.com/forms/d/e/test/viewform"],
        message_text="lead",
    )

    reply_text.assert_awaited_once()
