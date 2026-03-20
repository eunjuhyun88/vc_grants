from __future__ import annotations

import json

from src.core.types import CompanyProfile, CompanyStage
from src.research.runtime_reflection import resolve_runtime_reflection_seeds
from src.search.research_goal_router import GoalType


def _profile() -> CompanyProfile:
    return CompanyProfile(
        id="cp_hoot",
        company_name="HOOT Labs",
        stage=CompanyStage.MVP,
        sector_tags=["ai_infra", "crypto_infra"],
        target_ecosystems=["Monad", "Arbitrum"],
        projects=[{"name": "HOOT", "priority": 1}],
    )


def test_resolve_runtime_reflection_seeds_uses_program_load_path(tmp_path):
    reflection_path = tmp_path / "reflection.json"
    reflection_path.write_text(
        json.dumps(
            {
                "version": 1,
                "promoted_actions": ["recover_actionable_mix"],
                "case_reflections": [
                    {
                        "case_id": "hoot_actionable_strategy",
                        "goal_type": "actionable_strategy",
                        "goal_met": True,
                        "actions": ["recover_actionable_mix"],
                        "search_hints": ["Nitro Accelerator apply official"],
                        "bootstrap_terms": ["Nitro Accelerator"],
                        "target_entities": ["HOOT"],
                        "target_ecosystems": ["Monad"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    program_path = tmp_path / "funding_program.md"
    program_path.write_text(
        "```json\n"
        + json.dumps(
            {
                "reflection": {
                    "load_path": str(reflection_path),
                    "latest_path": str(tmp_path / "latest.json"),
                    "max_search_hints": 6,
                    "max_bootstrap_terms": 4,
                }
            }
        )
        + "\n```\n",
        encoding="utf-8",
    )

    seeds = resolve_runtime_reflection_seeds(
        profile=_profile(),
        goal_type=GoalType.ACTIONABLE_STRATEGY,
        requested_project="HOOT",
        program_path=program_path,
    )

    assert seeds.search_hints == ["Nitro Accelerator apply official"]
    assert seeds.bootstrap_terms == ["Nitro Accelerator"]


def test_resolve_runtime_reflection_seeds_falls_back_to_latest_path_when_load_path_is_empty(tmp_path):
    (tmp_path / "empty.json").write_text(
        json.dumps({"version": 1, "promoted_actions": [], "case_reflections": []}),
        encoding="utf-8",
    )
    latest_path = tmp_path / "latest.json"
    latest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "promoted_actions": ["expand_ecosystem_graph_queries"],
                "case_reflections": [
                    {
                        "case_id": "hoot_funding_map",
                        "goal_type": "funding_map",
                        "goal_met": True,
                        "actions": ["expand_ecosystem_graph_queries"],
                        "search_hints": ["Arbitrum grants official"],
                        "bootstrap_terms": ["Arbitrum Grants"],
                        "target_entities": ["HOOT"],
                        "target_ecosystems": ["Arbitrum"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    program_path = tmp_path / "funding_program.md"
    program_path.write_text(
        "```json\n"
        + json.dumps(
            {
                "reflection": {
                    "load_path": str(tmp_path / "empty.json"),
                    "latest_path": str(latest_path),
                }
            }
        )
        + "\n```\n",
        encoding="utf-8",
    )

    seeds = resolve_runtime_reflection_seeds(
        profile=_profile(),
        goal_type=GoalType.FUNDING_MAP,
        requested_project="HOOT",
        program_path=program_path,
    )

    assert seeds.search_hints == ["Arbitrum grants official"]
    assert seeds.bootstrap_terms == ["Arbitrum Grants"]
