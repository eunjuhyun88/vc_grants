"""
Funding Intelligence Agent — BaseAgent 추상 클래스.

모든 Agent는 이 클래스를 상속하며, run() → _execute() 패턴을 따른다.
- run(): 타이밍 + 에러 래핑 + 로깅 (final)
- _execute(): 실제 비즈니스 로직 (subclass 구현)
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import structlog

from src.core.config import Config
from src.core.errors import AgentError
from src.core.types import AgentResult
from src.db.entity_store import EntityStore

logger = structlog.get_logger()


class BaseAgent(ABC):
    """Agent 추상 기반 클래스."""

    def __init__(self, store: EntityStore, config: Config) -> None:
        self.store = store
        self.config = config
        self.log = logger.bind(agent=self.__class__.__name__)

    async def run(self, input_data: Any = None) -> AgentResult:
        """Agent 실행 진입점. 타이밍 + 에러 래핑."""
        start = time.monotonic()
        self.log.info("agent.start", input_type=type(input_data).__name__)

        try:
            result = await self._execute(input_data)
            elapsed = (time.monotonic() - start) * 1000
            result.elapsed_ms = elapsed
            self.log.info(
                "agent.complete",
                success=result.success,
                elapsed_ms=round(elapsed, 1),
            )
            return result

        except AgentError as e:
            elapsed = (time.monotonic() - start) * 1000
            self.log.error(
                "agent.error",
                code=e.code,
                message=e.message,
                elapsed_ms=round(elapsed, 1),
            )
            return AgentResult(
                success=False,
                error=f"[{e.code}] {e.message}",
                elapsed_ms=elapsed,
            )

        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            self.log.error(
                "agent.unexpected_error",
                error=str(e),
                elapsed_ms=round(elapsed, 1),
            )
            return AgentResult(
                success=False,
                error=f"[UNEXPECTED] {e}",
                elapsed_ms=elapsed,
            )

    @abstractmethod
    async def _execute(self, input_data: Any) -> AgentResult:
        """서브클래스에서 구현할 실제 비즈니스 로직."""
        ...
