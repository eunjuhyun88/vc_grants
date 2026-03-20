from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any


DEFAULT_GRAPH_PATH = Path(__file__).resolve().parents[2] / "data" / "curated_ecosystem_graph.json"
DEFAULT_PROGRAM_REGISTRY_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "curated_priority_programs.json"
)


@dataclass
class ProgramDossier:
    organization: str
    program: str
    program_type: str | None = None
    description: str | None = None
    official_url: str | None = None
    apply_url: str | None = None
    funding_range: str | None = None
    deadline_text: str | None = None
    status_note: str | None = None


@dataclass
class OrganizationDossier:
    organization: str
    ecosystems: list[str] = field(default_factory=list)
    programs: list[str] = field(default_factory=list)
    partners: list[str] = field(default_factory=list)
    mentors: list[str] = field(default_factory=list)
    portfolio_analogs: list[str] = field(default_factory=list)
    matched_programs: list[str] = field(default_factory=list)
    official_urls: list[str] = field(default_factory=list)
    program_details: list[ProgramDossier] = field(default_factory=list)


@dataclass
class FundingMap:
    project_name: str
    tier1_ecosystems: list[str] = field(default_factory=list)
    tier2_ecosystems: list[str] = field(default_factory=list)
    matched_ecosystems: list[str] = field(default_factory=list)
    covered_target_ecosystems: list[str] = field(default_factory=list)


def load_ecosystem_graph(path: Path | None = None) -> dict[str, Any]:
    graph_path = path or DEFAULT_GRAPH_PATH
    if not graph_path.exists():
        return {"profiles": {}, "ecosystems": [], "organizations": []}
    return json.loads(graph_path.read_text(encoding="utf-8"))


