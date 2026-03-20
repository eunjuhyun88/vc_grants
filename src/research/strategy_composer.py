from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.research.dossier_builder import is_snapshot_current

ACTIONABLE_STATUSES = {"open", "rolling", "upcoming"}


@dataclass
class StrategyEntry:
    organization: str
    program: str
    status: str
    apply_url: str | None
    official_url: str | None
    description: str | None
    funding_range: str | None
    status_note: str | None
    why_fit: str
    next_action: str
    ready: bool


def compute_output_readiness(snapshot: Any) -> bool:
    return bool(
        is_snapshot_current(snapshot)
        and
        getattr(snapshot, "organization", "")
        and getattr(snapshot, "program", "")
        and getattr(snapshot, "apply_url", None)
        and getattr(snapshot, "status", "") in ACTIONABLE_STATUSES
        and getattr(snapshot, "why_fit", "")
        and getattr(snapshot, "next_action", "")
    )


def compose_actionable_entries(project_name: str, snapshots: list[Any], top_n: int = 10) -> list[StrategyEntry]:
    entries: list[StrategyEntry] = []
    for snapshot in snapshots[:top_n]:
        entries.append(
            StrategyEntry(
                organization=getattr(snapshot, "organization", ""),
                program=getattr(snapshot, "program", ""),
                status=getattr(snapshot, "status", ""),
                apply_url=getattr(snapshot, "apply_url", None),
                official_url=getattr(snapshot, "source_url", None),
                description=getattr(snapshot, "description", None),
                funding_range=getattr(snapshot, "budget", None),
                status_note=getattr(snapshot, "status_note", None),
                why_fit=(getattr(snapshot, "why_fit", "") or "").strip(),
                next_action=(getattr(snapshot, "next_action", "") or "").strip(),
                ready=compute_output_readiness(snapshot),
            )
        )
    return entries


def compute_reason_coverage(entries: list[StrategyEntry]) -> float:
    if not entries:
        return 0.0
    return round(sum(1 for entry in entries if entry.why_fit) / len(entries), 4)


def compute_next_action_coverage(entries: list[StrategyEntry]) -> float:
    if not entries:
        return 0.0
    return round(sum(1 for entry in entries if entry.next_action) / len(entries), 4)


def compute_output_ready_count(entries: list[StrategyEntry]) -> int:
    return sum(1 for entry in entries if entry.ready)
