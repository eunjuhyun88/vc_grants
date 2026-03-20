#!/usr/bin/env python3
"""
Funding source extractor for the provided fundraising workbook and Folk CSV.

Outputs:
  1. companies-style CSV with the same header shape as Folk `companies.csv`
  2. normalized CSV for repo update planning
  3. Markdown report with overlap/review summary

Usage:
  python scripts/funding_source_extract.py \
    --companies-csv ".../companies.csv" \
    --notes-csv ".../notes.csv" \
    --excel ".../2026-03-06__VC_Fund_Raising_Tracker_221150.xlsx" \
    --companies-output output/spreadsheet/funding_sources_companies_like.csv \
    --normalized-output output/spreadsheet/funding_sources_normalized.csv \
    --report-output output/spreadsheet/funding_sources_report.md
"""

from __future__ import annotations

import argparse
import csv
import re
import uuid
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from openpyxl import load_workbook

COMPANIES_HEADER = [
    "id",
    "name",
    "contactType",
    "favoriteEmail",
    "description",
    "emails",
    "favoriteUrl",
    "urls",
    "favoritePhone",
    "phones",
    "favoriteAddress",
    "addresses",
    "groups",
    "createdAt",
    "createdBy",
    "fundingRaised",
    "lastFundingDate",
    "foundationDate",
    "industry",
    "employeeRange",
    "addedToGroupAt",
    "addedToGroupBy",
    "Category",
    "Grant Budget",
    "Grant Program",
    "Grant URL",
    "Maximum Amount",
]

NORMALIZED_HEADER = [
    "organization",
    "normalized_organization",
    "program",
    "normalized_program",
    "program_type",
    "org_type",
    "source",
    "source_sheet",
    "source_row",
    "status_note",
    "date_note",
    "funding_range",
    "max_amount",
    "website",
    "apply_url",
    "extra_urls",
    "industry_category",
    "sector_tags",
    "description",
    "review_required",
    "review_notes",
]

URL_RE = re.compile(r"https?://[^\s<>\"]+|(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}[^\s<>\"]*")
GENERIC_HOSTS = {
    "airtable.com",
    "calendly.com",
    "discord.com",
    "docs.google.com",
    "farcaster.xyz",
    "forms.gle",
    "google.com",
    "linktr.ee",
    "medium.com",
    "mirror.xyz",
    "notion.site",
    "paragraph.com",
    "reddit.com",
    "t.me",
    "twitter.com",
    "wkf.ms",
    "www.google.com",
    "x.com",
}
SHORTENER_HOSTS = {"wkf.ms", "bit.ly", "tinyurl.com", "t.co"}


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalize_name(text: str) -> str:
    value = safe_text(text).lower()
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -_")


def clean_url(raw: str | None) -> str:
    value = safe_text(raw)
    if not value:
        return ""
    value = value.strip(" ,);]>")
    if not value:
        return ""
    if not value.startswith(("http://", "https://")) and re.match(
        r"^(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}", value
    ):
        value = f"https://{value}"
    return value


def extract_urls(*parts: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for part in parts:
        text = safe_text(part)
        for match in URL_RE.findall(text):
            url = clean_url(match)
            if url and url not in seen:
                urls.append(url)
                seen.add(url)
    return urls


def host_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or parsed.path).lower()
    if host.startswith("www."):
        host = host[4:]
    return host.rstrip("/")


def domain_label(url: str) -> str:
    host = host_from_url(url)
    if not host or host in GENERIC_HOSTS:
        return ""
    parts = host.split(".")
    if len(parts) >= 2:
        return parts[-2]
    return parts[0]


def looks_like_apply_url(url: str) -> bool:
    lowered = url.lower()
    keywords = ["apply", "application", "airtable", "typeform", "form", "submit"]
    return any(keyword in lowered for keyword in keywords)


def titlecase_slug(text: str) -> str:
    value = re.sub(r"[_\-]+", " ", text).strip()
    if not value:
        return ""
    return " ".join(token.capitalize() for token in value.split())


