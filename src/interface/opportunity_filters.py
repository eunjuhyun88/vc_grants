"""
Funding Intelligence Agent — user-facing opportunity filters.

Renderer 수준 숨김이 아니라, user-facing surface에 올라가기 전
"지금 실제로 낼 수 있는 것"만 남기기 위한 공통 필터를 둔다.
"""

from __future__ import annotations

from typing import Any

from src.research.dossier_builder import is_snapshot_current

ACTIONABLE_STATUSES = {"open", "rolling", "upcoming"}
MIN_ACTIONABLE_CONFIDENCE = 0.75


def is_actionable_card(card: Any) -> bool:
    """사용자에게 바로 보여줄 수 있는 actionable row만 통과시킨다."""
    if not is_snapshot_current(card):
        return False

    status = str(getattr(card, "status", "") or "").strip().lower()
    if status not in ACTIONABLE_STATUSES:
        return False

    apply_url = str(getattr(card, "apply_url", "") or "").strip()
    if not apply_url:
        return False

    confidence = getattr(card, "confidence", 0.0) or 0.0
    try:
        if float(confidence) < MIN_ACTIONABLE_CONFIDENCE:
            return False
    except (TypeError, ValueError):
        return False

    return True


def filter_current_cards(cards: list[Any]) -> list[Any]:
    """User-facing surface에서는 current + actionable row만 통과시킨다."""
    return [card for card in cards if is_actionable_card(card)]
