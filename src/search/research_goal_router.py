from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GoalType(str, Enum):
    ACTIONABLE_STRATEGY = "actionable_strategy"
    FUNDING_MAP = "funding_map"
    ORG_DOSSIER = "org_dossier"
    COHORT_RECALL = "cohort_recall"
    GRANT_COVERAGE = "grant_coverage"


class RecoveryMode(str, Enum):
    ACTIONABLE_RECOVERY = "actionable_recovery"
    ECOSYSTEM_COVERAGE_RECOVERY = "ecosystem_coverage_recovery"
    DOSSIER_RECOVERY = "dossier_recovery"
    COHORT_RECOVERY = "cohort_recovery"
    GRANT_RECOVERY = "grant_recovery"


@dataclass(frozen=True)
class GoalRoute:
    goal_type: GoalType
    recovery_mode: RecoveryMode
    prioritized_metrics: list[str] = field(default_factory=list)
    target_ecosystems: list[str] = field(default_factory=list)
    target_entities: list[str] = field(default_factory=list)


_GOAL_DEFAULTS: dict[GoalType, tuple[RecoveryMode, list[str]]] = {
    GoalType.ACTIONABLE_STRATEGY: (
        RecoveryMode.ACTIONABLE_RECOVERY,
        [
            "output_ready_top10_count",
            "actionable_top10_count",
            "cohort_or_builder_in_top10_count",
            "why_fit_coverage",
            "next_action_coverage",
        ],
    ),
    GoalType.FUNDING_MAP: (
        RecoveryMode.ECOSYSTEM_COVERAGE_RECOVERY,
        [
            "funding_map_coverage",
            "tier1_ecosystem_count",
            "tier2_ecosystem_count",
            "profile_specific_recall",
        ],
    ),
    GoalType.ORG_DOSSIER: (
        RecoveryMode.DOSSIER_RECOVERY,
        [
            "dossier_fact_completeness",
            "dossier_program_count",
            "dossier_matched_program_count",
            "official_source_ratio",
        ],
    ),
    GoalType.COHORT_RECALL: (
        RecoveryMode.COHORT_RECOVERY,
        [
            "matched_anchor_count",
            "missing_anchor_count",
            "actionable_top10_count",
            "cohort_or_builder_in_top10_count",
        ],
    ),
    GoalType.GRANT_COVERAGE: (
        RecoveryMode.GRANT_RECOVERY,
        [
            "profile_specific_recall",
            "actionable_top10_count",
            "high_fit_verified_count",
        ],
    ),
}


def normalize_goal_type(value: str | None) -> GoalType:
    if not value:
        return GoalType.COHORT_RECALL
    normalized = value.strip().lower()
    for item in GoalType:
        if item.value == normalized:
            return item
    return GoalType.COHORT_RECALL


def normalize_recovery_mode(value: str | None, goal_type: GoalType) -> RecoveryMode:
    if value:
        normalized = value.strip().lower()
        for item in RecoveryMode:
            if item.value == normalized:
                return item
    return _GOAL_DEFAULTS[goal_type][0]


def resolve_goal_route(case_cfg: dict[str, Any]) -> GoalRoute:
    goal_type = normalize_goal_type(case_cfg.get("goal_type"))
    recovery_mode = normalize_recovery_mode(case_cfg.get("recovery_mode"), goal_type)
    prioritized_metrics = list(
        case_cfg.get("prioritized_metrics") or _GOAL_DEFAULTS[goal_type][1]
    )
    target_ecosystems = [str(v) for v in (case_cfg.get("target_ecosystems") or [])]

    target_entities: list[str] = []
    target_org = case_cfg.get("target_org")
    if target_org:
        target_entities.append(str(target_org))
    for anchor in case_cfg.get("anchors") or []:
        if isinstance(anchor, str):
            target_entities.append(anchor)
        elif isinstance(anchor, dict) and anchor.get("name"):
            target_entities.append(str(anchor["name"]))

    dedup_entities: list[str] = []
    seen = set()
    for entity in target_entities:
        key = entity.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        dedup_entities.append(entity)

    return GoalRoute(
        goal_type=goal_type,
        recovery_mode=recovery_mode,
        prioritized_metrics=prioritized_metrics,
        target_ecosystems=target_ecosystems,
        target_entities=dedup_entities,
    )


def goal_specific_actions(
    goal_route: GoalRoute,
    failed_metrics: list[str],
    metrics: dict[str, Any],
) -> list[str]:
    actions: list[str] = []
    goal_type = goal_route.goal_type

    if goal_type == GoalType.ACTIONABLE_STRATEGY:
        if (
            "output_ready_top10_count" in failed_metrics
            or "actionable_top10_count" in failed_metrics
        ):
            actions.append("recover_actionable_mix")
        if "cohort_or_builder_in_top10_count" in failed_metrics:
            actions.append("recover_builder_and_cohort_mix")
        if (
            "why_fit_coverage" in failed_metrics
            or "next_action_coverage" in failed_metrics
        ):
            actions.append("improve_reason_and_next_action_coverage")

    elif goal_type == GoalType.FUNDING_MAP:
        if (
            "funding_map_coverage" in failed_metrics
            or "tier1_ecosystem_count" in failed_metrics
            or "tier2_ecosystem_count" in failed_metrics
        ):
            actions.append("expand_ecosystem_graph_queries")
            actions.append("recover_missing_ecosystems")

    elif goal_type == GoalType.ORG_DOSSIER:
        if "dossier_fact_completeness" in failed_metrics:
            actions.append("expand_org_program_queries")
            actions.append("expand_official_docs_queries")
        if (
            "dossier_matched_program_count" in failed_metrics
            or "dossier_program_count" in failed_metrics
        ):
            actions.append("expand_partner_and_mentor_queries")

    elif goal_type == GoalType.COHORT_RECALL:
        actions.append("expand_target_ecosystem_and_vc_cohort_queries")
        if metrics.get("cohort_or_builder_in_top10_count", 0) < 2:
            actions.append("recover_builder_and_cohort_mix")

    elif goal_type == GoalType.GRANT_COVERAGE:
        actions.append("expand_grant_family_queries")

    deduped: list[str] = []
    for action in actions:
        if action not in deduped:
            deduped.append(action)
    return deduped
