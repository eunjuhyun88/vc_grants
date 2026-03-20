#!/usr/bin/env python3
"""
Resolve the manual review queue produced by funding_source_extract.py.

This script applies curated overrides to ambiguous rows, deduplicates the result,
and emits final split CSVs plus a smaller remaining review queue.
"""

from __future__ import annotations

import csv
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


NORMALIZED_INPUT = Path("output/spreadsheet/funding_sources_normalized.csv")
OUTPUT_DIR = Path("output/spreadsheet")


def normalize(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def make_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        normalize(row.get("organization", "")),
        normalize(row.get("program", "")),
        normalize(row.get("source", "")),
    )


RESOLUTIONS: dict[tuple[str, str, str], dict[str, Any]] = {
    ("2048", "2048", "excel_accelerators"): {
        "organization": "2048 Ventures",
        "program": "Pre-Seed Fast Track",
        "program_type": "vc_fund",
        "website": "https://www.2048.vc/blog/pre-seed-fast-track",
        "apply_url": "https://airtable.com/appV89PYGo3zN47f9/pagNjeYwHGADSGIs3/form?prefill_Introd+By+Type=Direct&hide_Introd+By+Type=true&prefill_Fast+Track+Opt+In=Yes",
        "funding_range": "$250K-$750K checks for $500K-$1.5M pre-seed rounds",
        "description": "Fast-track pre-seed pitch path for founders raising first rounds.",
        "review_required": "no",
        "review_notes": "resolved from official 2048 Ventures pre-seed fast track page",
    },
    ("500", "500", "excel_accelerators"): {
        "organization": "500 Global",
        "program": "500 Global",
        "website": "https://500.co/",
        "apply_url": "https://mena.aplica.500.co",
        "review_required": "no",
        "review_notes": "merged into canonical 500 Global accelerator row",
    },
    ("a16z", "speedrun", "excel_accelerators"): {
        "organization": "a16z",
        "program": "Speedrun",
        "program_type": "vc_cohort",
        "website": "https://a16z.com/speedrun/",
        "review_required": "no",
        "review_notes": "official a16z speedrun page confirms naming",
    },
    ("antropic", "antropic grants", "excel_accelerators"): {
        "organization": "Anthropic",
        "program": "Anthropic Startup Program",
        "website": "https://www.anthropic.com/startups",
        "apply_url": "https://www.anthropic.com/contact-sales/startup-program",
        "funding_range": "",
        "description": "Anthropic startup benefits program with credits and support for eligible startups.",
        "review_required": "no",
        "review_notes": "resolved from Anthropic startup program pages",
    },
    ("bahamut", "bahamut foundation grants", "excel_grants"): {
        "organization": "Bahamut Foundation",
        "program": "Bahamut Grants",
        "website": "https://www.bahamut.io/grants",
        "apply_url": "https://www.bahamut.io/grants",
        "review_required": "no",
        "review_notes": "resolved from official Bahamut grants page",
    },
    ("base", "base builder grants", "excel_grants"): {
        "website": "https://docs.base.org/get-started/get-funded",
        "apply_url": "https://docs.base.org/get-started/get-funded",
        "review_required": "no",
        "review_notes": "resolved from Base funding documentation",
    },
    ("btv", "the mint", "excel_accelerators"): {
        "organization": "BTV",
        "program": "The Mint",
        "website": "https://www.btv.vc/the-mint",
        "review_required": "no",
        "review_notes": "resolved from official BTV The Mint page",
    },
    ("eranyc", "founders fellowship", "excel_accelerators"): {
        "organization": "ERA",
        "program": "ERA Accelerator",
        "website": "https://www.eranyc.com/apply/",
        "apply_url": "https://www.eranyc.com/apply/",
        "funding_range": "$150K for 6%",
        "review_required": "no",
        "review_notes": "resolved from ERA apply page",
    },
    ("ethereum foundation", "ethereum ecosystem support program", "excel_grants"): {
        "website": "https://esp.ethereum.foundation/about/how-we-support",
        "apply_url": "https://esp.ethereum.foundation/about/how-we-support",
        "review_required": "no",
        "review_notes": "official ESP page confirms program",
    },
    ("fi", "founder institute", "excel_accelerators"): {
        "organization": "Founder Institute",
        "program": "Founder Institute Core Program",
        "website": "https://fi.co/core",
        "apply_url": "https://fi.co/core",
        "review_required": "no",
        "review_notes": "resolved from Founder Institute core program page",
    },
    ("joinef", "entrepreneur first", "excel_accelerators"): {
        "organization": "Entrepreneur First",
        "program": "Entrepreneur First",
        "website": "https://www.joinef.com/",
        "review_required": "no",
        "review_notes": "resolved from official Entrepreneur First site",
    },
    ("launch", "launch", "excel_accelerators"): {
        "organization": "LAUNCH Accelerator",
        "program": "LAUNCH Accelerator",
        "website": "https://launchaccelerator.co/jason",
        "apply_url": "https://launchaccelerator.co/jason",
        "review_required": "no",
        "review_notes": "resolved from official LAUNCH Accelerator page",
    },
    ("menlovc", "menlo ventures x anthropic", "excel_accelerators"): {
        "organization": "Menlo Ventures",
        "program": "Anthology Fund",
        "program_type": "vc_fund",
        "website": "https://menlovc.com/anthology-fund",
        "apply_url": "https://menlovc.com/anthology-fund-application/",
        "funding_range": "$100K+ starting check size; $100M fund",
        "description": "Anthology Fund between Menlo Ventures and Anthropic for AI startups.",
        "review_required": "no",
        "review_notes": "resolved from Menlo Ventures Anthology Fund pages",
    },
    ("mozilla ai accelerator", "mozilla ai accelerator (open source local ai)", "excel_accelerators"): {
        "organization": "Mozilla.ai",
        "program": "Builders in Residence Program",
        "website": "https://www.mozilla.ai/company/bir",
        "apply_url": "https://www.mozilla.ai/company/bir",
        "description": "Mozilla.ai Builders in Residence program for open and applied AI research.",
        "review_required": "no",
        "review_notes": "resolved from Mozilla.ai Builders in Residence page",
    },
    ("oasis", "oasis ecosystem grants", "excel_grants"): {
        "website": "https://oasisprotocol.org/ecosystem-grants",
        "apply_url": "https://oasisprotocol.org/ecosystem-grants",
        "review_required": "no",
        "review_notes": "official Oasis ecosystem grants url already present",
    },
    ("outlierventures", "outlier", "excel_accelerators"): {
        "organization": "Outlier Ventures",
        "program": "Outlier Ventures Base Camp",
        "website": "https://outlierventures.io/apply/form/",
        "apply_url": "https://outlierventures.io/apply/form/",
        "review_required": "no",
        "review_notes": "resolved from official Outlier Ventures apply form",
    },
    ("plugandplaytechcenter", "plug and play ai", "excel_accelerators"): {
        "organization": "Plug and Play Tech Center",
        "program": "Plug and Play AI",
        "review_required": "no",
        "review_notes": "normalized organization name from official domain",
    },
    ("ai2incubator.", "ai2incubator.", "excel_accelerators"): {
        "organization": "AI2 Incubator",
        "program": "AI2 Incubator",
        "website": "https://www.ai2incubator.com/apply",
        "apply_url": "https://www.ai2incubator.com/apply",
        "review_required": "no",
        "review_notes": "normalized slug-like organization name from official domain",
    },
    ("alchemistaccelerator.", "alchemistaccelerator.", "excel_accelerators"): {
        "organization": "Alchemist Accelerator",
        "program": "Alchemist Accelerator",
        "website": "https://www.alchemistaccelerator.com/",
        "review_required": "no",
        "review_notes": "normalized slug-like organization name and canonical homepage",
    },
    ("alliancedao", "alliancedao", "excel_accelerators"): {
        "organization": "Alliance",
        "program": "Alliance Accelerator",
        "website": "https://alliance.xyz/apply",
        "apply_url": "https://alliance.xyz/apply",
        "review_required": "no",
        "review_notes": "normalized legacy AllianceDAO naming to Alliance Accelerator",
    },
    ("monad", "monad", "excel_accelerators"): {
        "organization": "Monad",
        "program": "Monad Momentum",
        "website": "https://momentum.monad.xyz/",
        "apply_url": "https://momentum.monad.xyz/",
        "review_required": "no",
        "review_notes": "normalized program name from Monad Momentum site",
    },
    ("orangedao", "orangedao", "excel_accelerators"): {
        "organization": "OrangeDAO",
        "program": "OrangeDAO",
        "website": "https://refer.orangedao.xyz/berk",
        "apply_url": "https://refer.orangedao.xyz/berk",
        "review_required": "no",
        "review_notes": "normalized organization casing from official domain",
    },
    ("sequoiacap", "sequoia arc", "excel_accelerators"): {
        "organization": "Sequoia Capital",
        "program": "Sequoia Arc",
        "website": "https://www.sequoiacap.com/arc/",
        "apply_url": "https://www.sequoiacap.com/arc/",
        "review_required": "no",
        "review_notes": "resolved from official Sequoia Arc page",
    },
    ("sequoia arc", "sequoia arc (ai-inclusive seed)", "excel_accelerators"): {
        "organization": "Sequoia Capital",
        "program": "Sequoia Arc",
        "website": "https://www.sequoiacap.com/arc/",
        "apply_url": "https://www.sequoiacap.com/arc/",
        "review_required": "no",
        "review_notes": "normalized duplicate Sequoia Arc alias row",
    },
    ("greylock edge", "greylock edge", "excel_accelerators"): {
        "organization": "Greylock",
        "program": "Greylock Edge",
        "website": "https://greylock.com/edge/",
        "apply_url": "https://greylock.com/edge/",
        "review_required": "no",
        "review_notes": "normalized duplicate Greylock Edge alias row",
    },
    ("openai converge", "openai converge", "excel_accelerators"): {
        "organization": "OpenAI Startup Fund",
        "program": "Converge",
        "website": "https://www.openai.fund/",
        "review_required": "no",
        "review_notes": "normalized organization and program naming from OpenAI fund surface",
    },
    ("coinmarketcap", "coinmarketcap", "excel_accelerators"): {
        "organization": "CoinMarketCap",
        "program": "CMC Labs",
        "website": "https://coinmarketcap.com/events/cmc-labs/",
        "apply_url": "https://docs.google.com/forms/d/e/1FAIpQLSeTUxGaMmq1XFZbzfRXrYz-35bNa_LrQhdUL7_8H1sxbCbjzg/viewform",
        "review_required": "no",
        "review_notes": "normalized program name from CMC Labs page",
    },
    ("hfo", "hfo residency", "excel_accelerators"): {
        "organization": "HF0",
        "program": "HF0 Residency",
        "website": "https://www.hf0.com/",
        "review_required": "no",
        "review_notes": "normalized HF0 spelling from official domain",
    },
    ("typeform", "gery look", "excel_accelerators"): {
        "organization": "Greylock",
        "program": "Greylock Edge",
        "website": "https://greylock.com/edge/",
        "apply_url": "https://greylock.com/edge/",
        "description": "Greylock Edge company-building program for exceptional founders.",
        "review_required": "no",
        "review_notes": "resolved from Greylock Edge page; prior row captured Typeform host instead of program",
    },
    ("village global", "village global (ai network)", "excel_accelerators"): {
        "organization": "Village Global",
        "program": "Velocity",
        "website": "https://www.villageglobal.vc/velocity",
        "apply_url": "https://www.villageglobal.vc/velocity/apply",
        "funding_range": "Up to $1M",
        "description": "Village Global pre-seed founder program with capital, network, and AI perks.",
        "review_required": "no",
        "review_notes": "resolved from Village Global Velocity pages",
    },
    ("embed.conviction", "embed.conviction", "excel_accelerators"): {
        "organization": "Conviction",
        "program": "Embed",
        "website": "https://embed.conviction.com/",
        "review_required": "yes",
        "review_notes": "organization/program normalized, but current official apply surface still needs manual confirmation",
    },
    ("firstround", "firstround", "excel_accelerators"): {
        "organization": "First Round Capital",
        "program": "First Round",
        "website": "https://www.firstround.com/",
        "review_required": "yes",
        "review_notes": "organization normalized from domain, but exact current accelerator/program label still needs manual confirmation",
    },
    # Keep these in review with better context rather than force a low-confidence final mapping.
    ("base", "basecamp awards", "excel_grants"): {
        "website": "https://onchainsummer.xyz/",
        "review_required": "yes",
        "review_notes": "likely related to Base onchain awards, but exact canonical program name still needs manual confirmation",
    },
    ("immutable", "immutable zkevm grants", "excel_grants"): {
        "organization": "Immutable",
        "website": "https://www.immutable.com/",
        "review_required": "yes",
        "review_notes": "official Immutable site found, but exact current grant program page was not verified",
    },
    ("interchain foundation", "interchain foundation grants", "excel_grants"): {
        "organization": "Interchain Foundation",
        "website": "https://interchain.io/builders",
        "apply_url": "https://interchain.io/builders",
        "review_required": "yes",
        "review_notes": "official Interchain builders program found, but exact grant-page mapping remains ambiguous",
    },
    ("iterative incubator", "iterative incubator (ai dev tools)", "excel_accelerators"): {
        "review_required": "yes",
        "review_notes": "no reliable official incubator page was verified; keep out of final import set",
    },
}