def infer_org_from_program(program: str, urls: list[str]) -> tuple[str, str, list[str]]:
    review_notes: list[str] = []
    value = safe_text(program)
    if not value:
        label = titlecase_slug(domain_label(urls[0])) if urls else ""
        if label:
            review_notes.append("organization inferred from url")
        return label, label, review_notes

    cleaned = re.sub(r"\s*[→\-]+>\s*https?://\S+\s*$", "", value).strip()
    cleaned = re.sub(r"\s*https?://\S+\s*$", "", cleaned).strip()
    cleaned = cleaned.rstrip("→- ").strip()
    lowered = cleaned.lower()

    explicit_pairs = {
        "a16z speedrun": ("a16z", "Speedrun"),
        "accel atoms": ("Accel", "Atoms"),
        "500 global": ("500 Global", "500 Global"),
        "alliance accelerator": ("Alliance", "Alliance Accelerator"),
        "outlier ventures base camp": ("Outlier Ventures", "Base Camp"),
        "y combinator": ("Y Combinator", "Y Combinator"),
        "yzi labs": ("YZi Labs", "YZi Labs"),
    }
    if lowered in explicit_pairs:
        return explicit_pairs[lowered][0], explicit_pairs[lowered][1], review_notes

    if ":" in cleaned:
        head, tail = cleaned.split(":", 1)
        if head.strip() and tail.strip():
            return head.strip(), cleaned.strip(), review_notes

    suffixes = [
        " grants program",
        " grant program",
        " grants",
        " grant",
        " accelerator program",
        " accelerator",
        " ecosystem program",
        " builder program",
        " incubation",
        " incubator",
        " residency program",
        " residency",
        " awards",
    ]
    for suffix in suffixes:
        if lowered.endswith(suffix):
            org = cleaned[: -len(suffix)].strip(" :-")
            if org:
                return org, cleaned, review_notes

    if "(" in cleaned:
        prefix = cleaned.split("(", 1)[0].strip(" :-")
        if prefix:
            return prefix, cleaned, review_notes

    url_label = titlecase_slug(domain_label(urls[0])) if urls else ""
    normalized_cleaned = re.sub(r"\s+", "", cleaned.lower())
    normalized_url = re.sub(r"\s+", "", url_label.lower())
    if url_label and normalized_url not in normalized_cleaned:
        review_notes.append("organization inferred from url")
        return url_label, cleaned, review_notes

    if re.fullmatch(r"\d+", cleaned):
        review_notes.append("program cell is numeric-like and needs review")

    return cleaned, cleaned, review_notes


def choose_primary_urls(urls: list[str]) -> tuple[str, str]:
    website = ""
    apply_url = ""

    for url in urls:
        host = host_from_url(url)
        if looks_like_apply_url(url) and not apply_url:
            apply_url = url
        elif host not in SHORTENER_HOSTS and not website:
            website = url

    if not website and urls:
        website = urls[0]
    if not apply_url and website and looks_like_apply_url(website):
        apply_url = website
    return website, apply_url


def parse_budget(value: Any) -> str:
    text = safe_text(value)
    return text if text and text.lower() not in {"none", "nan", "미지정"} else ""


def extract_sector_tags(category: str, description: str) -> list[str]:
    combined = f"{safe_text(category)} {safe_text(description)}".lower()
    tag_keywords = {
        "ai": ["ai", "agent", "machine learning"],
        "defi": ["defi", "dex", "lending", "yield"],
        "infra": ["infra", "infrastructure", "tooling", "developer"],
        "gaming": ["game", "gaming", "metaverse"],
        "layer1": ["layer-1", "layer 1", "l1"],
        "layer2": ["layer-2", "layer 2", "l2", "rollup"],
        "nft": ["nft"],
        "social": ["social", "community"],
        "storage": ["storage", "data availability", "data"],
    }
    tags = [tag for tag, keywords in tag_keywords.items() if any(k in combined for k in keywords)]
    return sorted(tags)


def make_record(**kwargs: Any) -> dict[str, Any]:
    record = {
        "organization": "",
        "program": "",
        "program_type": "",
        "category": "",
        "org_type": "",
        "source": "",
        "source_sheet": "",
        "source_row": "",
        "status_note": "",
        "date_note": "",
        "funding_range": "",
        "max_amount": "",
        "website": "",
        "apply_url": "",
        "extra_urls": [],
        "industry_category": "",
        "sector_tags": [],
        "description": "",
        "review_required": False,
        "review_notes": [],
    }
    record.update(kwargs)
    return record


