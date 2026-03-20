from __future__ import annotations

from types import SimpleNamespace

from src.core.types import OpportunityCard
from src.interface.handlers.research_handler import (
    _filter_cards_to_actionable,
    _matches_project,
    _primary_project_name,
    _split_project_and_intent,
)
from src.core.types import CompanyProfile
from src.research.dossier_builder import (
    build_org_dossier,
    enrich_cards_from_registry,
    extract_deadline_text,
    is_snapshot_current,
    sanitize_status_note,
)


def test_split_project_and_intent_with_project_only():
    project, intent = _split_project_and_intent(["HOOT"])
    assert project == "HOOT"
    assert intent == "default"


def test_split_project_and_intent_with_intent_suffix():
    project, intent = _split_project_and_intent(["HOOT", "best_fit"])
    assert project == "HOOT"
    assert intent == "best_fit"


def test_matches_project_exact():
    assert _matches_project("HOOT", "HOOT") is True
    assert _matches_project("StockClaw", "HOOT") is False


def test_primary_project_name_ignores_generic_and_null_names():
    profile = CompanyProfile(
        id="cp_test",
        company_name="Infra",
        projects=[
            {"name": "null", "priority": 1, "tags": ["web3"]},
        ],
    )

    assert _primary_project_name(profile) == "내 프로젝트"


def test_filter_cards_to_actionable_prefers_ready_cards():
    ready = OpportunityCard(
        organization="Monad",
        program="Nitro Accelerator",
        category="vc_cohort",
        status="open",
        apply_url="https://nitroacc.xyz/apply",
        confidence=0.9,
        why_fit="crypto infra thesis fit",
        next_action="이번 주 내 지원서 제출",
    )
    partial = OpportunityCard(
        organization="Monad",
        program="Momentum",
        category="builder_program",
        status="open",
        apply_url="https://momentum.monad.xyz",
        confidence=0.7,
        why_fit="ecosystem fit",
        next_action="",
    )
    filtered = _filter_cards_to_actionable([ready, partial], "HOOT")
    assert filtered == [ready]


def test_filter_cards_to_actionable_returns_empty_when_none_ready():
    card = OpportunityCard(
        organization="Alliance",
        program="Alliance Accelerator",
        category="accelerator",
        status="upcoming",
        apply_url="https://alliance.xyz/apply",
        confidence=0.8,
    )
    filtered = _filter_cards_to_actionable([card], "HOOT")
    assert filtered == []


def test_filter_cards_to_actionable_drops_stale_deadline_cards():
    stale = OpportunityCard(
        organization="Old Org",
        program="Old Cohort",
        category="accelerator",
        status="open",
        apply_url="https://old.example/apply",
        confidence=0.7,
        deadline="2026-03-01",
    )
    filtered = _filter_cards_to_actionable([stale], "HOOT")
    assert filtered == []


def test_enrich_cards_from_registry_backfills_description_and_links():
    card = OpportunityCard(
        organization="Monad",
        program="Nitro Accelerator",
        category="vc_cohort",
        status="open",
        apply_url="",
        confidence=0.8,
    )
    registry = [
        {
            "organization": "Monad",
            "program": "Nitro Accelerator",
            "website": "https://nitroacc.xyz",
            "apply_url": "https://nitroacc.xyz/apply",
            "description": "12-week accelerator with mentorship and capital.",
            "funding_range": "Up to $500k per team",
        }
    ]

    enriched = enrich_cards_from_registry([card], registry)[0]

    assert enriched.source_url == "https://nitroacc.xyz"
    assert enriched.apply_url == "https://nitroacc.xyz/apply"
    assert enriched.description == "12-week accelerator with mentorship and capital."
    assert enriched.budget == "Up to $500k per team"


def test_enrich_cards_from_registry_marks_stale_registry_match():
    card = OpportunityCard(
        organization="Monad",
        program="Old Nitro",
        category="vc_cohort",
        status="open",
        apply_url="https://nitroacc.xyz/apply",
        confidence=0.8,
    )
    registry = [
        {
            "organization": "Monad",
            "program": "Old Nitro",
            "website": "https://nitroacc.xyz",
            "status_note": "Applications close March 01, 2026",
        }
    ]

    enriched = enrich_cards_from_registry([card], registry)[0]
    assert is_snapshot_current(enriched) is False


def test_build_org_dossier_uses_program_registry_details():
    graph = {
        "profiles": {},
        "ecosystems": [],
        "organizations": [
            {
                "name": "Monad",
                "aliases": [],
                "ecosystems": ["Monad"],
                "programs": ["Nitro Accelerator"],
                "partners": ["Paradigm"],
                "mentors": ["Electric Capital"],
                "portfolio_analogs": [],
                "official_urls": ["https://monad.xyz"],
            }
        ],
    }
    registry = [
        {
            "organization": "Monad",
            "program": "Nitro Accelerator",
            "program_type": "vc_cohort",
            "website": "https://nitroacc.xyz",
            "apply_url": "https://nitroacc.xyz/apply",
            "description": "12-week accelerator with mentorship and capital.",
            "status_note": "Applications close March 14, 2027",
        }
    ]

    dossier = build_org_dossier(
        "Monad",
        graph,
        ranked_snapshots=[SimpleNamespace(organization="Monad", program="Nitro Accelerator", apply_url="")],
        program_registry=registry,
    )

    assert dossier.program_details
    assert dossier.program_details[0].program == "Nitro Accelerator"
    assert dossier.program_details[0].official_url == "https://nitroacc.xyz"
    assert dossier.program_details[0].apply_url == "https://nitroacc.xyz/apply"
    assert dossier.program_details[0].deadline_text == "March 14, 2027"


def test_build_org_dossier_excludes_stale_registry_programs():
    graph = {
        "profiles": {},
        "ecosystems": [],
        "organizations": [
            {
                "name": "Monad",
                "aliases": [],
                "ecosystems": ["Monad"],
                "programs": ["Old Nitro", "Nitro Accelerator"],
                "partners": [],
                "mentors": [],
                "portfolio_analogs": [],
                "official_urls": [],
            }
        ],
    }
    registry = [
        {
            "organization": "Monad",
            "program": "Old Nitro",
            "website": "https://old.example",
            "status_note": "Applications close March 01, 2026",
        },
        {
            "organization": "Monad",
            "program": "Nitro Accelerator",
            "website": "https://nitroacc.xyz",
            "status_note": "Applications close March 14, 2027",
        },
    ]

    dossier = build_org_dossier("Monad", graph, ranked_snapshots=[], program_registry=registry)
    assert "Old Nitro" not in dossier.programs
    assert all(detail.program != "Old Nitro" for detail in dossier.program_details)


def test_extract_deadline_text_supports_rolling_and_exact_date():
    assert extract_deadline_text("Applications close March 14, 2027") == "March 14, 2027"
    assert extract_deadline_text("Reviewed on a rolling basis") == "Rolling"


def test_extract_deadline_text_drops_past_date():
    assert extract_deadline_text("Applications close March 01, 2026") is None


def test_sanitize_status_note_drops_stale_exact_date_text():
    assert sanitize_status_note("Applications close March 01, 2026") is None
    assert sanitize_status_note("Reviewed on a rolling basis") == "Reviewed on a rolling basis"
