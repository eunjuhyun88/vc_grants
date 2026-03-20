#!/usr/bin/env python3
"""
Goal-seeking funding research loop runner.

This is the first runnable evaluation harness for the autoresearch-style
funding discovery loop. It does not mutate production truth. Each run uses a
fresh temporary SQLite database, reuses the existing FundingSearchOrchestrator,
and stops only when the benchmark goals are met or the case-level run budget
is exhausted.

The benchmark file lives at eval/funding_benchmark.yaml. It is currently
stored as JSON-compatible YAML so this runner can load it with the standard
library when PyYAML is not installed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.config import config as base_config
from src.core.profiles import get_default_profile
from src.core.types import CompanyProfile, CompanyStage, MatchingOutput, calculate_days_left
from src.db.entity_store import EntityStore
from src.research.dossier_builder import (
    build_org_dossier,
    build_project_funding_map,
    compute_dossier_fact_completeness,
    compute_funding_map_coverage,
    load_ecosystem_graph,
)
from src.research.strategy_composer import (
    compose_actionable_entries,
    compute_next_action_coverage,
    compute_output_ready_count,
    compute_reason_coverage,
)
from src.search.funding_orchestrator import FundingSearchOrchestrator, FundingSearchResult
from src.search.research_goal_router import GoalRoute, goal_specific_actions, resolve_goal_route
from src.search.research_reflection import (
    ResearchReflection,
    build_research_reflection,
    load_research_reflection,
    load_research_reflection_from_data,
    resolve_reflection_seeds,
    write_research_reflection,
)

ACTIONABLE_STATUSES = {"open", "rolling", "upcoming"}
DEFAULT_BENCHMARK = Path("eval/funding_benchmark.yaml")
DEFAULT_PROGRAM = Path("funding_program.md")
DEFAULT_RESULTS_TSV = Path("output") / "research-evals" / "results.tsv"
DEFAULT_LATEST_REFLECTION = Path("output") / "research-evals" / "latest-reflection.json"
PROGRAM_JSON_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


@dataclass
class RankedSnapshot:
    opportunity_id: str
    organization: str
    program: str
    category: str
    status: str
    apply_url: str | None
    days_left: int | None
    source_tier: int | None
    confidence: float
    fit_score: float
    priority_score: float
    why_fit: str
    next_action: str
    source_chain: list[str]
    updated_at: str | None


@dataclass
class AttemptPolicy:
    mode: str
    search_hints: list[str]
    bootstrap_terms: list[str]
    applied_actions: list[str]


def merge_strings(*groups: list[str], limit: int | None = None) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            normalized = value.lower().strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(value)
            if limit is not None and len(merged) >= limit:
                return merged
    return merged


def build_timestamp_slug(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return current.strftime("%Y%m%d-%H%M%S-%f")


def load_program(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = PROGRAM_JSON_RE.search(text)
    if not match:
        raise ValueError(f"Program file does not contain a JSON code block: {path}")
    data = json.loads(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("Program config must be a JSON object")
    return data


def resolve_program_seed_actions(
    program_cfg: dict[str, Any] | None,
    case_cfg: dict[str, Any],
    goal_route: GoalRoute | None,
    carryover_actions: list[str] | None = None,
) -> list[str]:
    if not program_cfg:
        return merge_strings(list(case_cfg.get("seed_actions") or []), list(carryover_actions or []))

    goal_key = goal_route.goal_type.value if goal_route is not None else str(case_cfg.get("goal_type") or "")
    goal_overrides = program_cfg.get("goal_overrides") or {}
    goal_seed_actions = list(((goal_overrides.get(goal_key) or {}).get("seed_actions") or []))
    global_seed_actions = list(program_cfg.get("seed_actions") or [])
    case_seed_actions = list(case_cfg.get("seed_actions") or [])
    return merge_strings(global_seed_actions, goal_seed_actions, case_seed_actions, list(carryover_actions or []))


def resolve_continuous_config(
    program_cfg: dict[str, Any] | None,
    *,
    max_cycles_override: int | None = None,
    until_goal_or_interrupt: bool = False,
) -> dict[str, Any]:
    continuous_cfg = (program_cfg or {}).get("continuous") or {}
    max_cycles = max_cycles_override
    if max_cycles is None and not until_goal_or_interrupt:
        max_cycles = int(continuous_cfg.get("max_cycles", 3))

    return {
        "max_cycles": max_cycles,
        "plateau_cycles": int(continuous_cfg.get("plateau_cycles", 2)),
        "min_progress_delta": float(continuous_cfg.get("min_progress_delta", 0.01)),
    }


def resolve_reflection_config(program_cfg: dict[str, Any] | None) -> dict[str, Any]:
    reflection_cfg = (program_cfg or {}).get("reflection") or {}
    return {
        "enabled": bool(reflection_cfg),
        "load_path": str(reflection_cfg.get("load_path") or "").strip(),
        "latest_path": str(reflection_cfg.get("latest_path") or DEFAULT_LATEST_REFLECTION).strip(),
        "promote_path": str(reflection_cfg.get("promote_path") or "").strip(),
        "max_search_hints": int(reflection_cfg.get("max_search_hints", 12)),
        "max_bootstrap_terms": int(reflection_cfg.get("max_bootstrap_terms", 8)),
    }


def load_benchmark(path: Path) -> dict[str, Any]:
    """Load JSON-compatible YAML benchmark config."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Benchmark file is empty: {path}")

    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        yaml = None

    if yaml is not None:
        data = yaml.safe_load(text)
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "PyYAML is not installed and the benchmark file is not JSON-compatible YAML. "
                "Install PyYAML or keep eval/funding_benchmark.yaml JSON-compatible."
            ) from exc

    if not isinstance(data, dict):
        raise ValueError("Benchmark root must be an object")
    if not isinstance(data.get("cases"), list) or not data["cases"]:
        raise ValueError("Benchmark must define at least one case")
    return data


