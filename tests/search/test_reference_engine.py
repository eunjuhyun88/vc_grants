from __future__ import annotations

from src.core.types import CompanyProfile, CompanyStage
from src.search.engines.reference_engine import ReferenceDataEngine


def test_reference_search_priority_terms_boost_matching_program():
    engine = ReferenceDataEngine()
    engine._loaded = True
    engine._records = [
        {
            "organization": "Generic Grants",
            "program": "Open Grants",
            "program_type": "grant",
            "description": "AI infra support for builders",
            "apply_url": "https://generic.example/apply",
            "website": "https://generic.example",
            "sector_tags": "ai_infra,crypto_infra",
            "_source_file": "curated_priority_programs.json",
        },
        {
            "organization": "Monad",
            "program": "Nitro Accelerator",
            "program_type": "vc_cohort",
            "description": "AI infra support for builders",
            "apply_url": "https://nitro.example/apply",
            "website": "https://nitro.example",
            "sector_tags": "ai_infra,crypto_infra",
            "_source_file": "curated_priority_programs.json",
        },
    ]
    profile = CompanyProfile(
        id="cp_hoot",
        company_name="HOOT Labs",
        stage=CompanyStage.MVP,
        sector_tags=["ai_infra", "crypto_infra"],
        target_ecosystems=["Monad"],
        projects=[{"name": "HOOT", "priority": 1}],
    )

    results = engine.search(
        profile,
        top_n=2,
        priority_terms=["Nitro Accelerator"],
    )

    assert [result.program for result in results] == [
        "Nitro Accelerator",
        "Open Grants",
    ]
