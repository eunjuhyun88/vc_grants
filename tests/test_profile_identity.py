from __future__ import annotations

from src.core.profile_identity import (
    infer_default_project_from_text,
    merge_projects,
    primary_project_name,
    repair_profile_identity,
    resolve_profile_draft,
)
from src.core.types import CompanyProfile, CompanyStage


def test_primary_project_name_ignores_generic_values():
    profile = CompanyProfile(
        id="cp_generic",
        company_name="Infra",
        stage=CompanyStage.MVP,
        projects=[{"name": "null", "priority": 1, "tags": ["web3"]}],
    )

    assert primary_project_name(profile) is None
    assert primary_project_name(profile, fallback="내 프로젝트") == "내 프로젝트"


def test_infer_default_project_from_text_detects_hoot_signature():
    text = (
        "개인 데이터 기반 small model training 하고 "
        "distributed compute + blockchain coordination 구조야"
    )
    assert infer_default_project_from_text(text) == "HOOT"


def test_resolve_profile_draft_uses_known_project_when_llm_name_is_generic():
    existing = CompanyProfile(
        id="cp_hoot",
        company_name="Holo Studio Co., Ltd.",
        stage=CompanyStage.MVP,
        sector_tags=["ai_infra", "crypto_infra"],
        target_ecosystems=["ethereum"],
        projects=[{"name": "HOOT", "priority": 1, "tags": ["ai_infra"]}],
    )

    draft = resolve_profile_draft(
        original_text="HOOT 기준 지금 funding 정리해줘",
        profile_info={"company_name": "Infra", "project_name": "null"},
        existing_profile=existing,
    )

    assert draft is not None
    assert draft.project_name == "HOOT"
    assert draft.company_name == "Holo Studio Co., Ltd."


def test_resolve_profile_draft_returns_none_when_identity_is_unknown():
    draft = resolve_profile_draft(
        original_text="우리 프로젝트는 infra 쪽이야",
        profile_info={"company_name": "Infra", "project_name": "null"},
        existing_profile=None,
    )
    assert draft is None


def test_merge_projects_preserves_existing_projects_and_updates_target():
    merged = merge_projects(
        [
            {"name": "HOOT", "priority": 1, "tags": ["ai_infra"]},
            {"name": "StockClaw", "priority": 2, "tags": ["analytics"]},
        ],
        "HOOT",
        ["distributed_compute", "ai_infra"],
    )

    assert merged[0]["name"] == "HOOT"
    assert "distributed_compute" in merged[0]["tags"]
    assert any(item["name"] == "StockClaw" for item in merged)


def test_repair_profile_identity_recovers_hoot_from_signature_text():
    broken = CompanyProfile(
        id="cp_broken",
        company_name="Infra",
        stage=None,
        sector_tags=["ai", "web3"],
        projects=[{"name": "null", "priority": 1, "tags": ["crypto"]}],
        product_summary="personal small model training with distributed compute and blockchain coordination",
    )

    repaired = repair_profile_identity(broken)

    assert repaired is not None
    assert repaired.company_name == "Holo Studio Co., Ltd."
    assert repaired.projects[0]["name"] == "HOOT"
    assert "ethereum" in repaired.target_ecosystems