def _profile_to_payload(profile: CompanyProfile) -> dict[str, Any]:
    return {
        "id": profile.id,
        "company_name": profile.company_name,
        "stage": profile.stage,
        "sector_tags": list(profile.sector_tags),
        "subsector_tags": list(profile.subsector_tags),
        "projects": list(profile.projects),
        "description": profile.description,
        "geography": profile.geography,
        "funding_goal": profile.funding_goal,
        "product_summary": profile.product_summary,
        "target_ecosystems": list(profile.target_ecosystems),
        "telegram_user_id": profile.telegram_user_id,
        "updated_at": profile.updated_at,
    }


def resolve_profile(profile_key: str, profile_specs: dict[str, Any]) -> CompanyProfile:
    """Resolve a benchmark profile fixture with optional overrides."""
    profile_entry = profile_specs.get(profile_key, {})
    if not isinstance(profile_entry, dict):
        raise ValueError(f"Profile entry must be an object: {profile_key}")

    fixture_name = profile_entry.get("fixture", profile_key)
    base_profile = get_default_profile(fixture_name)
    if base_profile is None:
        raise ValueError(f"Unknown profile fixture: {fixture_name}")

    overrides = profile_entry.get("overrides") or {}
    if not overrides:
        return base_profile

    payload = _profile_to_payload(base_profile)
    payload.update(overrides)
    stage_value = payload.get("stage")
    if isinstance(stage_value, str):
        payload["stage"] = CompanyStage(stage_value)
    return CompanyProfile(**payload)


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").lower().split())


def _matches_anchor(snapshot: RankedSnapshot, anchor: str | dict[str, Any]) -> bool:
    if isinstance(anchor, str):
        terms = [anchor]
    elif isinstance(anchor, dict):
        terms = anchor.get("terms") or [anchor.get("name", "")]
    else:
        return False

    haystack = " | ".join(
        [
            snapshot.organization,
            snapshot.program,
            snapshot.apply_url or "",
            *snapshot.source_chain,
        ]
    )
    haystack_normalized = _normalize_text(haystack)
    return any(_normalize_text(term) in haystack_normalized for term in terms if term)


def _is_actionable(snapshot: RankedSnapshot, confidence_floor: float) -> bool:
    return (
        bool(snapshot.apply_url)
        and snapshot.status in ACTIONABLE_STATUSES
        and snapshot.confidence >= confidence_floor
    )


def _is_high_fit_verified_like(
    snapshot: RankedSnapshot,
    confidence_floor: float,
    fit_floor: float,
    source_tier_max: int,
) -> bool:
    source_tier = snapshot.source_tier if snapshot.source_tier is not None else 99
    return (
        _is_actionable(snapshot, confidence_floor)
        and snapshot.fit_score >= fit_floor
        and source_tier <= source_tier_max
    )


def _is_stale(snapshot: RankedSnapshot, stale_hours: int, source_tier_max: int) -> bool:
    if snapshot.status in {"unknown", "closed"}:
        return True
    if snapshot.source_tier is not None and snapshot.source_tier > source_tier_max:
        return True
    if not snapshot.updated_at:
        return False
    try:
        updated_at = datetime.fromisoformat(snapshot.updated_at)
    except ValueError:
        return True
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - updated_at > timedelta(hours=stale_hours)