def parse_companies_csv(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for idx, row in enumerate(reader, start=2):
            program = safe_text(row.get("Grant Program"))
            organization = safe_text(row.get("name"))
            if not organization and not program:
                continue

            urls = extract_urls(row.get("Grant URL", ""), row.get("favoriteUrl", ""))
            website, apply_url = choose_primary_urls(urls)
            description = safe_text(row.get("description"))
            category = safe_text(row.get("Category"))
            max_amount = parse_budget(row.get("Maximum Amount"))
            funding_range = parse_budget(row.get("Grant Budget"))

            records.append(
                make_record(
                    organization=organization or infer_org_from_program(program, urls)[0],
                    program=program or f"{organization} Grants",
                    program_type="grant",
                    category="grant",
                    org_type="foundation",
                    source="folk_companies",
                    source_sheet="companies.csv",
                    source_row=idx,
                    funding_range=funding_range,
                    max_amount=max_amount,
                    website=website,
                    apply_url=apply_url,
                    extra_urls=urls[1:] if len(urls) > 1 else [],
                    industry_category=category,
                    sector_tags=extract_sector_tags(category, description),
                    description=description,
                )
            )
    return records


def parse_notes_csv(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    return {"row_count": len(rows), "header": reader.fieldnames or []}


def parse_excel_grants(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb["grants program"]
    for idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if idx == 1:
            continue
        grant_name = safe_text(row[1] if len(row) > 1 else "")
        if not grant_name:
            continue

        org_name = safe_text(row[3] if len(row) > 3 else "")
        urls = extract_urls(safe_text(row[2] if len(row) > 2 else ""))
        if not org_name:
            inferred_org, _, infer_notes = infer_org_from_program(grant_name, urls)
        else:
            inferred_org, infer_notes = org_name, []
        website, apply_url = choose_primary_urls(urls)
        description = safe_text(row[5] if len(row) > 5 else "")
        review_notes = list(infer_notes)
        if not website:
            review_notes.append("missing official url")
        records.append(
            make_record(
                organization=inferred_org,
                program=grant_name,
                program_type="grant",
                category="grant",
                org_type="foundation",
                source="excel_grants",
                source_sheet="grants program",
                source_row=idx,
                status_note=safe_text(row[0] if len(row) > 0 else ""),
                date_note=safe_text(row[6] if len(row) > 6 else ""),
                funding_range=parse_budget(row[4] if len(row) > 4 else ""),
                website=website,
                apply_url=apply_url,
                extra_urls=urls[1:] if len(urls) > 1 else [],
                sector_tags=extract_sector_tags("", description),
                description=description,
                review_required=bool(review_notes),
                review_notes=review_notes,
            )
        )
    wb.close()
    return records


def classify_accelerator_program(program: str, urls: list[str]) -> str:
    lowered = program.lower()
    if any(keyword in lowered for keyword in ["speedrun", "incubation", "builder fund", "builders' fund"]):
        return "vc_cohort"
    if any(keyword in lowered for keyword in ["accelerator", "base camp", "yc", "y combinator", "atoms"]):
        return "accelerator"
    label = domain_label(urls[0]) if urls else ""
    if label in {"a16z", "accel", "alliance", "ycombinator"}:
        return "accelerator"
    return "accelerator"


def parse_excel_accelerators(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb["Accelerator Program"]
    header_found = False

    for idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        first = safe_text(row[0] if len(row) > 0 else "")
        third = safe_text(row[2] if len(row) > 2 else "")

        if not header_found:
            if first == "현재상태" and third == "Program":
                header_found = True
            continue

        program_text = third
        status_note = first
        focus = safe_text(row[1] if len(row) > 1 else "")
        funding_range = parse_budget(row[4] if len(row) > 4 else "")
        raw_link = safe_text(row[5] if len(row) > 5 else "")
        raw_notes = safe_text(row[6] if len(row) > 6 else "")
        result = safe_text(row[7] if len(row) > 7 else "")

        if not any([program_text, raw_link, raw_notes, funding_range]):
            continue

        urls = extract_urls(program_text, raw_link)
        organization, program, infer_notes = infer_org_from_program(program_text, urls)
        website, apply_url = choose_primary_urls(urls)

        review_notes = list(infer_notes)
        if not program:
            review_notes.append("missing program name")
        if not website and not apply_url:
            review_notes.append("missing url")
        if website and host_from_url(website) in SHORTENER_HOSTS:
            review_notes.append("primary url is a shortener")
        if len(normalize_name(organization)) < 2 and len(normalize_name(program or organization)) < 2:
            continue

        description_parts = []
        if focus:
            description_parts.append(f"Focus: {focus}")
        if result:
            description_parts.append(f"Result: {result}")
        if raw_notes:
            description_parts.append(f"Submission notes: {raw_notes}")

        records.append(
            make_record(
                organization=organization,
                program=program or organization,
                program_type=classify_accelerator_program(program or organization, urls),
                category="accelerator",
                org_type="accelerator_operator",
                source="excel_accelerators",
                source_sheet="Accelerator Program",
                source_row=idx,
                status_note=status_note,
                date_note=safe_text(row[3] if len(row) > 3 else ""),
                funding_range=funding_range,
                website=website,
                apply_url=apply_url,
                extra_urls=urls[1:] if len(urls) > 1 else [],
                industry_category=focus,
                sector_tags=extract_sector_tags(focus, " ".join(description_parts)),
                description=" | ".join(description_parts),
                review_required=bool(review_notes),
                review_notes=review_notes,
            )
        )

    wb.close()
    return records


def parse_excel_vc(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb["Web3 VC"]
    for idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if idx == 1:
            continue
        organization = safe_text(row[0] if len(row) > 0 else "")
        active = safe_text(row[3] if len(row) > 3 else "")
        if not organization or active.lower() not in {"yes", "y", "true", "1"}:
            continue

        website = clean_url(row[4] if len(row) > 4 else "")
        region = safe_text(row[2] if len(row) > 2 else "")
        tier = safe_text(row[1] if len(row) > 1 else "")

        records.append(
            make_record(
                organization=organization,
                program=f"{organization} Investment",
                program_type="vc_fund",
                category="vc_cohort",
                org_type="vc",
                source="excel_vc",
                source_sheet="Web3 VC",
                source_row=idx,
                status_note=f"active={active}",
                date_note="",
                website=website,
                apply_url="",
                industry_category=region,
                description=f"Active Web3 VC; region={region}; tier={tier}",
            )
        )
    wb.close()
    return records


def dedup_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for rec in records:
        key = (normalize_name(rec["organization"]), normalize_name(rec["program"]))
        if key not in merged:
            copy = dict(rec)
            copy["sources"] = [rec["source"]]
            merged[key] = copy
            continue

        existing = merged[key]
        existing["sources"] = sorted(set(existing["sources"] + [rec["source"]]))
        for field in [
            "website",
            "apply_url",
            "funding_range",
            "max_amount",
            "industry_category",
            "description",
            "status_note",
            "date_note",
        ]:
            if not safe_text(existing.get(field)) and safe_text(rec.get(field)):
                existing[field] = rec[field]
        existing["extra_urls"] = sorted(
            set(existing.get("extra_urls", [])) | set(rec.get("extra_urls", []))
        )
        existing["sector_tags"] = sorted(
            set(existing.get("sector_tags", [])) | set(rec.get("sector_tags", []))
        )
        existing["review_notes"] = sorted(
            set(existing.get("review_notes", [])) | set(rec.get("review_notes", []))
        )
        existing["review_required"] = bool(
            existing.get("review_required") or rec.get("review_required")
        )
    return list(merged.values())


def stable_id(record: dict[str, Any]) -> str:
    key = "|".join(
        [
            normalize_name(record["organization"]),
            normalize_name(record["program"]),
            safe_text(record["source"]),
        ]
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def row_to_companies_shape(record: dict[str, Any], created_at: str) -> dict[str, str]:
    favorite_url = record.get("website") or record.get("apply_url") or ""
    all_urls = [favorite_url] if favorite_url else []
    for extra in record.get("extra_urls", []):
        if extra and extra not in all_urls:
            all_urls.append(extra)
    category = record.get("industry_category") or record.get("program_type") or record.get("category")
    return {
        "id": stable_id(record),
        "name": record.get("organization", ""),
        "contactType": "company",
        "favoriteEmail": "",
        "description": safe_text(record.get("description")),
        "emails": "",
        "favoriteUrl": favorite_url,
        "urls": " | ".join(all_urls),
        "favoritePhone": "",
        "phones": "",
        "favoriteAddress": "",
        "addresses": "",
        "groups": f"Funding Intelligence Import,{record.get('source', '')}",
        "createdAt": created_at,
        "createdBy": "codex",
        "fundingRaised": "",
        "lastFundingDate": "",
        "foundationDate": "",
        "industry": ",".join(record.get("sector_tags", [])),
        "employeeRange": "",
        "addedToGroupAt": created_at,
        "addedToGroupBy": "codex",
        "Category": safe_text(category),
        "Grant Budget": safe_text(record.get("funding_range")),
        "Grant Program": record.get("program", ""),
        "Grant URL": record.get("apply_url") or record.get("website") or "",
        "Maximum Amount": safe_text(record.get("max_amount")),
    }


def write_companies_csv(records: list[dict[str, Any]], output_path: Path) -> None:
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMPANIES_HEADER)
        writer.writeheader()
        for record in records:
            writer.writerow(row_to_companies_shape(record, created_at))


def write_normalized_csv(records: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=NORMALIZED_HEADER)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "organization": record.get("organization", ""),
                    "normalized_organization": normalize_name(record.get("organization", "")),
                    "program": record.get("program", ""),
                    "normalized_program": normalize_name(record.get("program", "")),
                    "program_type": record.get("program_type", ""),
                    "org_type": record.get("org_type", ""),
                    "source": "|".join(record.get("sources", [record.get("source", "")])),
                    "source_sheet": record.get("source_sheet", ""),
                    "source_row": record.get("source_row", ""),
                    "status_note": record.get("status_note", ""),
                    "date_note": record.get("date_note", ""),
                    "funding_range": record.get("funding_range", ""),
                    "max_amount": record.get("max_amount", ""),
                    "website": record.get("website", ""),
                    "apply_url": record.get("apply_url", ""),
                    "extra_urls": " | ".join(record.get("extra_urls", [])),
                    "industry_category": record.get("industry_category", ""),
                    "sector_tags": ",".join(record.get("sector_tags", [])),
                    "description": record.get("description", ""),
                    "review_required": "yes" if record.get("review_required") else "no",
                    "review_notes": " | ".join(record.get("review_notes", [])),
                }
            )


def build_overlap_summary(
    folk_records: list[dict[str, Any]],
    grant_records: list[dict[str, Any]],
) -> dict[str, Any]:
    folk_orgs = {normalize_name(r["organization"]) for r in folk_records}
    excel_orgs = {normalize_name(r["organization"]) for r in grant_records}
    folk_programs = {normalize_name(r["program"]) for r in folk_records}
    excel_programs = {normalize_name(r["program"]) for r in grant_records}
    return {
        "folk_orgs": len(folk_orgs),
        "excel_orgs": len(excel_orgs),
        "org_overlap": len(folk_orgs & excel_orgs),
        "folk_programs": len(folk_programs),
        "excel_programs": len(excel_programs),
        "program_overlap": len(folk_programs & excel_programs),
        "folk_only_org_examples": sorted(folk_orgs - excel_orgs)[:12],
        "excel_only_org_examples": sorted(excel_orgs - folk_orgs)[:12],
    }


def write_report(
    report_path: Path,
    *,
    companies_path: Path,
    notes_path: Path | None,
    excel_path: Path,
    notes_summary: dict[str, Any],
    parsed_counts: Counter,
    deduped: list[dict[str, Any]],
    overlap: dict[str, Any],
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    review_rows = [record for record in deduped if record.get("review_required")]
    program_types = Counter(record.get("program_type", "") for record in deduped)
    sources = Counter()
    for record in deduped:
        for source in record.get("sources", [record.get("source", "")]):
            sources[source] += 1

    lines = [
        "# Funding Source Extract Report",
        "",
        "## Inputs",
        "",
        f"- companies.csv: `{companies_path}`",
        f"- notes.csv: `{notes_path}`" if notes_path else "- notes.csv: not provided",
        f"- workbook: `{excel_path}`",
        "",
        "## Source Facts",
        "",
        f"- Folk companies rows: {parsed_counts['folk_companies']}",
        f"- Excel grants rows parsed: {parsed_counts['excel_grants']}",
        f"- Excel accelerator rows parsed: {parsed_counts['excel_accelerators']}",
        f"- Excel active VC rows parsed: {parsed_counts['excel_vc']}",
        f"- notes.csv rows: {notes_summary['row_count']}",
        f"- Combined deduped records: {len(deduped)}",
        "",
        "## Overlap",
        "",
        f"- Folk vs Excel grant organization overlap: {overlap['org_overlap']} / {overlap['folk_orgs']} Folk orgs, {overlap['excel_orgs']} Excel orgs",
        f"- Folk vs Excel grant program overlap: {overlap['program_overlap']} / {overlap['folk_programs']} Folk programs, {overlap['excel_programs']} Excel programs",
        f"- Folk-only organization examples: {', '.join(overlap['folk_only_org_examples']) or 'none'}",
        f"- Excel-only organization examples: {', '.join(overlap['excel_only_org_examples']) or 'none'}",
        "",
        "## Deduped Mix",
        "",
    ]
    for program_type, count in sorted(program_types.items()):
        lines.append(f"- {program_type}: {count}")

    lines.extend(
        [
            "",
            "## Source Mix",
            "",
        ]
    )
    for source, count in sorted(sources.items()):
        lines.append(f"- {source}: {count}")

    lines.extend(
        [
            "",
            "## Review Required",
            "",
            f"- flagged rows: {len(review_rows)}",
        ]
    )
    for record in review_rows[:20]:
        notes = "; ".join(record.get("review_notes", []))
        lines.append(
            f"- {record['organization']} | {record['program']} | {record['source']} | {notes}"
        )

    lines.extend(
        [
            "",
            "## Recommended Update Path",
            "",
            "- Use the generated `companies`-style CSV when you want a familiar CRM-like flat table.",
            "- Use the normalized CSV when updating `Organization -> Program -> Opportunity` records in the repo.",
            "- Review flagged accelerator rows before importing them into canonical seed data.",
            "- `notes.csv` is currently empty, so it does not add useful enrichment yet.",
        ]
    )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract and normalize funding source data")
    parser.add_argument("--companies-csv", required=True, help="Path to Folk companies.csv")
    parser.add_argument("--notes-csv", default="", help="Path to Folk notes.csv")
    parser.add_argument("--excel", required=True, help="Path to VC fundraising workbook")
    parser.add_argument("--companies-output", required=True, help="Output companies-style CSV path")
    parser.add_argument("--normalized-output", required=True, help="Output normalized CSV path")
    parser.add_argument("--report-output", required=True, help="Output Markdown report path")
    args = parser.parse_args()

    companies_path = Path(args.companies_csv)
    notes_path = Path(args.notes_csv) if args.notes_csv else None
    excel_path = Path(args.excel)

    folk_records = parse_companies_csv(companies_path)
    notes_summary = parse_notes_csv(notes_path) if notes_path and notes_path.exists() else {"row_count": 0, "header": []}
    grant_records = parse_excel_grants(excel_path)
    accelerator_records = parse_excel_accelerators(excel_path)
    vc_records = parse_excel_vc(excel_path)

    all_records = folk_records + grant_records + accelerator_records + vc_records
    deduped = dedup_records(all_records)
    deduped.sort(key=lambda row: (row.get("organization", "").lower(), row.get("program", "").lower()))

    write_companies_csv(deduped, Path(args.companies_output))
    write_normalized_csv(deduped, Path(args.normalized_output))
    write_report(
        Path(args.report_output),
        companies_path=companies_path,
        notes_path=notes_path,
        excel_path=excel_path,
        notes_summary=notes_summary,
        parsed_counts=Counter(
            {
                "folk_companies": len(folk_records),
                "excel_grants": len(grant_records),
                "excel_accelerators": len(accelerator_records),
                "excel_vc": len(vc_records),
            }
        ),
        deduped=deduped,
        overlap=build_overlap_summary(folk_records, grant_records),
    )

    print(f"[DONE] companies-style CSV: {args.companies_output}")
    print(f"[DONE] normalized CSV: {args.normalized_output}")
    print(f"[DONE] report: {args.report_output}")
    print(
        f"[STATS] folk={len(folk_records)} grants={len(grant_records)} "
        f"accelerators={len(accelerator_records)} vc={len(vc_records)} deduped={len(deduped)}"
    )


if __name__ == "__main__":
    main()
