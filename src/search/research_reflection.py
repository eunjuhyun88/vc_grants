from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def _dedup_strings(values: list[str], limit: int | None = None) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.lower().strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(value)
        if limit is not None and len(deduped) >= limit:
            break
    return deduped


@dataclass(frozen=True)
class CaseReflection:
    case_id: str
    goal_type: str
    recovery_mode: str
    progress_score: float
    goal_met: bool
    actions: list[str] = field(default_factory=list)
    search_hints: list[str] = field(default_factory=list)
    bootstrap_terms: list[str] = field(default_factory=list)
    target_entities: list[str] = field(default_factory=list)
    target_ecosystems: list[str] = field(default_factory=list)
    matched_anchors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResearchReflection:
    version: int = 1
    generated_at: str = ""
    source_report_type: str = ""
    overall_goal_met: bool = False
    promoted_actions: list[str] = field(default_factory=list)
    case_reflections: list[CaseReflection] = field(default_factory=list)


@dataclass(frozen=True)
class ReflectionSeeds:
    actions: list[str] = field(default_factory=list)
    search_hints: list[str] = field(default_factory=list)
    bootstrap_terms: list[str] = field(default_factory=list)


def _select_best_run(case_report: dict[str, Any]) -> dict[str, Any]:
    runs = list(case_report.get("runs") or [])
    if not runs:
        return {}
    scored_runs = sorted(
        runs,
        key=lambda run: (
            bool((run.get("goal") or {}).get("met", False)),
            float(run.get("progress_score", 0.0)),
            len(run.get("top_results") or []),
        ),
        reverse=True,
    )
    return scored_runs[0]


def build_case_reflection(
    case_report: dict[str, Any],
    *,
    max_search_hints: int = 12,
    max_bootstrap_terms: int = 8,
) -> CaseReflection:
    best_run = _select_best_run(case_report)
    best_actions = list(best_run.get("applied_actions") or [])
    recommended_actions = list(case_report.get("recommended_actions") or [])
    actions = _dedup_strings(best_actions + recommended_actions)
    matched_anchors = [
        str(anchor)
        for anchor in (case_report.get("final_metrics") or {}).get("matched_anchors", [])
        if str(anchor).strip()
    ]
    search_hints = _dedup_strings(
        list(best_run.get("search_hints") or []) + matched_anchors,
        limit=max_search_hints,
    )
    bootstrap_terms = _dedup_strings(
        list(best_run.get("bootstrap_terms") or []) + matched_anchors,
        limit=max_bootstrap_terms,
    )

    return CaseReflection(
        case_id=str(case_report.get("case_id") or ""),
        goal_type=str(case_report.get("goal_type") or ""),
        recovery_mode=str(case_report.get("recovery_mode") or ""),
        progress_score=float(case_report.get("final_progress_score", 0.0)),
        goal_met=bool((case_report.get("goal") or {}).get("met", False))
        or bool((best_run.get("goal") or {}).get("met", False)),
        actions=actions,
        search_hints=search_hints,
        bootstrap_terms=bootstrap_terms,
        target_entities=[
            str(value)
            for value in (case_report.get("target_entities") or [])
            if str(value).strip()
        ],
        target_ecosystems=[
            str(value)
            for value in (case_report.get("target_ecosystems") or [])
            if str(value).strip()
        ],
        matched_anchors=matched_anchors,
    )


def build_research_reflection(
    report: dict[str, Any],
    *,
    max_search_hints: int = 12,
    max_bootstrap_terms: int = 8,
) -> ResearchReflection:
    case_reports = list(report.get("cases") or [])
    case_reflections = [
        build_case_reflection(
            case_report,
            max_search_hints=max_search_hints,
            max_bootstrap_terms=max_bootstrap_terms,
        )
        for case_report in case_reports
    ]
    promoted_actions = _dedup_strings(
        list(report.get("recommended_actions") or [])
        + [
            action
            for case_reflection in case_reflections
            if case_reflection.goal_met
            for action in case_reflection.actions
        ]
    )
    return ResearchReflection(
        generated_at=str(report.get("generated_at") or ""),
        source_report_type=str(report.get("report_type") or ""),
        overall_goal_met=bool(report.get("overall_goal_met", False)),
        promoted_actions=promoted_actions,
        case_reflections=case_reflections,
    )


