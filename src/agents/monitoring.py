"""
Funding Intelligence Agent — Monitoring Agent.

AGENTS_SPEC.md Agent 6 구현. core.md M2 마일스톤 대응.

재검증 주기 (PRD §13):
  deadline ≤ 14일  → 6시간
  status = open    → 24시간
  status = unknown → 12시간
  status = closed  → 72시간

변경 감지: deadline, status, apply_url, budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from src.agents.base_agent import BaseAgent
from src.core.errors import MonitoringError
from src.core.types import (
    AgentResult,
    Opportunity,
    OpportunityStatus,
    generate_id,
)

logger = structlog.get_logger()

# ============================================================
# 재검증 간격 (시간 단위)
# ============================================================

REVERIFY_INTERVALS: dict[str, int] = {
    "deadline_soon": 6,    # deadline ≤ 14일
    "open": 24,
    "unknown": 12,
    "closed": 72,
    "rolling": 24,
    "upcoming": 48,
    "default": 24,
}


def _get_reverify_interval(opp: Opportunity) -> int:
    """opportunity 상태에 따른 재검증 간격 (시간)."""
    # deadline ≤ 14일이면 6시간
    if opp.deadline_at:
        days_left = (opp.deadline_at - datetime.now(timezone.utc)).days
        if 0 <= days_left <= 14:
            return REVERIFY_INTERVALS["deadline_soon"]

    status_key = opp.status.value if opp.status else "default"
    return REVERIFY_INTERVALS.get(status_key, REVERIFY_INTERVALS["default"])


# ============================================================
# I/O 타입
# ============================================================

@dataclass
class MonitoringInput:
    """Monitoring Agent 입력."""
    max_checks: int = 50        # 한 번에 최대 체크 수
    force_all: bool = False     # True면 간격 무시하고 전부 체크


@dataclass
class MonitoringOutput:
    """Monitoring Agent 출력."""
    total_checked: int = 0
    total_changed: int = 0
    changes: list[dict] = field(default_factory=list)
    social_alert_candidates: list[dict] = field(default_factory=list)
    checked_at: str = ""


# ============================================================
# Monitoring Agent
# ============================================================

class MonitoringAgent(BaseAgent):
    """기회 재검증 + 변경 감지 Agent."""

    async def _execute(self, input_data: Any) -> AgentResult:
        if input_data is None:
            input_data = MonitoringInput()

        if not isinstance(input_data, MonitoringInput):
            raise MonitoringError(
                message="input_data must be MonitoringInput",
                fix="MonitoringInput() 형태로 전달",
                context={"received": type(input_data).__name__},
            )

        self.log.info("monitoring.start", max_checks=input_data.max_checks)

        # 1. 재검증 대상 선정
        candidates = await self._select_candidates(
            input_data.max_checks,
            input_data.force_all,
        )

        if not candidates:
            return AgentResult(
                success=True,
                data=MonitoringOutput(
                    checked_at=datetime.now(timezone.utc).isoformat(),
                ).__dict__,
            )

        # 2. 각 기회 재검증
        changes: list[dict] = []

        for opp in candidates:
            try:
                change = await self._check_opportunity(opp)
                if change:
                    changes.append(change)
            except Exception as e:
                self.log.warning(
                    "monitoring.check_error",
                    opportunity_id=opp.id,
                    error=str(e),
                )
                continue

        output = MonitoringOutput(
            total_checked=len(candidates),
            total_changed=len(changes),
            changes=changes,
            social_alert_candidates=await self.store.list_social_alert_candidates(limit=20),
            checked_at=datetime.now(timezone.utc).isoformat(),
        )

        self.log.info(
            "monitoring.complete",
            checked=len(candidates),
            changed=len(changes),
        )

        return AgentResult(success=True, data=output.__dict__)

    async def _select_candidates(
        self, max_checks: int, force_all: bool
    ) -> list[Opportunity]:
        """재검증 대상 선정.

        마지막 검증 시점 + 상태별 간격을 비교해서
        재검증이 필요한 기회만 선택.
        """
        # 모든 기회 조회
        all_opps = await self.store.list_opportunities(limit=500)

        if force_all:
            return all_opps[:max_checks]

        now = datetime.now(timezone.utc)
        candidates: list[Opportunity] = []

        for opp in all_opps:
            interval_hours = _get_reverify_interval(opp)
            threshold = now - timedelta(hours=interval_hours)

            # updated_at이 threshold보다 오래되면 재검증 대상
            if opp.updated_at is None or opp.updated_at < threshold:
                candidates.append(opp)

            if len(candidates) >= max_checks:
                break

        self.log.info(
            "monitoring.candidates_selected",
            total=len(all_opps),
            selected=len(candidates),
        )
        return candidates

    async def _check_opportunity(self, opp: Opportunity) -> dict | None:
        """개별 기회 재검증. 변경 감지 시 dict 반환."""
        if not opp.apply_url:
            return None

        # SmartFetcher로 apply_url 재방문
        from src.search.fetcher import SmartFetcher

        fetcher = SmartFetcher(self.config)
        pages = await fetcher.fetch_many([opp.apply_url], max_pages=1)

        if not pages or not pages[0].success:
            # URL 접근 불가 → apply_url 비활성화 감지
            change = {
                "opportunity_id": opp.id,
                "change_type": "apply_url_unreachable",
                "old_value": opp.apply_url,
                "new_value": None,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            }

            # apply_url을 None으로 업데이트하진 않음 (일시적 장애일 수 있음)
            # 대신 change_event만 기록
            self.log.warning(
                "monitoring.url_unreachable",
                opportunity_id=opp.id,
                url=opp.apply_url,
            )
            return change

        # 페이지 내용에서 상태 변경 감지 (간단 버전)
        page = pages[0]
        content_lower = page.content.lower()

        changes: dict | None = None

        # closed 감지
        closed_keywords = [
            "applications closed", "no longer accepting",
            "program ended", "deadline passed",
            "submissions closed", "not accepting",
        ]
        if (
            opp.status != OpportunityStatus.CLOSED
            and any(kw in content_lower for kw in closed_keywords)
        ):
            changes = {
                "opportunity_id": opp.id,
                "change_type": "status_changed",
                "old_value": opp.status.value,
                "new_value": "closed",
                "detected_at": datetime.now(timezone.utc).isoformat(),
            }

            # DB 업데이트
            await self.store.update_opportunity(
                opp.id,
                status=OpportunityStatus.CLOSED,
            )

            self.log.info(
                "monitoring.status_changed",
                opportunity_id=opp.id,
                old_status=opp.status.value,
                new_status="closed",
            )

        # updated_at 갱신 (검증 시점 기록)
        await self.store.update_opportunity(
            opp.id,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        return changes
