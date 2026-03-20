from __future__ import annotations

from pathlib import Path

from src.search.research_reflection import (
    build_research_reflection,
    load_research_reflection,
    resolve_reflection_seeds,
    write_research_reflection,
)


def test_build_research_reflection_promotes_best_run_and_matched_anchors(tmp_path: Path):
    report = {
        "generated_at": "2026-03-15T00:00:00+00:00",
        "report_type": "continuous_cycle",
        "overall_goal_met": False,
        "recommended_actions": ["recover_actionable_mix"],
        "cases": [
            {
                "case_id": "hoot_actionable_strategy",
                "goal_type": "actionable_strategy",
                "recovery_mode": "actionable_recovery",
                "final_progress_score": 0.72,
                "goal": {"met": False},
                "recommended_actions": ["recover_builder_and_cohort_mix"],
                "target_entities": ["Nitro Accelerator"],
                "target_ecosystems": ["Monad"],
                "final_metrics": {"matched_anchors": ["Speedrun"]},
                "runs": [
                    {
                        "goal": {"met": False},
                        "progress_score": 0.45,
                        "applied_actions": ["fallback_to_reference_registry"],
                        "search_hints": ["legacy hint"],
                        "bootstrap_terms": ["Legacy"],
                        "top_results": [],
                    },
                    {
                        "goal": {"met": True},
                        "progress_score": 0.72,
                        "applied_actions": [
                            "expand_apply_and_official_page_queries",
                            "recover_actionable_mix",
                        ],
                        "search_hints": ["Nitro Accelerator apply official"],
                        "bootstrap_terms": ["Nitro Accelerator"],
                        "top_results": [{"opportunity_id": "opp_1"}],
                    },
                ],
            }
        ],
    }

    reflection = build_research_reflection(report, max_search_hints=4, max_bootstrap_terms=4)
    saved_path = write_research_reflection(tmp_path / "reflection.json", reflection)
    loaded = load_research_reflection(saved_path)

    assert loaded.promoted_actions == [
        "recover_actionable_mix",
        "expand_apply_and_official_page_queries",
        "recover_builder_and_cohort_mix",
    ]
    assert loaded.case_reflections[0].search_hints == [
        "Nitro Accelerator apply official",
        "Speedrun",
    ]
    assert loaded.case_reflections[0].bootstrap_terms == [
        "Nitro Accelerator",
        "Speedrun",
    ]


def test_resolve_reflection_seeds_matches_goal_and_target_scope():
    reflection = build_research_reflection(
        {
            "generated_at": "2026-03-15T00:00:00+00:00",
            "report_type": "continuous_cycle",
            "overall_goal_met": False,
            "recommended_actions": ["recover_actionable_mix"],
            "cases": [
                {
                    "case_id": "hoot_actionable_strategy",
                    "goal_type": "actionable_strategy",
                    "recovery_mode": "actionable_recovery",
                    "final_progress_score": 0.7,
                    "goal": {"met": False},
                    "recommended_actions": ["recover_builder_and_cohort_mix"],
                    "target_entities": ["Nitro Accelerator"],
                    "target_ecosystems": ["Monad"],
                    "final_metrics": {"matched_anchors": ["Speedrun"]},
                    "runs": [
                        {
                            "goal": {"met": False},
                            "progress_score": 0.7,
                            "applied_actions": ["expand_apply_and_official_page_queries"],
                            "search_hints": ["Nitro Accelerator apply official"],
                            "bootstrap_terms": ["Nitro Accelerator"],
                            "top_results": [{"opportunity_id": "opp_1"}],
                        }
                    ],
                },
                {
                    "case_id": "org_dossier_monad",
                    "goal_type": "org_dossier",
                    "recovery_mode": "dossier_recovery",
                    "final_progress_score": 0.6,
                    "goal": {"met": False},
                    "recommended_actions": ["expand_official_docs_queries"],
                    "target_entities": ["Monad"],
                    "target_ecosystems": [],
                    "final_metrics": {"matched_anchors": ["Monad Momentum"]},
                    "runs": [
                        {
                            "goal": {"met": False},
                            "progress_score": 0.6,
                            "applied_actions": ["expand_org_program_queries"],
                            "search_hints": ["Monad residency official"],
                            "bootstrap_terms": ["Monad"],
                            "top_results": [{"opportunity_id": "opp_2"}],
                        }
                    ],
                },
            ],
        }
    )

    seeds = resolve_reflection_seeds(
        reflection,
        case_id="hoot_actionable_strategy",
        goal_type="actionable_strategy",
        target_entities=["Nitro Accelerator"],
        target_ecosystems=["Monad"],
    )

    assert "recover_actionable_mix" in seeds.actions
    assert "expand_apply_and_official_page_queries" in seeds.actions
    assert "expand_org_program_queries" in seeds.actions
    assert "Nitro Accelerator apply official" in seeds.search_hints
    assert "Monad residency official" in seeds.search_hints
    assert seeds.bootstrap_terms == ["Nitro Accelerator", "Speedrun", "Monad", "Monad Momentum"]
