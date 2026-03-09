"""
BaseAgent 테스트 — run/execute 패턴, 타이밍, 에러 래핑 검증.

실행: pytest tests/test_base_agent.py -v
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from src.agents.base_agent import BaseAgent
from src.core.config import Config
from src.core.errors import AgentError
from src.core.types import AgentResult
from src.db.entity_store import EntityStore


# ============================================================
# 테스트용 Agent 구현
# ============================================================


class SuccessAgent(BaseAgent):
    """성공 케이스."""

    async def _execute(self, input_data: Any) -> AgentResult:
        return AgentResult(success=True, data={"result": "ok"})


class FailAgent(BaseAgent):
    """AgentError 발생."""

    async def _execute(self, input_data: Any) -> AgentResult:
        raise AgentError(
            code="TEST_ERROR",
            message="Test error occurred",
            fix="Fix the test",
        )


class CrashAgent(BaseAgent):
    """예상치 못한 에러 발생."""

    async def _execute(self, input_data: Any) -> AgentResult:
        raise ValueError("unexpected crash")


class SlowAgent(BaseAgent):
    """시간 걸리는 Agent."""

    async def _execute(self, input_data: Any) -> AgentResult:
        await asyncio.sleep(0.05)
        return AgentResult(success=True, data={"slow": True})


# ============================================================
# Fixtures
# ============================================================


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    """테스트용 EntityStore."""
    db_path = tmp_path / "test_agent.db"
    async with EntityStore(db_path) as s:
        await s.init_schema()
        yield s


@pytest.fixture
def cfg():
    """테스트 설정."""
    return Config()


# ============================================================
# Tests
# ============================================================


@pytest.mark.asyncio
async def test_success_agent(store: EntityStore, cfg: Config):
    """성공 시 AgentResult 반환."""
    agent = SuccessAgent(store, cfg)
    result = await agent.run(None)

    assert result.success is True
    assert result.data == {"result": "ok"}
    assert result.error is None
    assert result.elapsed_ms > 0


@pytest.mark.asyncio
async def test_fail_agent_wraps_error(store: EntityStore, cfg: Config):
    """AgentError는 success=False + error message로 래핑."""
    agent = FailAgent(store, cfg)
    result = await agent.run(None)

    assert result.success is False
    assert "TEST_ERROR" in result.error
    assert result.elapsed_ms > 0


@pytest.mark.asyncio
async def test_crash_agent_wraps_unexpected(store: EntityStore, cfg: Config):
    """예상치 못한 에러도 안전하게 래핑."""
    agent = CrashAgent(store, cfg)
    result = await agent.run(None)

    assert result.success is False
    assert "UNEXPECTED" in result.error
    assert "unexpected crash" in result.error
    assert result.elapsed_ms > 0


@pytest.mark.asyncio
async def test_elapsed_ms_tracked(store: EntityStore, cfg: Config):
    """실행 시간이 측정됨."""
    agent = SlowAgent(store, cfg)
    result = await agent.run(None)

    assert result.success is True
    # 50ms sleep → elapsed > 40ms (여유)
    assert result.elapsed_ms >= 40


@pytest.mark.asyncio
async def test_input_data_passed(store: EntityStore, cfg: Config):
    """input_data가 _execute에 전달됨."""

    class EchoAgent(BaseAgent):
        async def _execute(self, input_data: Any) -> AgentResult:
            return AgentResult(success=True, data={"echo": input_data})

    agent = EchoAgent(store, cfg)
    result = await agent.run({"key": "value"})

    assert result.success is True
    assert result.data["echo"] == {"key": "value"}
