from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


def _load_research_loop_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_research_loop.py"
    spec = importlib.util.spec_from_file_location("run_research_loop", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_benchmark_supports_json_compatible_yaml(tmp_path: Path):
    module = _load_research_loop_module()
    bench_path = tmp_path / "benchmark.yaml"
    bench_path.write_text(
        json.dumps(
            {
                "cases": [
                    {"id": "sample", "profile": "HOOT", "goal_thresholds": {}},
                ]
            }
        ),
        encoding="utf-8",
    )

    loaded = module.load_benchmark(bench_path)
    assert loaded["cases"][0]["id"] == "sample"


def test_case_metrics_and_goal_evaluation():
    module = _load_research_loop_module()
    goal_module = importlib.import_module("src.search.research_goal_router")
    snapshots = [
        module.RankedSnapshot(
            opportunity_id="opp_1",
            organization="Alliance",
            program="Alliance Accelerator",
            category="accelerator",
            status="open",
            apply_url="https://alliance.xyz/apply",
            days_left=7,
            source_tier=1,
            confidence=0.92,
            fit_score=0.82,
            priority_score=0.81,
            why_fit="crypto infra fit",
            next_action="apply now",
            source_chain=["https://alliance.xyz/apply"],
            updated_at="2026-03-12T00:00:00+00:00",
        ),
        module.RankedSnapshot(
            opportunity_id="opp_2",
            organization="Ethereum Foundation",
            program="Ethereum Ecosystem Support Program",
            category="grant",
            status="rolling",
            apply_url="https://esp.ethereum.foundation",
            days_left=None,
            source_tier=1,
            confidence=0.90,
            fit_score=0.88,
            priority_score=0.79,
            why_fit="infra grant",
            next_action="prepare grant proposal",
            source_chain=["https://esp.ethereum.foundation"],
            updated_at="2026-03-12T00:00:00+00:00",
        ),
        module.RankedSnapshot(
            opportunity_id="opp_3",
            organization="Random Blog",
            program="Unknown Program",
            category="grant",
            status="unknown",
            apply_url=None,
            days_left=None,
            source_tier=5,
            confidence=0.20,
            fit_score=0.30,
            priority_score=0.15,
            why_fit="weak",
            next_action="watch",
            source_chain=[],
            updated_at=None,
        ),
    ]
    result = SimpleNamespace(
        social_count=1,
        total_raw=5,
        total_ingested=3,
        round_log=[{"round": 0}, {"round": 1}],
    )
    profile = module.resolve_profile("HOOT", {"HOOT": {"fixture": "HOOT"}})
    case_cfg = {
        "top_n": 3,
        "confidence_floor": 0.60,
        "fit_floor": 0.70,
        "source_tier_max": 3,
        "stale_hours": 168,
        "goal_type": "actionable_strategy",
        "anchors": ["Alliance Accelerator", "Ethereum Ecosystem Support Program", "Speedrun"],
        "goal_thresholds": {
            "actionable_top10_count": {"gte": 2},
            "high_fit_verified_count": {"gte": 2},
            "missing_anchor_count": {"lte": 1},
            "profile_specific_recall": {"gte": 0.66},
        },
    }
    goal_route = goal_module.resolve_goal_route(case_cfg)

    metrics = module.compute_case_metrics(case_cfg, result, snapshots, profile=profile, goal_route=goal_route)
    assert metrics["actionable_top10_count"] == 2
    assert metrics["high_fit_verified_count"] == 2
    assert metrics["missing_anchor_count"] == 1
    assert metrics["profile_specific_recall"] == 0.6667
    assert metrics["output_ready_top10_count"] == 2
    assert metrics["why_fit_coverage"] == 1.0
    assert metrics["next_action_coverage"] == 1.0
    assert metrics["cohort_or_builder_in_top10_count"] == 1

    goal = module.evaluate_goal_metrics(metrics, case_cfg["goal_thresholds"])
    assert goal["met"] is True
    assert goal["failed_metrics"] == []


def test_select_next_actions_prefers_continuation_steps():
    module = _load_research_loop_module()
    goal_module = importlib.import_module("src.search.research_goal_router")
    goal_result = {
        "met": False,
        "failed_metrics": [
            "actionable_top10_count",
            "missing_anchor_count",
            "cohort_or_builder_in_top10_count",
        ],
    }
    metrics = {
        "top_result_count": 0,
    }
    goal_route = goal_module.resolve_goal_route({"goal_type": "actionable_strategy"})

    actions = module.select_next_actions(goal_route, goal_result, metrics, last_mode="fast")
    assert "fallback_to_reference_registry" in actions
    assert "escalate_to_deep_search" in actions
    assert "expand_apply_and_official_page_queries" in actions
    assert "expand_target_ecosystem_and_vc_cohort_queries" in actions
    assert "recover_actionable_mix" in actions
    assert "recover_builder_and_cohort_mix" in actions


def test_build_search_hints_translates_actions_into_queries():
    module = _load_research_loop_module()
    goal_module = importlib.import_module("src.search.research_goal_router")
    profile = module.resolve_profile("HOOT", {"HOOT": {"fixture": "HOOT"}})
    case_cfg = {
        "goal_type": "funding_map",
        "target_ecosystems": ["Monad", "NEAR", "Ethereum"],
        "anchors": [
            "Nitro Accelerator",
            "Speedrun",
            "Alliance Accelerator",
        ]
    }
    actions = [
        "expand_apply_and_official_page_queries",
        "expand_target_ecosystem_and_vc_cohort_queries",
        "add_profile_specific_anchor_and_thesis_variants",
        "recover_missing_ecosystems",
    ]
    goal_route = goal_module.resolve_goal_route(case_cfg)

    hints = module.build_search_hints(profile, case_cfg, actions, goal_route)

    assert any("Nitro Accelerator" in hint for hint in hints)
    assert any("ethereum vc accelerator cohort apply 2026" == hint for hint in hints)
    assert any("distributed compute" in hint for hint in hints)
    assert any("Monad ecosystem funding official" == hint for hint in hints)
    assert len(hints) <= 32


def test_build_bootstrap_terms_uses_anchors_for_reference_bootstrap():
    module = _load_research_loop_module()
    goal_module = importlib.import_module("src.search.research_goal_router")
    case_cfg = {
        "goal_type": "org_dossier",
        "target_org": "Monad",
        "anchors": [
            "Nitro Accelerator",
            "Speedrun",
            "Alliance Accelerator",
        ]
    }
    actions = [
        "expand_apply_and_official_page_queries",
        "bias_official_domains_and_reference_sources",
    ]
    goal_route = goal_module.resolve_goal_route(case_cfg)

    terms = module.build_bootstrap_terms(case_cfg, actions, goal_route)

    assert terms[:3] == [
        "Nitro Accelerator",
        "Speedrun",
        "Alliance Accelerator",
    ]
    assert "Monad" in terms


def test_goal_router_resolves_output_oriented_cases():
    goal_module = importlib.import_module("src.search.research_goal_router")
    route = goal_module.resolve_goal_route(
        {
            "goal_type": "funding_map",
            "recovery_mode": "ecosystem_coverage_recovery",
            "target_ecosystems": ["Monad", "NEAR"],
            "anchors": ["Nitro Accelerator", "NEAR Funding"],
        }
    )

    assert route.goal_type.value == "funding_map"
    assert route.recovery_mode.value == "ecosystem_coverage_recovery"
    assert route.target_ecosystems == ["Monad", "NEAR"]
    assert "Nitro Accelerator" in route.target_entities


def test_build_bootstrap_terms_can_seed_from_case_anchors_on_first_deep_attempt():
    module = _load_research_loop_module()
    case_cfg = {
        "anchors": [
            "Nitro Accelerator",
            "Speedrun",
            "Alliance Accelerator",
        ]
    }

    terms = module.build_bootstrap_terms(
        case_cfg,
        actions=[],
        include_case_anchors=True,
    )

    assert terms == [
        "Nitro Accelerator",
        "Speedrun",
        "Alliance Accelerator",
    ]


def test_build_attempt_policy_escalates_to_deep_when_requested():
    module = _load_research_loop_module()
    profile = module.resolve_profile("HOOT", {"HOOT": {"fixture": "HOOT"}})
    case_cfg = {
        "mode_sequence": ["fast", "fast"],
        "anchors": ["Speedrun"],
    }
    goal = {"met": False}
    actions = ["escalate_to_deep_search", "expand_apply_and_official_page_queries"]

    policy = module.build_attempt_policy(
        attempt_index=1,
        case_cfg=case_cfg,
        profile=profile,
        previous_goal=goal,
        previous_actions=actions,
    )

    assert policy.mode == "deep"
    assert "escalate_to_deep_search" in policy.applied_actions
    assert any("Speedrun" in hint for hint in policy.search_hints)
    assert "Speedrun" in policy.bootstrap_terms


def test_build_attempt_policy_seeds_bootstrap_terms_for_first_deep_attempt():
    module = _load_research_loop_module()
    profile = module.resolve_profile("HOOT", {"HOOT": {"fixture": "HOOT"}})
    case_cfg = {
        "mode_sequence": ["deep"],
        "anchors": ["Nitro Accelerator", "Speedrun"],
    }

    policy = module.build_attempt_policy(
        attempt_index=0,
        case_cfg=case_cfg,
        profile=profile,
    )

    assert policy.mode == "deep"
    assert policy.bootstrap_terms == ["Nitro Accelerator", "Speedrun"]


def test_build_attempt_policy_merges_reflection_seeds():
    module = _load_research_loop_module()
    profile = module.resolve_profile("HOOT", {"HOOT": {"fixture": "HOOT"}})
    goal_module = importlib.import_module("src.search.research_goal_router")
    case_cfg = {
        "id": "hoot_actionable_strategy",
        "goal_type": "actionable_strategy",
        "target_ecosystems": ["Monad"],
        "anchors": ["Nitro Accelerator"],
    }
    goal_route = goal_module.resolve_goal_route(case_cfg)
    reflection = {
        "version": 1,
        "generated_at": "2026-03-15T00:00:00+00:00",
        "source_report_type": "continuous_cycle",
        "overall_goal_met": False,
        "promoted_actions": ["recover_actionable_mix"],
        "case_reflections": [
            {
                "case_id": "hoot_actionable_strategy",
                "goal_type": "actionable_strategy",
                "recovery_mode": "actionable_recovery",
                "progress_score": 0.7,
                "goal_met": False,
                "actions": ["expand_apply_and_official_page_queries"],
                "search_hints": ["Nitro Accelerator apply official"],
                "bootstrap_terms": ["Nitro Accelerator"],
                "target_entities": ["Nitro Accelerator"],
                "target_ecosystems": ["Monad"],
                "matched_anchors": ["Speedrun"],
            }
        ],
    }

    policy = module.build_attempt_policy(
        attempt_index=0,
        case_cfg=case_cfg,
        profile=profile,
        goal_route=goal_route,
        seed_actions=["fallback_to_reference_registry"],
        reflection=reflection,
    )

    assert policy.mode == "deep"
    assert policy.applied_actions[:3] == [
        "fallback_to_reference_registry",
        "recover_actionable_mix",
        "expand_apply_and_official_page_queries",
    ]
    assert "Nitro Accelerator apply official" in policy.search_hints
    assert "Nitro Accelerator" in policy.bootstrap_terms


def test_compute_progress_score_tracks_goal_convergence():
    module = _load_research_loop_module()
    goal_thresholds = {
        "actionable_top10_count": {"gte": 4},
        "profile_specific_recall": {"gte": 0.5},
        "missing_anchor_count": {"lte": 3},
    }

    weak_metrics = {
        "actionable_top10_count": 1,
        "profile_specific_recall": 0.2,
        "missing_anchor_count": 6,
    }
    strong_metrics = {
        "actionable_top10_count": 4,
        "profile_specific_recall": 0.5,
        "missing_anchor_count": 2,
    }

    weak_score = module.compute_progress_score(weak_metrics, goal_thresholds)
    strong_score = module.compute_progress_score(strong_metrics, goal_thresholds)

    assert 0.0 <= weak_score < strong_score <= 1.0
    assert strong_score == 1.0


def test_load_program_reads_json_block_from_markdown(tmp_path: Path):
    module = _load_research_loop_module()
    program_path = tmp_path / "funding_program.md"
    program_path.write_text(
        "# Funding Program\n\n```json\n"
        + json.dumps(
            {
                "name": "funding-autoresearch",
                "seed_actions": ["fallback_to_reference_registry"],
                "continuous": {"max_cycles": 4},
            }
        )
        + "\n```\n",
        encoding="utf-8",
    )

    loaded = module.load_program(program_path)

    assert loaded["name"] == "funding-autoresearch"
    assert loaded["continuous"]["max_cycles"] == 4


def test_resolve_program_seed_actions_merges_global_goal_case_and_carryover_actions():
    module = _load_research_loop_module()
    goal_module = importlib.import_module("src.search.research_goal_router")
    program_cfg = {
        "seed_actions": ["fallback_to_reference_registry"],
        "goal_overrides": {
            "actionable_strategy": {
                "seed_actions": ["recover_actionable_mix"],
            }
        },
    }
    case_cfg = {
        "goal_type": "actionable_strategy",
        "seed_actions": ["expand_apply_and_official_page_queries"],
    }
    goal_route = goal_module.resolve_goal_route(case_cfg)

    actions = module.resolve_program_seed_actions(
        program_cfg,
        case_cfg,
        goal_route,
        carryover_actions=["recover_builder_and_cohort_mix"],
    )

    assert actions == [
        "fallback_to_reference_registry",
        "recover_actionable_mix",
        "expand_apply_and_official_page_queries",
        "recover_builder_and_cohort_mix",
    ]


def test_run_continuous_program_cycles_until_goal_and_appends_tsv(tmp_path: Path):
    module = _load_research_loop_module()
    benchmark = {
        "defaults": {},
        "profiles": {},
        "cases": [{"id": "hoot_actionable_strategy", "goal_type": "actionable_strategy"}],
    }
    reports = [
        {
            "generated_at": "2026-03-12T00:00:00+00:00",
            "report_type": "single_run",
            "case_count": 1,
            "overall_goal_met": False,
            "recommended_actions": ["recover_actionable_mix"],
            "cases": [
                {
                    "case_id": "hoot_actionable_strategy",
                    "goal_type": "actionable_strategy",
                    "recovery_mode": "actionable_recovery",
                    "stop_reason": "continuing_on_progress",
                    "final_progress_score": 0.45,
                    "goal": {"met": False},
                    "final_metrics": {
                        "actionable_top10_count": 2,
                        "output_ready_top10_count": 1,
                        "profile_specific_recall": 0.2,
                        "funding_map_coverage": 0.0,
                        "dossier_fact_completeness": 0.0,
                    },
                    "recommended_actions": ["recover_actionable_mix"],
                }
            ],
        },
        {
            "generated_at": "2026-03-12T00:05:00+00:00",
            "report_type": "single_run",
            "case_count": 1,
            "overall_goal_met": True,
            "recommended_actions": [],
            "cases": [
                {
                    "case_id": "hoot_actionable_strategy",
                    "goal_type": "actionable_strategy",
                    "recovery_mode": "actionable_recovery",
                    "stop_reason": "goal_met",
                    "final_progress_score": 1.0,
                    "goal": {"met": True},
                    "final_metrics": {
                        "actionable_top10_count": 4,
                        "output_ready_top10_count": 3,
                        "profile_specific_recall": 0.6,
                        "funding_map_coverage": 0.0,
                        "dossier_fact_completeness": 0.0,
                    },
                    "recommended_actions": [],
                }
            ],
        },
    ]

    async def fake_run_benchmark(**kwargs):
        return reports.pop(0)

    original = module.run_benchmark
    module.run_benchmark = fake_run_benchmark
    try:
        tsv_path = tmp_path / "results.tsv"
        report = asyncio.run(
            module.run_continuous_program(
                benchmark,
                program_cfg={
                    "name": "funding-autoresearch",
                    "seed_actions": ["fallback_to_reference_registry"],
                    "continuous": {
                        "max_cycles": 3,
                        "plateau_cycles": 2,
                        "min_progress_delta": 0.01,
                    },
                    "reflection": {
                        "latest_path": str(tmp_path / "latest-reflection.json"),
                        "promote_path": str(tmp_path / "promoted-reflection.json"),
                    },
                },
                results_tsv_path=tsv_path,
            )
        )
    finally:
        module.run_benchmark = original

    assert report["report_type"] == "continuous_run"
    assert report["stop_reason"] == "goal_met"
    assert report["cycle_count"] == 2
    assert report["overall_goal_met"] is True
    assert report["reflection_latest_path"] == str(tmp_path / "latest-reflection.json")
    assert (tmp_path / "latest-reflection.json").exists()
    assert (tmp_path / "promoted-reflection.json").exists()
    tsv_text = tsv_path.read_text(encoding="utf-8")
    assert "hoot_actionable_strategy" in tsv_text
    assert "continuous_cycle" in tsv_text