BASE_FIELDS = [
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

QUALITY_AUDIT_FIELDS = [
    "organization",
    "program",
    "program_type",
    "source",
    "issue_flags",
    "website",
    "apply_url",
    "review_notes",
]


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def apply_resolutions(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    resolved_log: list[dict[str, str]] = []
    updated: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []

    for row in rows:
        rec = dict(row)
        key = make_key(rec)
        resolution = RESOLUTIONS.get(key)
        if resolution:
            for field, value in resolution.items():
                rec[field] = value
            resolved_log.append(
                {
                    "original_organization": row["organization"],
                    "original_program": row["program"],
                    "source": row["source"],
                    "resolved_organization": rec["organization"],
                    "resolved_program": rec["program"],
                    "program_type": rec["program_type"],
                    "review_required": rec["review_required"],
                    "review_notes": rec["review_notes"],
                }
            )
        updated.append(rec)
        if rec.get("review_required") == "yes":
            unresolved.append(rec)
    return updated, unresolved, resolved_log


def dedup(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (
            normalize(row["organization"]),
            normalize(row["program"]),
            normalize(row["program_type"]),
        )
        if key not in merged:
            merged[key] = dict(row)
            continue
        existing = merged[key]
        for field in [
            "status_note",
            "date_note",
            "funding_range",
            "max_amount",
            "website",
            "apply_url",
            "industry_category",
            "sector_tags",
            "description",
            "review_notes",
        ]:
            if not (existing.get(field) or "").strip() and (row.get(field) or "").strip():
                existing[field] = row[field]
        if existing.get("source") and row.get("source") and row["source"] not in existing["source"].split("|"):
            existing["source"] = f"{existing['source']}|{row['source']}"
        existing["review_required"] = "yes" if "yes" in {existing.get("review_required"), row.get("review_required")} else "no"
    result = list(merged.values())
    result.sort(key=lambda r: (r["organization"].lower(), r["program"].lower()))
    return result


def write_csv(path: Path, rows: list[dict[str, str]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in headers})


def normalize_for_id(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def stable_id(row: dict[str, str]) -> str:
    key = "|".join(
        [
            normalize_for_id(row.get("organization", "")),
            normalize_for_id(row.get("program", "")),
            normalize_for_id(row.get("source", "")),
        ]
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def build_companies_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    result: list[dict[str, str]] = []
    for row in rows:
        favorite_url = row.get("website") or row.get("apply_url") or ""
        urls: list[str] = []
        for candidate in [row.get("website", ""), row.get("apply_url", "")]:
            if candidate and candidate not in urls:
                urls.append(candidate)
        result.append(
            {
                "id": stable_id(row),
                "name": row.get("organization", ""),
                "contactType": "company",
                "favoriteEmail": "",
                "description": row.get("description", ""),
                "emails": "",
                "favoriteUrl": favorite_url,
                "urls": " | ".join(urls),
                "favoritePhone": "",
                "phones": "",
                "favoriteAddress": "",
                "addresses": "",
                "groups": f"Funding Intelligence Import,{row.get('source', '')}",
                "createdAt": created_at,
                "createdBy": "codex",
                "fundingRaised": "",
                "lastFundingDate": "",
                "foundationDate": "",
                "industry": row.get("sector_tags", ""),
                "employeeRange": "",
                "addedToGroupAt": created_at,
                "addedToGroupBy": "codex",
                "Category": row.get("industry_category") or row.get("program_type", ""),
                "Grant Budget": row.get("funding_range", ""),
                "Grant Program": row.get("program", ""),
                "Grant URL": row.get("apply_url") or row.get("website") or "",
                "Maximum Amount": row.get("max_amount", ""),
            }
        )
    return result


def build_quality_audit_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    allowed_lowercase_orgs = {"a16z", "1kx", "orangeDAO".lower()}
    audit: list[dict[str, str]] = []
    for row in rows:
        flags: list[str] = []
        organization = row.get("organization", "")
        program = row.get("program", "")
        program_type = row.get("program_type", "")
        website = row.get("website", "")
        apply_url = row.get("apply_url", "")

        if row.get("review_required") == "yes":
            flags.append("review_required")
        if organization and organization.lower() == organization and organization.lower() not in allowed_lowercase_orgs:
            flags.append("org_all_lowercase")
        if organization.endswith("."):
            flags.append("org_trailing_dot")
        if re.fullmatch(r"[A-Za-z0-9._-]+", organization or "") and " " not in organization and len(organization) > 10:
            flags.append("org_slug_like")
        if organization and program and organization.strip().lower() == program.strip().lower() and program_type not in {"grant", "vc_fund"}:
            flags.append("org_equals_program")
        if program_type in {"accelerator", "vc_cohort"} and not apply_url:
            flags.append("missing_apply_url_for_cohort")
        for field_name, value in [("website", website), ("apply_url", apply_url)]:
            if value:
                host = urlparse(value).netloc.lower()
                if host and "." not in host:
                    flags.append(f"invalid_{field_name}_host")
        if flags:
            audit.append(
                {
                    "organization": organization,
                    "program": program,
                    "program_type": program_type,
                    "source": row.get("source", ""),
                    "issue_flags": ",".join(sorted(set(flags))),
                    "website": website,
                    "apply_url": apply_url,
                    "review_notes": row.get("review_notes", ""),
                }
            )
    audit.sort(key=lambda item: (item["organization"].lower(), item["program"].lower()))
    return audit


def main() -> None:
    rows = load_rows(NORMALIZED_INPUT)
    updated, unresolved, resolved_log = apply_resolutions(rows)
    deduped = dedup(updated)

    final_clean = [row for row in deduped if row.get("review_required") != "yes"]
    remaining_review = [row for row in deduped if row.get("review_required") == "yes"]

    vc = [row for row in final_clean if row["program_type"] == "vc_fund"]
    grants = [row for row in final_clean if row["program_type"] == "grant"]
    accelerators = [row for row in final_clean if row["program_type"] in {"accelerator", "vc_cohort"}]
    fund = [row for row in final_clean if row["program_type"] in {"grant", "accelerator", "vc_cohort"}]
    companies_like = build_companies_rows(final_clean)
    quality_audit = build_quality_audit_rows(final_clean)

    write_csv(OUTPUT_DIR / "funding_sources_resolved.csv", deduped, BASE_FIELDS)
    write_csv(OUTPUT_DIR / "review_resolution_log.csv", resolved_log, list(resolved_log[0].keys()) if resolved_log else [])
    write_csv(OUTPUT_DIR / "review_queue_remaining.csv", remaining_review, BASE_FIELDS)
    write_csv(OUTPUT_DIR / "vc_list_final.csv", vc, BASE_FIELDS)
    write_csv(OUTPUT_DIR / "grant_list_final.csv", grants, BASE_FIELDS)
    write_csv(OUTPUT_DIR / "accelerator_list_final.csv", accelerators, BASE_FIELDS)
    write_csv(OUTPUT_DIR / "fund_list_final.csv", fund, BASE_FIELDS)
    write_csv(OUTPUT_DIR / "funding_sources_companies_like_final.csv", companies_like, COMPANIES_HEADER)
    write_csv(OUTPUT_DIR / "final_quality_audit.csv", quality_audit, QUALITY_AUDIT_FIELDS)

    summary = [
        "# Funding Review Resolution Summary",
        "",
        f"- input rows: {len(rows)}",
        f"- resolved log rows: {len(resolved_log)}",
        f"- deduped rows after resolution: {len(deduped)}",
        f"- final clean rows: {len(final_clean)}",
        f"- remaining review rows: {len(remaining_review)}",
        f"- final vc rows: {len(vc)}",
        f"- final grant rows: {len(grants)}",
        f"- final accelerator/cohort rows: {len(accelerators)}",
        f"- final fund rows: {len(fund)}",
        f"- quality audit rows: {len(quality_audit)}",
        "",
        "## Remaining Review Items",
        "",
    ]
    for row in remaining_review:
        summary.append(f"- {row['organization']} | {row['program']} | {row['review_notes']}")
    summary.append("")
    summary.append("## Program Type Mix")
    summary.append("")
    counts = Counter(row["program_type"] for row in final_clean)
    for key, value in sorted(counts.items()):
        summary.append(f"- {key}: {value}")
    (OUTPUT_DIR / "resolution_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    print(f"[DONE] final clean rows={len(final_clean)} remaining_review={len(remaining_review)}")
    print(f"[DONE] vc={len(vc)} grants={len(grants)} accelerators={len(accelerators)} fund={len(fund)}")
    print(f"[DONE] quality_audit={len(quality_audit)} companies_like={len(companies_like)}")


if __name__ == "__main__":
    main()
