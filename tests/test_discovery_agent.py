from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.agents.discovery import DiscoveryAgent
from src.core.config import Config
from src.core.types import DiscoveryInput


@pytest.mark.asyncio
async def test_discovery_agentic_executes_primary_and_hint_queries(monkeypatch):
    class DummyMultiEngineSearch:
        def __init__(self, config):
            self.available_count = 1

    class DummyOrchestrator:
        def __init__(self, config):
            self.calls: list[tuple[str, list[str] | None]] = []

        async def search(self, query: str, category=None, sources=None):
            self.calls.append((query, list(sources) if sources else None))
            return (
                [
                    {
                        "organization": query,
                        "program": f"{query} Program",
                        "apply_url": f"https://example.com/{len(self.calls)}",
                    }
                ],
                [f"https://example.com/{len(self.calls)}"],
            )

    dummy_orchestrator = DummyOrchestrator(Config())
    monkeypatch.setattr("src.search.multi_engine.MultiEngineSearch", DummyMultiEngineSearch)
    monkeypatch.setattr(
        "src.search.orchestrator.SearchOrchestrator",
        lambda config: dummy_orchestrator,
    )

    agent = DiscoveryAgent(store=SimpleNamespace(), config=Config())
    result = await agent.run(
        DiscoveryInput(
            query="ai grants",
            sources=["https://seed.example/program"],
            hint_queries=["Nitro Accelerator apply official", "ai grants"],
        )
    )

    assert result.success is True
    assert dummy_orchestrator.calls == [
        ("ai grants", ["https://seed.example/program"]),
        ("Nitro Accelerator apply official", None),
    ]
    assert len(result.data["raw_opportunities"]) == 2
