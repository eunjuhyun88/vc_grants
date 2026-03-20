from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.core.types import CompanyProfile
from src.search.research_goal_router import GoalType, normalize_goal_type
from src.search.research_reflection import (
    ReflectionSeeds,
    ResearchReflection,
    load_research_reflection,
    resolve_reflection_seeds,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROGRAM_PATH = REPO_ROOT / "funding_program.md"
PROGRAM_JSON_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def load_funding_program(path: Path | str = DEFAULT_PROGRAM_PATH) -> dict[str, Any]:
    program_path = Path(path)
    if not program_path.exists():
        return {}

    text = program_path.read_text(encoding="utf-8")
    match = PROGRAM_JSON_RE.search(text)
    if not match:
        return {}

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def resolve_runtime_reflection_config(program_cfg: dict[str, Any] | None) -> dict[str, Any]:
    reflection_cfg = (program_cfg or {}).get("reflection") or {}
    return {
        "enabled": bool(reflection_cfg),
        "load_path": str(reflection_cfg.get("load_path") or "").strip(),
        "latest_path": str(reflection_cfg.get("latest_path") or "").strip(),
        "max_search_hints": int(reflection_cfg.get("max_search_hints", 12)),
        "max_bootstrap_terms": int(reflection_cfg.get("max_bootstrap_terms", 8)),
    }


def _dedup_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.lower().strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(value)
    return deduped


def _has_reflection_signal(reflection: ResearchReflection | None) -> bool:
    if reflection is None:
        return False
    return bool(reflection.promoted_actions or reflection.case_reflections)


def load_runtime_reflection(
    *,
    program_path: Path | str = DEFAULT_PROGRAM_PATH,
) -> ResearchReflection | None:
    program_cfg = load_funding_program(program_path)
    reflection_cfg = resolve_runtime_reflection_config(program_cfg)
    if not reflection_cfg["enabled"]:
        return None

    fallback: ResearchReflection | None = None
    for raw_path in (
        reflection_cfg["load_path"],
        reflection_cfg["latest_path"],
    ):
        if not raw_path:
            continue
        path = Path(raw_path)
        if not path.exists():
            continue
        try:
            reflection = load_research_reflection(path)
        except Exception:
            continue
        if _has_reflection_signal(reflection):
            return reflection
        if fallback is None:
            fallback = reflection
    return fallback


def _profile_target_entities(
    profile: CompanyProfile,
    *,
    requested_project: str | None = None,
    target_entities: list[str] | None = None,
) -> list[str]:
    values = list(target_entities or [])
    if requested_project:
        values.append(requested_project)
    if profile.company_name:
        values.append(profile.company_name)
    for project in profile.projects or []:
        name = str((project or {}).get("name") or "").strip()
        if name:
            values.append(name)
    return _dedup_strings(values)


def _profile_target_ecosystems(
    profile: CompanyProfile,
    *,
    target_ecosystems: list[str] | None = None,
) -> list[str]:
    return _dedup_strings(list(target_ecosystems or []) + list(profile.target_ecosystems or []))


def resolve_runtime_reflection_seeds(
    *,
    profile: CompanyProfile,
    goal_type: GoalType | str = GoalType.ACTIONABLE_STRATEGY,
    requested_project: str | None = None,
    case_id: str = "",
    target_entities: list[str] | None = None,
    target_ecosystems: list[str] | None = None,
    program_path: Path | str = DEFAULT_PROGRAM_PATH,
) -> ReflectionSeeds:
    reflection = load_runtime_reflection(program_path=program_path)
    if reflection is None:
        return ReflectionSeeds()

    normalized_goal_type = normalize_goal_type(
        goal_type.value if isinstance(goal_type, GoalType) else goal_type
    )
    program_cfg = load_funding_program(program_path)
    reflection_cfg = resolve_runtime_reflection_config(program_cfg)

    return resolve_reflection_seeds(
        reflection,
        case_id=case_id,
        goal_type=normalized_goal_type.value,
        target_entities=_profile_target_entities(
            profile,
            requested_project=requested_project,
            target_entities=target_entities,
        ),
        target_ecosystems=_profile_target_ecosystems(
            profile,
            target_ecosystems=target_ecosystems,
        ),
        max_search_hints=reflection_cfg["max_search_hints"],
        max_bootstrap_terms=reflection_cfg["max_bootstrap_terms"],
    )
