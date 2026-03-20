"""
Funding Intelligence Agent — 에러 클래스.

모든 에러는 복구 방법을 포함해야 한다.
금지: raise ValueError("invalid input")
필수: raise AgentError(code="...", message="...", fix="...", context={...})
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class AgentError(Exception):
    """Agent 시스템 공통 에러. 복구 정보 포함 필수."""

    def __init__(
        self,
        code: str,
        message: str,
        fix: str,
        context: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.fix = fix
        self.context = context or {}
        super().__init__(
            f"[{code}] {message}\n"
            f"수정: {fix}\n"
            f"컨텍스트: {self.context}"
        )


class StoreError(AgentError):
    """DB 작업 에러."""

    def __init__(self, message: str, fix: str, context: dict[str, Any] | None = None):
        super().__init__(
            code="STORE_ERROR",
            message=message,
            fix=fix,
            context=context,
        )


class DiscoveryError(AgentError):
    """Discovery Agent 에러."""

    def __init__(self, message: str, fix: str, context: dict[str, Any] | None = None):
        super().__init__(
            code="DISCOVERY_ERROR",
            message=message,
            fix=fix,
            context=context,
        )


class VerificationError(AgentError):
    """Verification Agent 에러."""

    def __init__(self, message: str, fix: str, context: dict[str, Any] | None = None):
        super().__init__(
            code="VERIFICATION_ERROR",
            message=message,
            fix=fix,
            context=context,
        )


class MatchingError(AgentError):
    """Matching Agent 에러."""

    def __init__(self, message: str, fix: str, context: dict[str, Any] | None = None):
        super().__init__(
            code="MATCHING_ERROR",
            message=message,
            fix=fix,
            context=context,
        )


class PipelineError(AgentError):
    """Pipeline 오케스트레이션 에러."""

    def __init__(self, message: str, fix: str, context: dict[str, Any] | None = None):
        super().__init__(
            code="PIPELINE_ERROR",
            message=message,
            fix=fix,
            context=context,
        )


class SearchError(AgentError):
    """Search 모듈 에러 (Agentic RAG)."""

    def __init__(self, message: str, fix: str, context: dict[str, Any] | None = None):
        super().__init__(
            code="SEARCH_ERROR",
            message=message,
            fix=fix,
            context=context,
        )


class MonitoringError(AgentError):
    """Monitoring Agent 에러."""

    def __init__(self, message: str, fix: str, context: dict[str, Any] | None = None):
        super().__init__(
            code="MONITORING_ERROR",
            message=message,
            fix=fix,
            context=context,
        )