def compute_case_metrics(
    case_cfg: dict[str, Any],
    funding_result: FundingSearchResult,
    ranked_items: list[RankedSnapshot],
    profile: CompanyProfile | None = None,
    goal_route: GoalRoute | None = None,
    ecosystem_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    top_n = int(case_cfg.get("top_n", 10))
    confidence_floor = float(case_cfg.get("confidence_floor", 0.60))
    fit_floor = float(case_cfg.get("fit_floor", 0.65))
    source_tier_max = int(case_cfg.get("source_tier_max", 3))
    stale_hours = int(case_cfg.get("stale_hours", 168))
    anchors = list(case_cfg.get("anchors") or [])

    top_items = ranked_items[:top_n]
    actionable_entries = compose_actionable_entries(
        project_name=(profile.projects[0]["name"] if profile and profile.projects else (profile.company_name if profile else "project")),
        snapshots=top_items,
        top_n=top_n,
    )
    actionable_count = sum(
        1 for item in top_items if _is_actionable(item, confidence_floor)
    )
    high_fit_verified_like_count = sum(
        1
        for item in top_items
        if _is_high_fit_verified_like(
            item,
            confidence_floor=confidence_floor,
            fit_floor=fit_floor,
            source_tier_max=source_tier_max,
        )
    )
    stale_count = sum(
        1 for item in top_items if _is_stale(item, stale_hours, source_tier_max)
    )
    cohort_or_builder_count = sum(
        1
        for item in top_items
        if item.category in {"accelerator", "vc_cohort", "builder_program", "residency", "hackathon_pipeline"}
    )

    matched_anchors: list[str] = []
    for anchor in anchors:
        if any(_matches_anchor(item, anchor) for item in top_items):
            if isinstance(anchor, str):
                matched_anchors.append(anchor)
            else:
                matched_anchors.append(anchor.get("name", ""))

    anchor_total = len(anchors)
    matched_anchor_count = len(matched_anchors)
    profile_specific_recall = (
        matched_anchor_count / anchor_total if anchor_total else 1.0
    )

    avg_priority = (
        round(sum(item.priority_score for item in top_items) / len(top_items), 4)
        if top_items
        else 0.0
    )

    graph = ecosystem_graph or load_ecosystem_graph()
    target_ecosystems = [str(v) for v in (case_cfg.get("target_ecosystems") or (profile.target_ecosystems if profile else []))]
    profile_name = (
        profile.projects[0]["name"]
        if profile and profile.projects
        else (profile.company_name if profile else "project")
    )
    funding_map = build_project_funding_map(
        project_name=profile_name,
        target_ecosystems=target_ecosystems,
        graph=graph,
        ranked_snapshots=top_items,
    )

    target_org = case_cfg.get("target_org")
    dossier = build_org_dossier(str(target_org), graph, top_items) if target_org else None
    matched_dossier_snapshots = [
        item
        for item in top_items
        if dossier and (
            _normalize_text(item.organization) == _normalize_text(dossier.organization)
            or _normalize_text(item.program) in {_normalize_text(name) for name in dossier.programs}
        )
    ]
    official_source_ratio = (
        round(
            sum(1 for item in matched_dossier_snapshots if (item.source_tier or 99) <= 2)
            / len(matched_dossier_snapshots),
            4,
        )
        if matched_dossier_snapshots
        else 0.0
    )

    return {
        "top_result_count": len(top_items),
        "actionable_top10_count": actionable_count,
        "high_fit_verified_count": high_fit_verified_like_count,
        "output_ready_top10_count": compute_output_ready_count(actionable_entries),
        "why_fit_coverage": compute_reason_coverage(actionable_entries),
        "next_action_coverage": compute_next_action_coverage(actionable_entries),
        "cohort_or_builder_in_top10_count": cohort_or_builder_count,
        "matched_anchor_count": matched_anchor_count,
        "missing_anchor_count": max(0, anchor_total - matched_anchor_count),
        "profile_specific_recall": round(profile_specific_recall, 4),
        "stale_top10_count": stale_count,
        "average_priority_score": avg_priority,
        "funding_map_coverage": compute_funding_map_coverage(funding_map, target_ecosystems),
        "tier1_ecosystem_count": len(funding_map.tier1_ecosystems),
        "tier2_ecosystem_count": len(funding_map.tier2_ecosystems),
        "matched_ecosystem_count": len(funding_map.matched_ecosystems),
        "dossier_fact_completeness": compute_dossier_fact_completeness(dossier) if dossier else 0.0,
        "dossier_program_count": len(dossier.programs) if dossier else 0,
        "dossier_matched_program_count": len(dossier.matched_programs) if dossier else 0,
        "official_source_ratio": official_source_ratio,
        "social_candidate_count": funding_result.social_count,
        "social_candidate_ratio": round(
            funding_result.social_count / max(1, funding_result.total_raw), 4
        ),
        "candidate_to_ingested_ratio": round(
            funding_result.total_ingested / max(1, funding_result.total_raw), 4
        ),
        "rounds_executed": len(funding_result.round_log),
        "matched_anchors": matched_anchors,
    }


def _evaluate_threshold(value: Any, rule: dict[str, Any]) -> tuple[bool, str]:
    checks: list[bool] = []
    parts: list[str] = []

    for op in ("gte", "gt", "lte", "lt", "eq"):
        if op not in rule:
            continue
        target = rule[op]
        if value is None:
            checks.append(False)
            parts.append(f"{op} {target} (value missing)")
            continue
        if op == "gte":
            passed = value >= target
            rendered = f"{value} >= {target}"
        elif op == "gt":
            passed = value > target
            rendered = f"{value} > {target}"
        elif op == "lte":
            passed = value <= target
            rendered = f"{value} <= {target}"
        elif op == "lt":
            passed = value < target
            rendered = f"{value} < {target}"
        else:
            passed = value == target
            rendered = f"{value} == {target}"
        checks.append(passed)
        parts.append(rendered)

    if not checks:
        return True, "no threshold"
    return all(checks), ", ".join(parts)


def evaluate_goal_metrics(
    metrics: dict[str, Any],
    goal_thresholds: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    for metric_name, rule in goal_thresholds.items():
        passed, detail = _evaluate_threshold(metrics.get(metric_name), rule)
        checks.append(
            {
                "metric": metric_name,
                "value": metrics.get(metric_name),
                "rule": rule,
                "passed": passed,
                "detail": detail,
            }
        )
        if not passed:
            failures.append(metric_name)

    return {
        "met": not failures,
        "failed_metrics": failures,
        "checks": checks,
    }


def compute_progress_score(
    metrics: dict[str, Any],
    goal_thresholds: dict[str, dict[str, Any]],
) -> float:
    """Goal threshold 대비 현재 상태를 0.0~1.0 수렴 점수로 환산."""
    if not goal_thresholds:
        return 1.0

    progress_parts: list[float] = []
    for metric_name, rule in goal_thresholds.items():
        value = metrics.get(metric_name)
        if value is None:
            progress_parts.append(0.0)
            continue

        if "gte" in rule:
            target = float(rule["gte"])
            if target <= 0:
                progress_parts.append(1.0)
            else:
                progress_parts.append(min(1.0, float(value) / target))
            continue

        if "lte" in rule:
            target = float(rule["lte"])
            if float(value) <= target:
                progress_parts.append(1.0)
            else:
                divisor = max(abs(float(value)), 1.0)
                progress_parts.append(max(0.0, target / divisor))
            continue

        passed, _ = _evaluate_threshold(value, rule)
        progress_parts.append(1.0 if passed else 0.0)

    return round(sum(progress_parts) / len(progress_parts), 4)


def select_next_actions(
    goal_route: GoalRoute | None,
    goal_result: dict[str, Any],
    metrics: dict[str, Any],
    last_mode: str,
) -> list[str]:
    actions: list[str] = []

    if metrics.get("top_result_count", 0) == 0:
        actions.append("fallback_to_reference_registry")

    if last_mode == "fast" and not goal_result.get("met"):
        actions.append("escalate_to_deep_search")

    failure_to_action = {
        "actionable_top10_count": "expand_apply_and_official_page_queries",
        "high_fit_verified_count": "bias_official_domains_and_reference_sources",
        "missing_anchor_count": "expand_target_ecosystem_and_vc_cohort_queries",
        "profile_specific_recall": "add_profile_specific_anchor_and_thesis_variants",
        "stale_top10_count": "increase_freshness_bias_and_reverification",
    }

    for failure in goal_result.get("failed_metrics", []):
        action = failure_to_action.get(failure)
        if action:
            actions.append(action)

    if goal_route is not None:
        actions.extend(goal_specific_actions(goal_route, goal_result.get("failed_metrics", []), metrics))

    deduped: list[str] = []
    for action in actions:
        if action not in deduped:
            deduped.append(action)
    return deduped


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


def _anchor_names(case_cfg: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for anchor in case_cfg.get("anchors") or []:
        if isinstance(anchor, str):
            names.append(anchor)
        elif isinstance(anchor, dict):
            name = anchor.get("name")
            if name:
                names.append(str(name))
    return names


def build_search_hints(
    profile: CompanyProfile,
    case_cfg: dict[str, Any],
    actions: list[str],
    goal_route: GoalRoute | None = None,
) -> list[str]:
    """Translate loop actions into real hint queries for the next attempt."""
    priority_hints: list[str] = []
    hints: list[str] = []
    anchors = _anchor_names(case_cfg)
    ecosystems = list(profile.target_ecosystems or [])
    sector_terms = [tag.replace("_", " ") for tag in (profile.sector_tags or [])[:4]]
    subsector_terms = [tag.replace("_", " ") for tag in (profile.subsector_tags or [])[:4]]
    project_terms: list[str] = []
    for project in profile.projects[:2]:
        for tag in project.get("tags", [])[:3]:
            project_terms.append(str(tag).replace("_", " "))

    if "add_profile_specific_anchor_and_thesis_variants" in actions:
        for term in (sector_terms + subsector_terms + project_terms)[:8]:
            hints.append(f"{term} crypto grant apply 2026")
            hints.append(f"{term} web3 accelerator cohort")
        if profile.product_summary:
            summary_words = [
                word.strip(" ,.")
                for word in profile.product_summary.lower().split()
                if len(word.strip(" ,.")) >= 5
            ]
            phrase = " ".join(summary_words[:4])
            if phrase:
                hints.append(f"{phrase} funding program")

    if "expand_apply_and_official_page_queries" in actions:
        for anchor in anchors[:6]:
            hints.append(f"\"{anchor}\" apply official")
            hints.append(f"\"{anchor}\" application official site")

    if "bias_official_domains_and_reference_sources" in actions:
        for anchor in anchors[:6]:
            hints.append(f"\"{anchor}\" official program page")
            hints.append(f"site:{anchor.split()[0].lower()}.xyz \"{anchor}\"")

    if "expand_target_ecosystem_and_vc_cohort_queries" in actions:
        for eco in ecosystems[:6]:
            hints.append(f"{eco} vc accelerator cohort apply 2026")
            hints.append(f"{eco} builder program official apply 2026")
            hints.append(f"{eco} ecosystem venture accelerator")
        for anchor in anchors[:4]:
            hints.append(f"\"{anchor}\" cohort application")

    if goal_route is not None:
        if "recover_builder_and_cohort_mix" in actions:
            for eco in (goal_route.target_ecosystems or ecosystems)[:6]:
                priority_hints.append(f"{eco} builder residency accelerator")
                priority_hints.append(f"{eco} vc ecosystem cohort")
        if "recover_missing_ecosystems" in actions or "expand_ecosystem_graph_queries" in actions:
            for eco in goal_route.target_ecosystems[:8]:
                priority_hints.append(f"{eco} ecosystem funding official")
                priority_hints.append(f"{eco} builder program apply")
        if "expand_org_program_queries" in actions:
            for entity in goal_route.target_entities[:6]:
                priority_hints.append(f"\"{entity}\" official program page")
                priority_hints.append(f"\"{entity}\" cohort apply")
        if "expand_partner_and_mentor_queries" in actions:
            for entity in goal_route.target_entities[:6]:
                priority_hints.append(f"\"{entity}\" mentors investors partners")
                priority_hints.append(f"\"{entity}\" demo day mentors")
        if "expand_official_docs_queries" in actions:
            for entity in goal_route.target_entities[:6]:
                priority_hints.append(f"\"{entity}\" official docs")
                priority_hints.append(f"\"{entity}\" official announcement")
        if "expand_grant_family_queries" in actions:
            for eco in (goal_route.target_ecosystems or ecosystems)[:6]:
                priority_hints.append(f"{eco} grants rolling apply")
                priority_hints.append(f"{eco} foundation grants official")

    return _dedup_strings(priority_hints + hints, limit=32)


def build_bootstrap_terms(
    case_cfg: dict[str, Any],
    actions: list[str],
    goal_route: GoalRoute | None = None,
    *,
    include_case_anchors: bool = False,
) -> list[str]:
    """다음 시도에서 공식 페이지 direct fetch에 쓸 우선 용어."""
    anchors = _anchor_names(case_cfg)
    if include_case_anchors and anchors:
        return _dedup_strings(anchors, limit=10)

    if not actions:
        return []

    direct_fetch_actions = {
        "expand_apply_and_official_page_queries",
        "bias_official_domains_and_reference_sources",
        "expand_target_ecosystem_and_vc_cohort_queries",
        "add_profile_specific_anchor_and_thesis_variants",
        "fallback_to_reference_registry",
    }
    if not any(action in direct_fetch_actions for action in actions):
        if goal_route is None:
            return []
        return _dedup_strings(goal_route.target_entities + goal_route.target_ecosystems, limit=10)

    terms = anchors
    if goal_route is not None:
        terms = [*terms, *goal_route.target_entities, *goal_route.target_ecosystems]
    return _dedup_strings(terms, limit=10)


def build_attempt_policy(
    attempt_index: int,
    case_cfg: dict[str, Any],
    profile: CompanyProfile,
    goal_route: GoalRoute | None = None,
    previous_goal: dict[str, Any] | None = None,
    previous_actions: list[str] | None = None,
    seed_actions: list[str] | None = None,
    reflection: ResearchReflection | dict[str, Any] | None = None,
    max_reflection_search_hints: int = 12,
    max_reflection_bootstrap_terms: int = 8,
) -> AttemptPolicy:
    mode_sequence = list(case_cfg.get("mode_sequence") or ["deep"])
    mode = mode_sequence[min(attempt_index, len(mode_sequence) - 1)]
    reflection_seeds = resolve_reflection_seeds(
        reflection,
        case_id=str(case_cfg.get("id") or ""),
        goal_type=(
            goal_route.goal_type.value
            if goal_route is not None
            else str(case_cfg.get("goal_type") or "")
        ),
        target_entities=(goal_route.target_entities if goal_route is not None else []),
        target_ecosystems=(
            goal_route.target_ecosystems if goal_route is not None else []
        ),
        max_search_hints=max_reflection_search_hints,
        max_bootstrap_terms=max_reflection_bootstrap_terms,
    )
    applied_actions = merge_strings(
        list(seed_actions or []),
        list(reflection_seeds.actions),
        list(previous_actions or []),
    )

    if previous_goal and not previous_goal.get("met") and "escalate_to_deep_search" in applied_actions:
        mode = "deep"

    search_hints = merge_strings(
        list(reflection_seeds.search_hints),
        build_search_hints(profile, case_cfg, applied_actions, goal_route),
        limit=32,
    )
    bootstrap_terms = merge_strings(
        list(reflection_seeds.bootstrap_terms),
        build_bootstrap_terms(
            case_cfg,
            applied_actions,
            goal_route,
            include_case_anchors=(attempt_index == 0 and mode == "deep"),
        ),
        limit=10,
    )
    return AttemptPolicy(
        mode=mode,
        search_hints=search_hints,
        bootstrap_terms=bootstrap_terms,
        applied_actions=applied_actions,
    )


async def build_ranked_snapshots(
    store: EntityStore,
    ranked_results: list[MatchingOutput],
) -> list[RankedSnapshot]:
    snapshots: list[RankedSnapshot] = []

    for output in ranked_results:
        opp = await store.get_opportunity(output.opportunity_id)
        if opp is None:
            continue
        program = await store.get_program(opp.program_id)
        org = await store.get_organization(program.org_id) if program else None

        days_left = opp.days_left
        if days_left is None and opp.deadline_at is not None:
            days_left = calculate_days_left(opp.deadline_at)

        snapshots.append(
            RankedSnapshot(
                opportunity_id=output.opportunity_id,
                organization=(
                    org.display_name
                    or org.normalized_name
                    or ""
                ) if org else "",
                program=(
                    program.display_name
                    or program.normalized_name
                    or ""
                ) if program else "",
                category=program.category.value if program else "",
                status=opp.status.value,
                apply_url=opp.apply_url,
                days_left=days_left,
                source_tier=opp.source_tier,
                confidence=output.confidence,
                fit_score=output.fit_score,
                priority_score=output.priority_score,
                why_fit=output.why_fit,
                next_action=output.next_action,
                source_chain=list(opp.source_chain),
                updated_at=opp.updated_at.isoformat() if opp.updated_at else None,
            )
        )

    return snapshots


async def run_case(
    benchmark_defaults: dict[str, Any],
    profile_specs: dict[str, Any],
    case_cfg: dict[str, Any],
    max_runs_override: int | None = None,
    seed_actions: list[str] | None = None,
    reflection: ResearchReflection | dict[str, Any] | None = None,
    reflection_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged_case = dict(benchmark_defaults)
    merged_case.update(case_cfg)

    case_id = merged_case["id"]
    profile = resolve_profile(merged_case["profile"], profile_specs)
    mode_sequence = list(merged_case.get("mode_sequence") or ["deep"])
    max_runs = max_runs_override or int(merged_case.get("max_runs", len(mode_sequence)))
    max_total_runs = int(merged_case.get("max_total_runs", max_runs * 2))
    plateau_window = int(merged_case.get("plateau_window", 2))
    top_n = int(merged_case.get("top_n", 10))
    intent = str(merged_case.get("intent", "best_fit"))
    goal_route = resolve_goal_route(merged_case)
    ecosystem_graph = load_ecosystem_graph()

    runs: list[dict[str, Any]] = []
    stop_reason = "max_runs_reached"
    previous_goal: dict[str, Any] | None = None
    previous_actions: list[str] = []
    best_progress_score = -1.0
    plateau_streak = 0

    attempt = 0
    while attempt < max_total_runs:
        policy = build_attempt_policy(
            attempt_index=attempt,
            case_cfg=merged_case,
            profile=profile,
            goal_route=goal_route,
            previous_goal=previous_goal,
            previous_actions=previous_actions,
            seed_actions=seed_actions,
            reflection=reflection,
            max_reflection_search_hints=int((reflection_cfg or {}).get("max_search_hints", 12)),
            max_reflection_bootstrap_terms=int((reflection_cfg or {}).get("max_bootstrap_terms", 8)),
        )
        mode = policy.mode

        with tempfile.TemporaryDirectory(prefix=f"{case_id}-") as temp_dir:
            db_path = Path(temp_dir) / "research.db"
            config = replace(base_config, db_path=db_path)

            async with EntityStore(db_path) as store:
                await store.init_schema()
                orchestrator = FundingSearchOrchestrator(store=store, config=config)
                funding_result = await orchestrator.search_for_project(
                    profile=profile,
                    intent=intent,
                    top_n=top_n,
                    mode=mode,
                    search_hints=policy.search_hints,
                    bootstrap_terms=policy.bootstrap_terms,
                )
                ranked_items = await build_ranked_snapshots(store, funding_result.ranked_results)

        metrics = compute_case_metrics(
            merged_case,
            funding_result,
            ranked_items,
            profile=profile,
            goal_route=goal_route,
            ecosystem_graph=ecosystem_graph,
        )
        goal_result = evaluate_goal_metrics(
            metrics=metrics,
            goal_thresholds=merged_case.get("goal_thresholds") or {},
        )
        progress_score = compute_progress_score(
            metrics=metrics,
            goal_thresholds=merged_case.get("goal_thresholds") or {},
        )
        next_actions = select_next_actions(goal_route, goal_result, metrics, last_mode=mode)

        run_record = {
            "attempt": attempt + 1,
            "mode": mode,
            "goal_type": goal_route.goal_type.value,
            "recovery_mode": goal_route.recovery_mode.value,
            "search_hints": list(policy.search_hints),
            "bootstrap_terms": list(policy.bootstrap_terms),
            "applied_actions": list(policy.applied_actions),
            "metrics": metrics,
            "goal": goal_result,
            "progress_score": progress_score,
            "result_counts": {
                "web_count": funding_result.web_count,
                "social_count": funding_result.social_count,
                "reference_count": funding_result.reference_count,
                "total_raw": funding_result.total_raw,
                "total_deduped": funding_result.total_deduped,
                "total_ingested": funding_result.total_ingested,
                "new_discovered": funding_result.new_discovered,
                "elapsed_seconds": round(funding_result.elapsed_seconds, 3),
                "errors": list(funding_result.errors),
            },
            "round_log": list(funding_result.round_log),
            "next_actions": next_actions,
            "top_results": [asdict(item) for item in ranked_items[:top_n]],
        }
        runs.append(run_record)
        previous_goal = goal_result
        previous_actions = next_actions

        if goal_result["met"]:
            stop_reason = "goal_met"
            break

        attempt += 1

        if progress_score > best_progress_score:
            best_progress_score = progress_score
            plateau_streak = 0
        else:
            plateau_streak += 1
            if plateau_streak >= plateau_window:
                stop_reason = "plateau_reached"
                break

        if attempt >= max_runs and progress_score < 0.999 and next_actions:
            stop_reason = "continuing_on_progress"
            continue

        if attempt >= max_runs and not next_actions:
            stop_reason = "strategy_exhausted"
            break

    final_run = runs[-1] if runs else {}
    return {
        "case_id": case_id,
        "summary": merged_case.get("summary", ""),
        "profile": merged_case["profile"],
        "goal_type": goal_route.goal_type.value,
        "recovery_mode": goal_route.recovery_mode.value,
        "seed_actions": list(seed_actions or []),
        "anchors": list(merged_case.get("anchors") or []),
        "target_entities": list(goal_route.target_entities),
        "target_ecosystems": list(goal_route.target_ecosystems),
        "goal_thresholds": merged_case.get("goal_thresholds") or {},
        "stop_reason": stop_reason,
        "runs": runs,
        "final_metrics": final_run.get("metrics", {}),
        "final_progress_score": final_run.get("progress_score", 0.0),
        "goal": final_run.get("goal", {"met": False, "failed_metrics": ["no_runs"], "checks": []}),
        "recommended_actions": final_run.get("next_actions", []),
    }


async def run_benchmark(
    benchmark: dict[str, Any],
    case_filter: set[str] | None = None,
    max_runs_override: int | None = None,
    program_cfg: dict[str, Any] | None = None,
    carryover_actions: list[str] | None = None,
    reflection: ResearchReflection | dict[str, Any] | None = None,
    reflection_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    defaults = benchmark.get("defaults") or {}
    profiles = benchmark.get("profiles") or {}

    case_reports: list[dict[str, Any]] = []
    for case_cfg in benchmark["cases"]:
        case_id = case_cfg.get("id")
        if case_filter and case_id not in case_filter:
            continue
        goal_route = resolve_goal_route(case_cfg)
        seed_actions = resolve_program_seed_actions(
            program_cfg,
            case_cfg,
            goal_route,
            carryover_actions=carryover_actions,
        )
        case_report = await run_case(
            benchmark_defaults=defaults,
            profile_specs=profiles,
            case_cfg=case_cfg,
            max_runs_override=max_runs_override,
            seed_actions=seed_actions,
            reflection=reflection,
            reflection_cfg=reflection_cfg,
        )
        case_reports.append(case_report)

    overall_goal_met = all(case["goal"]["met"] for case in case_reports) if case_reports else False
    recommended_actions: list[str] = []
    for case in case_reports:
        for action in case.get("recommended_actions", []):
            if action not in recommended_actions:
                recommended_actions.append(action)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_type": "single_run",
        "case_count": len(case_reports),
        "overall_goal_met": overall_goal_met,
        "cases": case_reports,
        "recommended_actions": recommended_actions,
    }


def compute_report_progress_score(report: dict[str, Any]) -> float:
    cases = report.get("cases") or []
    if not cases:
        return 0.0
    scores = [float(case.get("final_progress_score", 0.0)) for case in cases]
    return round(sum(scores) / len(scores), 4)


def append_results_tsv(tsv_path: Path, report: dict[str, Any], cycle_index: int) -> None:
    tsv_path.parent.mkdir(parents=True, exist_ok=True)
    if not tsv_path.exists():
        tsv_path.write_text(
            "timestamp\tcycle\treport_type\tcase_id\tgoal_type\trecovery_mode\tcase_goal_met\toverall_goal_met\tstop_reason\tprogress_score\tactionable_top10_count\toutput_ready_top10_count\tprofile_specific_recall\tfunding_map_coverage\tdossier_fact_completeness\trecommended_actions\n",
            encoding="utf-8",
        )

    timestamp = str(report.get("generated_at") or datetime.now(timezone.utc).isoformat())
    overall_goal_met = str(bool(report.get("overall_goal_met", False))).lower()
    with tsv_path.open("a", encoding="utf-8") as handle:
        for case in report.get("cases", []):
            metrics = case.get("final_metrics", {})
            handle.write(
                "\t".join(
                    [
                        timestamp,
                        str(cycle_index),
                        str(report.get("report_type", "single_run")),
                        str(case.get("case_id", "")),
                        str(case.get("goal_type", "")),
                        str(case.get("recovery_mode", "")),
                        str(bool((case.get("goal") or {}).get("met", False))).lower(),
                        overall_goal_met,
                        str(case.get("stop_reason", "")),
                        str(case.get("final_progress_score", 0.0)),
                        str(metrics.get("actionable_top10_count", "")),
                        str(metrics.get("output_ready_top10_count", "")),
                        str(metrics.get("profile_specific_recall", "")),
                        str(metrics.get("funding_map_coverage", "")),
                        str(metrics.get("dossier_fact_completeness", "")),
                        ",".join(case.get("recommended_actions", [])),
                    ]
                )
                + "\n"
            )


async def run_continuous_program(
    benchmark: dict[str, Any],
    *,
    program_cfg: dict[str, Any] | None = None,
    case_filter: set[str] | None = None,
    max_runs_override: int | None = None,
    max_cycles_override: int | None = None,
    until_goal_or_interrupt: bool = False,
    results_tsv_path: Path | None = None,
) -> dict[str, Any]:
    settings = resolve_continuous_config(
        program_cfg,
        max_cycles_override=max_cycles_override,
        until_goal_or_interrupt=until_goal_or_interrupt,
    )
    reflection_cfg = resolve_reflection_config(program_cfg)
    max_cycles = settings["max_cycles"]
    plateau_cycles = settings["plateau_cycles"]
    min_progress_delta = settings["min_progress_delta"]

    cycle_reports: list[dict[str, Any]] = []
    carryover_actions = merge_strings(list((program_cfg or {}).get("seed_actions") or []))
    active_reflection: ResearchReflection | None = None
    load_path = reflection_cfg.get("load_path") or ""
    if reflection_cfg.get("enabled") and load_path and Path(load_path).exists():
        active_reflection = load_research_reflection(load_path)
    best_progress_score = -1.0
    plateau_streak = 0
    stop_reason = "max_cycles_reached"
    cycle_index = 0

    while max_cycles is None or cycle_index < max_cycles:
        cycle_index += 1
        report = await run_benchmark(
            benchmark=benchmark,
            case_filter=case_filter,
            max_runs_override=max_runs_override,
            program_cfg=program_cfg,
            carryover_actions=carryover_actions,
            reflection=active_reflection,
            reflection_cfg=reflection_cfg,
        )
        report["report_type"] = "continuous_cycle"
        report["cycle"] = cycle_index
        report["carryover_actions"] = list(carryover_actions)
        report["progress_score"] = compute_report_progress_score(report)
        reflection = build_research_reflection(
            report,
            max_search_hints=int(reflection_cfg["max_search_hints"]),
            max_bootstrap_terms=int(reflection_cfg["max_bootstrap_terms"]),
        )
        report["reflection"] = asdict(reflection)
        cycle_reports.append(report)
        active_reflection = reflection

        if results_tsv_path is not None:
            append_results_tsv(results_tsv_path, report, cycle_index)

        if report["overall_goal_met"]:
            stop_reason = "goal_met"
            break

        next_actions = merge_strings(
            list((program_cfg or {}).get("seed_actions") or []),
            list(report.get("recommended_actions") or []),
        )
        progress_score = float(report.get("progress_score", 0.0))
        actions_changed = next_actions != carryover_actions

        if progress_score > best_progress_score + min_progress_delta:
            best_progress_score = progress_score
            plateau_streak = 0
        elif actions_changed:
            best_progress_score = max(best_progress_score, progress_score)
            plateau_streak = 0
        else:
            best_progress_score = max(best_progress_score, progress_score)
            plateau_streak += 1
            if plateau_streak >= plateau_cycles:
                stop_reason = "plateau_reached"
                carryover_actions = next_actions
                break

        if not next_actions:
            stop_reason = "strategy_exhausted"
            break

        carryover_actions = next_actions

    final_cycle = cycle_reports[-1] if cycle_reports else {}
    final_reflection = (
        load_research_reflection_from_data(final_cycle["reflection"])
        if final_cycle.get("reflection")
        else active_reflection
    )
    latest_reflection_path = str(reflection_cfg.get("latest_path") or "")
    promote_reflection_path = str(reflection_cfg.get("promote_path") or "")
    if reflection_cfg.get("enabled") and final_reflection is not None:
        if latest_reflection_path:
            write_research_reflection(latest_reflection_path, final_reflection)
        if promote_reflection_path:
            write_research_reflection(promote_reflection_path, final_reflection)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_type": "continuous_run",
        "program_name": (program_cfg or {}).get("name", "funding-autoresearch"),
        "benchmark": str((program_cfg or {}).get("benchmark", DEFAULT_BENCHMARK)),
        "cycle_count": len(cycle_reports),
        "stop_reason": stop_reason,
        "overall_goal_met": bool(final_cycle.get("overall_goal_met", False)),
        "progress_score": float(final_cycle.get("progress_score", 0.0)),
        "carryover_actions": list(carryover_actions),
        "recommended_actions": list(final_cycle.get("recommended_actions", [])),
        "reflection": asdict(final_reflection) if final_reflection is not None else None,
        "reflection_latest_path": latest_reflection_path,
        "reflection_promote_path": promote_reflection_path,
        "cycles": cycle_reports,
        "cases": list(final_cycle.get("cases", [])),
    }


def render_summary(report: dict[str, Any]) -> str:
    if report.get("report_type") == "continuous_run":
        lines = [
            f"Continuous funding autoresearch generated_at={report['generated_at']}",
            f"program={report.get('program_name')} cycles={report.get('cycle_count')} stop={report.get('stop_reason')} overall_goal_met={report.get('overall_goal_met')}",
            f"progress_score={report.get('progress_score')}",
        ]
        for case in report.get("cases", []):
            goal = case.get("goal", {})
            metrics = case.get("final_metrics", {})
            lines.append(
                " - "
                f"{case['case_id']}: stop={case['stop_reason']} "
                f"goal_met={goal.get('met')} "
                f"actionable_top10={metrics.get('actionable_top10_count')} "
                f"output_ready={metrics.get('output_ready_top10_count')} "
                f"recall={metrics.get('profile_specific_recall')} "
                f"missing_anchors={metrics.get('missing_anchor_count')}"
            )
        if report.get("recommended_actions"):
            lines.append("recommended_actions=" + ", ".join(report["recommended_actions"]))
        return "\n".join(lines)

    lines = [
        f"Research benchmark generated_at={report['generated_at']}",
        f"cases={report['case_count']} overall_goal_met={report['overall_goal_met']}",
    ]
    for case in report.get("cases", []):
        goal = case.get("goal", {})
        metrics = case.get("final_metrics", {})
        lines.append(
            " - "
            f"{case['case_id']}: stop={case['stop_reason']} "
            f"goal_met={goal.get('met')} "
            f"actionable_top10={metrics.get('actionable_top10_count')} "
            f"recall={metrics.get('profile_specific_recall')} "
            f"missing_anchors={metrics.get('missing_anchor_count')}"
        )
    if report.get("recommended_actions"):
        lines.append("recommended_actions=" + ", ".join(report["recommended_actions"]))
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the funding research benchmark loop.")
    parser.add_argument(
        "--benchmark",
        default=str(DEFAULT_BENCHMARK),
        help="Path to eval benchmark spec (JSON-compatible YAML).",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="cases",
        default=[],
        help="Limit execution to one or more case ids.",
    )
    parser.add_argument(
        "--max-runs-per-case",
        type=int,
        default=None,
        help="Override max_runs for every case.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Write the full JSON report to this path. Defaults to output/research-evals/<timestamp>.json",
    )
    parser.add_argument(
        "--program-file",
        default="",
        help="Optional markdown control file with a JSON config block. Defaults to funding_program.md when --continuous is used and the file exists.",
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run multiple benchmark cycles until goal, plateau, or manual stop.",
    )
    parser.add_argument(
        "--until-goal-or-interrupt",
        action="store_true",
        help="Keep cycling until goal is met, strategy is exhausted, plateau is reached, or the process is interrupted.",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help="Override continuous cycle budget.",
    )
    parser.add_argument(
        "--results-tsv",
        default="",
        help="Append compact case results to this TSV path. Defaults to output/research-evals/results.tsv in continuous mode.",
    )
    return parser.parse_args()


async def _main() -> int:
    args = parse_args()
    benchmark_path = Path(args.benchmark)
    benchmark = load_benchmark(benchmark_path)
    program_path = Path(args.program_file) if args.program_file else None
    if program_path is None and (args.continuous or args.until_goal_or_interrupt) and DEFAULT_PROGRAM.exists():
        program_path = DEFAULT_PROGRAM
    program_cfg = load_program(program_path) if program_path is not None and program_path.exists() else None
    reflection_cfg = resolve_reflection_config(program_cfg)

    if args.continuous or args.until_goal_or_interrupt:
        report = await run_continuous_program(
            benchmark=benchmark,
            program_cfg=program_cfg,
            case_filter=set(args.cases) if args.cases else None,
            max_runs_override=args.max_runs_per_case,
            max_cycles_override=args.max_cycles,
            until_goal_or_interrupt=args.until_goal_or_interrupt,
            results_tsv_path=Path(args.results_tsv) if args.results_tsv else DEFAULT_RESULTS_TSV,
        )
    else:
        report = await run_benchmark(
            benchmark=benchmark,
            case_filter=set(args.cases) if args.cases else None,
            max_runs_override=args.max_runs_per_case,
            program_cfg=program_cfg,
            reflection=(
                load_research_reflection(reflection_cfg["load_path"])
                if reflection_cfg.get("enabled")
                and reflection_cfg.get("load_path")
                and Path(reflection_cfg["load_path"]).exists()
                else None
            ),
            reflection_cfg=reflection_cfg,
        )
        reflection = build_research_reflection(
            report,
            max_search_hints=int(reflection_cfg["max_search_hints"]),
            max_bootstrap_terms=int(reflection_cfg["max_bootstrap_terms"]),
        )
        report["reflection"] = asdict(reflection)
        report["reflection_latest_path"] = str(reflection_cfg.get("latest_path") or "")
        report["reflection_promote_path"] = str(reflection_cfg.get("promote_path") or "")
        if reflection_cfg.get("enabled"):
            if report["reflection_latest_path"]:
                write_research_reflection(report["reflection_latest_path"], reflection)
            if report["reflection_promote_path"]:
                write_research_reflection(report["reflection_promote_path"], reflection)

    timestamp = build_timestamp_slug()
    output_path = (
        Path(args.output)
        if args.output
        else Path("output") / "research-evals" / f"{timestamp}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(render_summary(report))
    print(f"report_path={output_path}")
    if report.get("reflection_latest_path"):
        print(f"reflection_path={report['reflection_latest_path']}")
    return 0 if report["overall_goal_met"] else 2


def main() -> int:
    return asyncio.run(_main())


if __name__ == "__main__":
    raise SystemExit(main())
