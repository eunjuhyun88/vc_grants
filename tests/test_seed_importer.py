from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


def test_seed_importer_builds_seed_from_curated_csv(tmp_path: Path):
    csv_path = tmp_path / "funding_sources_resolved.csv"
    output_path = tmp_path / "seed_raw.json"
    fieldnames = [
        "organization",
        "program",
        "program_type",
        "source",
        "status_note",
        "date_note",
        "funding_range",
        "max_amount",
        "website",
        "apply_url",
        "industry_category",
        "sector_tags",
        "description",
        "review_required",
        "review_notes",
    ]
    rows = [
        {
            "organization": "1kx",
            "program": "1kx Investment",
            "program_type": "vc_fund",
            "source": "excel_vc",
            "status_note": "active",
            "date_note": "",
            "funding_range": "",
            "max_amount": "",
            "website": "https://1kx.network/",
            "apply_url": "",
            "industry_category": "vc",
            "sector_tags": "crypto,web3",
            "description": "Active web3 fund",
            "review_required": "no",
            "review_notes": "",
        },
        {
            "organization": "Alliance",
            "program": "Alliance Accelerator",
            "program_type": "accelerator",
            "source": "excel_accelerators",
            "status_note": "진행중",
            "date_note": "",
            "funding_range": "$500K",
            "max_amount": "",
            "website": "https://alliance.xyz/apply",
            "apply_url": "https://alliance.xyz/apply",
            "industry_category": "accelerator",
            "sector_tags": "ai,crypto",
            "description": "Alliance cohort",
            "review_required": "no",
            "review_notes": "",
        },
        {
            "organization": "Base",
            "program": "BaseCamp Awards",
            "program_type": "grant",
            "source": "excel_grants",
            "status_note": "",
            "date_note": "마감 2025-09-02",
            "funding_range": "$250K",
            "max_amount": "",
            "website": "https://onchainsummer.xyz/",
            "apply_url": "",
            "industry_category": "grant",
            "sector_tags": "ecosystem",
            "description": "Needs review",
            "review_required": "yes",
            "review_notes": "manual confirmation needed",
        },
    ]

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    repo_root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [
            sys.executable,
            "scripts/seed_importer.py",
            "--curated-csv",
            str(csv_path),
            "--output",
            str(output_path),
        ],
        cwd=repo_root,
        check=True,
    )

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(data) == 2

    by_program = {row["program"]: row for row in data}
    assert by_program["1kx Investment"]["category"] == "fund"
    assert by_program["1kx Investment"]["org_type"] == "vc"
    assert by_program["1kx Investment"]["status"] == "open"
    assert by_program["Alliance Accelerator"]["category"] == "accelerator"
    assert by_program["Alliance Accelerator"]["apply_url"] == "https://alliance.xyz/apply"
    assert by_program["Alliance Accelerator"]["program_url"] == "https://alliance.xyz/apply"