def load_program_registry(path: Path | None = None) -> list[dict[str, Any]]:
    registry_path = path or DEFAULT_PROGRAM_REGISTRY_PATH
    if not registry_path.exists():
        return []

    data = json.loads(registry_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def _normalize(value: str | None) -> str:
    return " ".join((value or "").lower().split())


def _match_name(candidates: list[str], text: str) -> bool:
    haystack = _normalize(text)
    return any(_normalize(candidate) in haystack for candidate in candidates if candidate)


def _dedupe_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


_MONTH_DATE_RE = re.compile(
    r"\b("
    r"January|February|March|April|May|June|July|August|September|October|November|December"
    r")\s+\d{1,2},\s+\d{4}\b",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def extract_deadline_text(status_note: str | None) -> str | None:
    text = (status_note or "").strip()
    if not text:
        return None

    iso_match = _ISO_DATE_RE.search(text)
    if iso_match:
        candidate = iso_match.group(0)
        try:
            parsed = datetime.strptime(candidate, "%Y-%m-%d").date()
        except ValueError:
            return None
        if parsed < date.today():
            return None
        return candidate

    month_match = _MONTH_DATE_RE.search(text)
    if month_match:
        candidate = month_match.group(0)
        try:
            parsed = datetime.strptime(candidate, "%B %d, %Y").date()
        except ValueError:
            return None
        if parsed < date.today():
            return None
        return candidate

    normalized = _normalize(text)
    if "rolling" in normalized:
        return "Rolling"
    if "upcoming" in normalized:
        return "Upcoming"
    return None


def sanitize_status_note(status_note: str | None) -> str | None:
    text = (status_note or "").strip()
    if not text:
        return None

    normalized = _normalize(text)
    if "rolling" in normalized or "upcoming" in normalized:
        return text

    if extract_deadline_text(text) is None and (
        _ISO_DATE_RE.search(text) or _MONTH_DATE_RE.search(text)
    ):
        return None
    return text


def is_stale_deadline_text(text: str | None) -> bool:
    return extract_deadline_text(text) is None and bool(
        (text or "").strip()
        and (_ISO_DATE_RE.search(text or "") or _MONTH_DATE_RE.search(text or ""))
    )


def is_registry_entry_current(entry: dict[str, Any]) -> bool:
    status_note = entry.get("status_note")
    normalized = _normalize(str(status_note or ""))
    if "rolling" in normalized or "upcoming" in normalized:
        return True
    if extract_deadline_text(status_note) is not None:
        return True
    if is_stale_deadline_text(str(status_note or "")):
        return False
    return True


def is_snapshot_current(snapshot: Any) -> bool:
    if getattr(snapshot, "_registry_stale", False):
        return False

    status = _normalize(str(getattr(snapshot, "status", "") or ""))
    if status == "closed":
        return False

    days_left = getattr(snapshot, "days_left", None)
    if isinstance(days_left, int) and days_left < 0:
        return False

    deadline = getattr(snapshot, "deadline", None)
    if deadline:
        if is_stale_deadline_text(deadline):
            return False
        deadline_text = extract_deadline_text(deadline)
        if deadline_text is None and (
            _ISO_DATE_RE.search(str(deadline)) or _MONTH_DATE_RE.search(str(deadline))
        ):
            return False

    status_note = getattr(snapshot, "status_note", None)
    if status_note and is_stale_deadline_text(status_note):
        return False

    return True


def lookup_program_registry_entry(
    organization: str,
    program: str,
    program_registry: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    registry = program_registry or load_program_registry()
    target_org = _normalize(organization)
    target_program = _normalize(program)

    exact_program_matches: list[dict[str, Any]] = []
    for entry in registry:
        entry_org = _normalize(str(entry.get("organization") or ""))
        entry_program = _normalize(str(entry.get("program") or ""))
        if target_program and entry_program == target_program:
            exact_program_matches.append(entry)
            if target_org and entry_org == target_org:
                return entry if is_registry_entry_current(entry) else None

    if exact_program_matches:
        for entry in exact_program_matches:
            if is_registry_entry_current(entry):
                return entry
        return None

    combined_target = " ".join(part for part in [target_org, target_program] if part)
    for entry in registry:
        combined_entry = " ".join(
            [
                _normalize(str(entry.get("organization") or "")),
                _normalize(str(entry.get("program") or "")),
            ]
        ).strip()
        if combined_target and combined_target in combined_entry:
            return entry if is_registry_entry_current(entry) else None
    return None


def lookup_any_program_registry_entry(
    organization: str,
    program: str,
    program_registry: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    registry = program_registry or load_program_registry()
    target_org = _normalize(organization)
    target_program = _normalize(program)

    for entry in registry:
        entry_org = _normalize(str(entry.get("organization") or ""))
        entry_program = _normalize(str(entry.get("program") or ""))
        if target_program and entry_program == target_program and (
            not target_org or entry_org == target_org
        ):
            return entry

    combined_target = " ".join(part for part in [target_org, target_program] if part)
    for entry in registry:
        combined_entry = " ".join(
            [
                _normalize(str(entry.get("organization") or "")),
                _normalize(str(entry.get("program") or "")),
            ]
        ).strip()
        if combined_target and combined_target in combined_entry:
            return entry
    return None


def enrich_card_from_registry(
    card: Any,
    program_registry: list[dict[str, Any]] | None = None,
) -> Any:
    entry = lookup_program_registry_entry(
        organization=getattr(card, "organization", ""),
        program=getattr(card, "program", ""),
        program_registry=program_registry,
    )
    if entry is None:
        raw_entry = lookup_any_program_registry_entry(
            organization=getattr(card, "organization", ""),
            program=getattr(card, "program", ""),
            program_registry=program_registry,
        )
        if raw_entry is not None and not is_registry_entry_current(raw_entry):
            setattr(card, "_registry_stale", True)
        return card

    setattr(card, "_registry_stale", False)
    setattr(card, "status_note", sanitize_status_note(entry.get("status_note")))

    if not getattr(card, "source_url", None):
        setattr(card, "source_url", entry.get("website") or entry.get("apply_url"))
    if not getattr(card, "description", None):
        setattr(card, "description", entry.get("description"))
    if not getattr(card, "apply_url", None):
        setattr(card, "apply_url", entry.get("apply_url") or "")
    if not getattr(card, "budget", None):
        setattr(card, "budget", entry.get("funding_range"))
    if not getattr(card, "deadline", None):
        extracted = extract_deadline_text(entry.get("status_note"))
        if extracted:
            setattr(card, "deadline", extracted)
    return card


def enrich_cards_from_registry(
    cards: list[Any],
    program_registry: list[dict[str, Any]] | None = None,
) -> list[Any]:
    registry = program_registry or load_program_registry()
    return [enrich_card_from_registry(card, registry) for card in cards]


def _build_program_dossiers(
    organization: str,
    program_names: list[str],
    program_registry: list[dict[str, Any]],
) -> list[ProgramDossier]:
    details: list[ProgramDossier] = []
    for program_name in _dedupe_preserve(program_names):
        entry = lookup_program_registry_entry(
            organization=organization,
            program=program_name,
            program_registry=program_registry,
        )
        if entry is None:
            raw_entry = lookup_any_program_registry_entry(
                organization=organization,
                program=program_name,
                program_registry=program_registry,
            )
            if raw_entry is not None and not is_registry_entry_current(raw_entry):
                continue
            details.append(
                ProgramDossier(
                    organization=organization,
                    program=program_name,
                )
            )
            continue
        details.append(
            ProgramDossier(
                organization=str(entry.get("organization") or organization),
                program=str(entry.get("program") or program_name),
                program_type=entry.get("program_type"),
                description=entry.get("description"),
                official_url=entry.get("website"),
                apply_url=entry.get("apply_url"),
                funding_range=entry.get("funding_range"),
                deadline_text=extract_deadline_text(entry.get("status_note")),
                status_note=sanitize_status_note(entry.get("status_note")),
            )
        )
    return details


def build_org_dossier(
    organization: str,
    graph: dict[str, Any],
    ranked_snapshots: list[Any] | None = None,
    program_registry: list[dict[str, Any]] | None = None,
) -> OrganizationDossier:
    ranked_snapshots = ranked_snapshots or []
    registry = program_registry or load_program_registry()
    target = _normalize(organization)

    org_entry = None
    for candidate in graph.get("organizations", []):
        names = [candidate.get("name", ""), *(candidate.get("aliases") or [])]
        if any(_normalize(name) == target for name in names if name):
            org_entry = candidate
            break

    if org_entry is None:
        fallback_rows = [
            entry for entry in registry
            if _normalize(str(entry.get("organization") or "")) == target
        ]
        if not fallback_rows:
            return OrganizationDossier(organization=organization)

        program_names = [
            str(entry.get("program") or "")
            for entry in fallback_rows
            if is_registry_entry_current(entry)
        ]
        official_urls = _dedupe_preserve(
            [
                str(entry.get("website") or "")
                for entry in fallback_rows
                if entry.get("website") and is_registry_entry_current(entry)
            ]
        )
        return OrganizationDossier(
            organization=str(fallback_rows[0].get("organization") or organization),
            programs=_dedupe_preserve(program_names),
            official_urls=official_urls,
            program_details=_build_program_dossiers(
                organization=str(fallback_rows[0].get("organization") or organization),
                program_names=program_names,
                program_registry=registry,
            ),
        )

    programs = [str(v) for v in (org_entry.get("programs") or [])]
    matched_programs: list[str] = []
    for snapshot in ranked_snapshots:
        haystack = " ".join(
            [
                getattr(snapshot, "organization", ""),
                getattr(snapshot, "program", ""),
                getattr(snapshot, "apply_url", "") or "",
            ]
        )
        if _match_name([org_entry.get("name", ""), *(org_entry.get("aliases") or [])], haystack):
            matched_programs.append(getattr(snapshot, "program", ""))
            continue
        if _match_name(programs, haystack):
            matched_programs.append(getattr(snapshot, "program", ""))

    dedup_matched = []
    for program in matched_programs:
        if program and program not in dedup_matched:
            dedup_matched.append(program)

    org_name = str(org_entry.get("name") or organization)
    official_urls = _dedupe_preserve([str(v) for v in (org_entry.get("official_urls") or [])])
    program_details = _build_program_dossiers(
        organization=org_name,
        program_names=[*programs, *dedup_matched],
        program_registry=registry,
    )
    combined_programs = _dedupe_preserve([detail.program for detail in program_details] + dedup_matched)
    official_urls = _dedupe_preserve(
        official_urls + [detail.official_url or "" for detail in program_details]
    )

    return OrganizationDossier(
        organization=org_name,
        ecosystems=[str(v) for v in (org_entry.get("ecosystems") or [])],
        programs=combined_programs,
        partners=[str(v) for v in (org_entry.get("partners") or [])],
        mentors=[str(v) for v in (org_entry.get("mentors") or [])],
        portfolio_analogs=[str(v) for v in (org_entry.get("portfolio_analogs") or [])],
        matched_programs=dedup_matched,
        official_urls=official_urls,
        program_details=program_details,
    )


def compute_dossier_fact_completeness(dossier: OrganizationDossier) -> float:
    checks = [
        bool(dossier.organization),
        bool(dossier.ecosystems),
        bool(dossier.programs or dossier.program_details),
        bool(dossier.official_urls),
        bool(dossier.partners or dossier.mentors or dossier.portfolio_analogs),
    ]
    return round(sum(1 for check in checks if check) / len(checks), 4)


def build_project_funding_map(
    project_name: str,
    target_ecosystems: list[str],
    graph: dict[str, Any],
    ranked_snapshots: list[Any],
) -> FundingMap:
    project_cfg = (graph.get("profiles") or {}).get(project_name, {})
    tier1 = [str(v) for v in (project_cfg.get("tier1_ecosystems") or [])]
    tier2 = [str(v) for v in (project_cfg.get("tier2_ecosystems") or [])]

    target_pool = [*target_ecosystems, *tier1, *tier2]
    matched: list[str] = []
    covered_targets: list[str] = []
    for snapshot in ranked_snapshots:
        text = " ".join(
            [
                getattr(snapshot, "organization", ""),
                getattr(snapshot, "program", ""),
                *(getattr(snapshot, "source_chain", []) or []),
            ]
        )
        for eco in graph.get("ecosystems", []):
            aliases = [eco.get("name", ""), *(eco.get("aliases") or []), *((eco.get("programs") or []))]
            if _match_name([str(v) for v in aliases], text):
                name = str(eco.get("name") or "")
                if name and name not in matched:
                    matched.append(name)
                if name in target_pool and name not in covered_targets:
                    covered_targets.append(name)

    return FundingMap(
        project_name=project_name,
        tier1_ecosystems=tier1,
        tier2_ecosystems=tier2,
        matched_ecosystems=matched,
        covered_target_ecosystems=covered_targets,
    )


def compute_funding_map_coverage(funding_map: FundingMap, target_ecosystems: list[str]) -> float:
    target_pool = list(dict.fromkeys([*target_ecosystems, *funding_map.tier1_ecosystems, *funding_map.tier2_ecosystems]))
    if not target_pool:
        return 0.0
    return round(len(funding_map.covered_target_ecosystems) / len(target_pool), 4)
