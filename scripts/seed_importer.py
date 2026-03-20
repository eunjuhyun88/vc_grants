#!/usr/bin/env python3
"""
Curated funding CSV -> canonical seed_raw.json converter.

Primary input:
  output/spreadsheet/funding_sources_resolved.csv

This script assumes the raw spreadsheet extraction and manual review workflow has
already happened:
  raw sources -> funding_source_extract.py -> resolve_funding_review_queue.py
  -> funding_sources_resolved.csv -> seed_importer.py -> data/seed_raw.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path


PROGRAM_TYPE_TO_CATEGORY = {
    "grant": "grant",
    "accelerator": "accelerator",
    "vc_cohort": "vc_cohort",
    "vc_fund": "fund",
    "fund": "fund",
    "builder_program": "builder_program",
    "ecosystem_builder": "builder_program",
    "residency": "residency",
    "hackathon_pipeline": "hackathon_pipeline",
}

PROGRAM_TYPE_TO_ORG_TYPE = {
    "grant": "foundation",
    "accelerator": "accelerator",
    "vc_cohort": "vc",
    "vc_fund": "vc",
    "fund": "vc",
    "builder_program": "ecosystem",
    "ecosystem_builder": "ecosystem",
    "residency": "accelerator",
    "hackathon_pipeline": "ecosystem",
}

ROLLING_KEYWORDS = ("rolling",)
OPEN_KEYWORDS = ("open", "active", "accepting", "ongoing", "진행중", "활성", "모집중")
UPCOMING_KEYWORDS = ("upcoming", "coming soon", "opens", "예정")
CLOSED_KEYWORDS = ("closed", "ended", "expired", "마감", "종료")


def clean_url(url: str | None) -> str | None:
    if not url:
        return None
    value = str(url).strip()
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        return None
    return value.rstrip("/")


def parse_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_budget(text: str | None) -> str | None:
    if text is None:
        return None
    value = str(text).strip()
    if value in {"", "None", "nan"}:
        return None
    return value


def parse_tags(raw: str | None) -> list[str]:
    text = parse_text(raw)
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    tags = [part.strip() for part in text.split(",")]
    return [tag for tag in tags if tag]


def infer_status(status_note: str | None, date_note: str | None) -> str:
    combined = " ".join(part for part in [status_note or "", date_note or ""] if part).lower()
    if not combined:
        return "unknown"
    if any(keyword in combined for keyword in ROLLING_KEYWORDS):
        return "rolling"
    if any(keyword in combined for keyword in CLOSED_KEYWORDS):
        return "closed"
    if any(keyword in combined for keyword in UPCOMING_KEYWORDS):
        return "upcoming"
    if any(keyword in combined for keyword in OPEN_KEYWORDS):
        return "open"
    return "unknown"


def map_category(program_type: str | None) -> str:
    key = (program_type or "").strip().lower()
    if key not in PROGRAM_TYPE_TO_CATEGORY:
        raise ValueError(f"Unknown program_type for seed import: {program_type!r}")
    return PROGRAM_TYPE_TO_CATEGORY[key]


def map_org_type(program_type: str | None) -> str:
    key = (program_type or "").strip().lower()
    return PROGRAM_TYPE_TO_ORG_TYPE.get(key, "foundation")


def normalize_key(record: dict) -> tuple[str, str, str]:
    return (
        (record.get("organization") or "").strip().lower(),
        (record.get("program") or "").strip().lower(),
        (record.get("category") or "").strip().lower(),
    )


def merge_records(existing: dict, incoming: dict) -> dict:
    merged = dict(existing)
    for field in [
        "website",
        "program_url",
        "apply_url",
        "funding_range",
        "max_amount",
        "description",
        "status_note",
        "date_note",
        "review_notes",
    ]:
        if not merged.get(field) and incoming.get(field):
            merged[field] = incoming[field]

    for field in ["source_tier", "fact_confidence"]:
        if field in incoming and incoming.get(field) is not None:
            current = merged.get(field)
            if current is None:
                merged[field] = incoming[field]
            elif field == "source_tier":
                merged[field] = min(current, incoming[field])
            else:
                merged[field] = max(current, incoming[field])

    merged["sector_tags"] = sorted(set(merged.get("sector_tags", [])) | set(incoming.get("sector_tags", [])))
    if merged.get("status") == "unknown" and incoming.get("status") != "unknown":
        merged["status"] = incoming["status"]
    return merged


def dedup_records(records: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str, str], dict] = {}
    for record in records:
        key = normalize_key(record)
        if key not in merged:
            merged[key] = dict(record)
            continue
        merged[key] = merge_records(merged[key], record)
    result = list(merged.values())
    result.sort(key=lambda item: (item["organization"].lower(), item["program"].lower()))
    return result


def parse_curated_csv(csv_path: str, include_review: bool = False) -> list[dict]:
    path = Path(csv_path)
    if not path.exists():
        print(f"[ERROR] Curated CSV not found: {csv_path}")
        sys.exit(1)

    records: list[dict] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            review_required = (row.get("review_required") or "").strip().lower() == "yes"
            if review_required and not include_review:
                continue

            organization = (row.get("organization") or "").strip()
            program = (row.get("program") or "").strip()
            program_type = (row.get("program_type") or "").strip()
            if not organization or not program or not program_type:
                continue

            category = map_category(program_type)
            website = clean_url(row.get("website"))
            apply_url = clean_url(row.get("apply_url"))
            status_note = parse_text(row.get("status_note"))
            date_note = parse_text(row.get("date_note"))

            records.append(
                {
                    "organization": organization,
                    "program": program,
                    "category": category,
                    "program_type": program_type,
                    "website": website,
                    "program_url": website,
                    "apply_url": apply_url,
                    "funding_range": parse_budget(row.get("funding_range")),
                    "max_amount": parse_budget(row.get("max_amount")),
                    "org_type": map_org_type(program_type),
                    "sector_tags": parse_tags(row.get("sector_tags")),
                    "description": (row.get("description") or "").strip()[:500] or None,
                    "source": (row.get("source") or "curated_csv").strip(),
                    "status": infer_status(status_note, date_note),
                    "status_note": status_note,
                    "date_note": date_note,
                    "review_notes": parse_text(row.get("review_notes")),
                    "source_tier": 3,
                    "fact_confidence": 0.45 if review_required else 0.6,
                }
            )

    deduped = dedup_records(records)
    print(f"[OK] Curated CSV: {len(records)} rows -> {len(deduped)} seed records")
    return deduped


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build canonical data/seed_raw.json from curated funding CSV"
    )
    parser.add_argument(
        "--curated-csv",
        default="output/spreadsheet/funding_sources_resolved.csv",
        help="Path to curated funding CSV (default: output/spreadsheet/funding_sources_resolved.csv)",
    )
    parser.add_argument(
        "--output",
        default="data/seed_raw.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--include-review",
        action="store_true",
        help="Include review_required=yes rows in the seed output",
    )
    args = parser.parse_args()

    records = parse_curated_csv(
        csv_path=args.curated_csv,
        include_review=args.include_review,
    )
    if not records:
        print("[ERROR] No records found in curated CSV")
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    by_category = Counter(record["category"] for record in records)
    by_org_type = Counter(record["org_type"] for record in records)

    print(f"[DONE] {len(records)} records saved to {output_path}")
    print(f"By category: {dict(sorted(by_category.items()))}")
    print(f"By org_type: {dict(sorted(by_org_type.items()))}")


if __name__ == "__main__":
    main()