def resolve_reflection_seeds(
    reflection: ResearchReflection | dict[str, Any] | None,
    *,
    case_id: str = "",
    goal_type: str = "",
    target_entities: list[str] | None = None,
    target_ecosystems: list[str] | None = None,
    max_search_hints: int = 12,
    max_bootstrap_terms: int = 8,
) -> ReflectionSeeds:
    if reflection is None:
        return ReflectionSeeds()

    if isinstance(reflection, dict):
        reflection = load_research_reflection_from_data(reflection)

    entity_keys = {value.lower().strip() for value in (target_entities or []) if value}
    ecosystem_keys = {value.lower().strip() for value in (target_ecosystems or []) if value}

    matched_cases: list[CaseReflection] = []
    for case_reflection in reflection.case_reflections:
        case_entity_keys = {
            value.lower().strip() for value in case_reflection.target_entities
        }
        case_ecosystem_keys = {
            value.lower().strip() for value in case_reflection.target_ecosystems
        }
        case_match = case_id and case_reflection.case_id == case_id
        goal_match = goal_type and case_reflection.goal_type == goal_type
        entity_match = bool(entity_keys and case_entity_keys & entity_keys)
        ecosystem_match = bool(ecosystem_keys and case_ecosystem_keys & ecosystem_keys)
        cross_scope_match = bool(
            (ecosystem_keys and case_entity_keys & ecosystem_keys)
            or (entity_keys and case_ecosystem_keys & entity_keys)
        )
        if case_match or goal_match or entity_match or ecosystem_match or cross_scope_match:
            matched_cases.append(case_reflection)

    return ReflectionSeeds(
        actions=_dedup_strings(
            list(reflection.promoted_actions)
            + [action for case_reflection in matched_cases for action in case_reflection.actions]
        ),
        search_hints=_dedup_strings(
            [hint for case_reflection in matched_cases for hint in case_reflection.search_hints],
            limit=max_search_hints,
        ),
        bootstrap_terms=_dedup_strings(
            [term for case_reflection in matched_cases for term in case_reflection.bootstrap_terms],
            limit=max_bootstrap_terms,
        ),
    )


def load_research_reflection_from_data(data: dict[str, Any]) -> ResearchReflection:
    case_reflections = [
        CaseReflection(
            case_id=str(item.get("case_id") or ""),
            goal_type=str(item.get("goal_type") or ""),
            recovery_mode=str(item.get("recovery_mode") or ""),
            progress_score=float(item.get("progress_score", 0.0)),
            goal_met=bool(item.get("goal_met", False)),
            actions=[str(value) for value in (item.get("actions") or [])],
            search_hints=[str(value) for value in (item.get("search_hints") or [])],
            bootstrap_terms=[str(value) for value in (item.get("bootstrap_terms") or [])],
            target_entities=[str(value) for value in (item.get("target_entities") or [])],
            target_ecosystems=[str(value) for value in (item.get("target_ecosystems") or [])],
            matched_anchors=[str(value) for value in (item.get("matched_anchors") or [])],
        )
        for item in (data.get("case_reflections") or [])
        if isinstance(item, dict)
    ]
    return ResearchReflection(
        version=int(data.get("version", 1) or 1),
        generated_at=str(data.get("generated_at") or ""),
        source_report_type=str(data.get("source_report_type") or ""),
        overall_goal_met=bool(data.get("overall_goal_met", False)),
        promoted_actions=[str(value) for value in (data.get("promoted_actions") or [])],
        case_reflections=case_reflections,
    )


def load_research_reflection(path: Path | str) -> ResearchReflection:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Reflection payload must be a JSON object")
    return load_research_reflection_from_data(payload)


def write_research_reflection(path: Path | str, reflection: ResearchReflection) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(asdict(reflection), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target
