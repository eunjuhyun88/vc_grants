from __future__ import annotations

from dataclasses import dataclass

from src.core.profiles import get_default_profile
from src.core.types import CompanyProfile, CompanyStage


GENERIC_NAME_STOPWORDS = {
    "infra", "ai", "web3", "crypto", "blockchain", "protocol", "grant",
    "grants", "accelerator", "cohort", "fund", "funding", "builder", "program",
    "tooling", "network", "agent", "agents", "null", "none", "unknown",
    "my project", "project", "startup", "company",
}

DEFAULT_PROFILE_SIGNATURES: dict[str, tuple[str, ...]] = {
    "HOOT": (
        "distributed compute",
        "blockchain coordination",
        "personal model",
        "small model",
        "torrent",
        "decentralized ai",
        "agent infrastructure",
        "ai infrastructure",
    ),
}


@dataclass
class NormalizedProfileDraft:
    company_name: str
    project_name: str
    stage: CompanyStage
    sector_tags: list[str]
    target_ecosystems: list[str]
    description: str


def normalize_text(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def is_generic_name(value: str | None) -> bool:
    normalized = normalize_text(value)
    return not normalized or normalized in GENERIC_NAME_STOPWORDS


def primary_project_name(
    profile: CompanyProfile | None,
    fallback: str | None = None,
) -> str | None:
    if profile and profile.projects:
        ordered = sorted(profile.projects, key=lambda item: item.get("priority", 999))
        for item in ordered:
            name = (item.get("name") or "").strip()
            if name and not is_generic_name(name):
                return name
    if profile and profile.company_name and not is_generic_name(profile.company_name):
        return profile.company_name
    return fallback


def known_project_names(profile: CompanyProfile | None = None) -> list[str]:
    names: list[str] = []

    def _add(candidate: str | None) -> None:
        if candidate and not is_generic_name(candidate) and candidate not in names:
            names.append(candidate)

    if profile:
        for item in profile.projects or []:
            _add((item.get("name") or "").strip())
        _add(profile.company_name)

    default_profile = get_default_profile("HOOT")
    if default_profile:
        for item in default_profile.projects or []:
            _add((item.get("name") or "").strip())
        _add(default_profile.company_name)

    return names


def extract_name_from_text(text: str, candidates: list[str]) -> str | None:
    normalized_text = normalize_text(text)
    matched: list[tuple[int, str]] = []
    for candidate in candidates:
        if is_generic_name(candidate):
            continue
        normalized_candidate = normalize_text(candidate)
        if normalized_candidate and normalized_candidate in normalized_text:
            matched.append((len(normalized_candidate), candidate))
    if not matched:
        return None
    matched.sort(key=lambda item: item[0], reverse=True)
    return matched[0][1]


def infer_default_project_from_text(text: str) -> str | None:
    normalized = normalize_text(text)
    for project_name, signature_terms in DEFAULT_PROFILE_SIGNATURES.items():
        if normalize_text(project_name) in normalized:
            return project_name
        hits = sum(1 for term in signature_terms if term in normalized)
        if hits >= 2:
            return project_name
    return None


def normalize_sector_tags(tags: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for tag in tags or []:
        candidate = normalize_text(tag).replace(" ", "_")
        if candidate and candidate not in normalized:
            normalized.append(candidate)
    return normalized


def normalize_ecosystems(ecosystems: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for ecosystem in ecosystems or []:
        candidate = normalize_text(ecosystem)
        if candidate and candidate not in normalized and candidate not in {"없음", "none"}:
            normalized.append(candidate)
    return normalized


def merge_unique_strings(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for value in group:
            if value and value not in merged:
                merged.append(value)
    return merged


def merge_projects(
    existing_projects: list[dict] | None,
    project_name: str,
    tags: list[str],
) -> list[dict]:
    merged: list[dict] = []
    matched = False
    target_key = normalize_text(project_name)

    for item in existing_projects or []:
        current_name = (item.get("name") or "").strip()
        current_key = normalize_text(current_name)
        if current_name and current_key == target_key:
            merged.append(
                {
                    "name": current_name,
                    "priority": item.get("priority", 1),
                    "tags": merge_unique_strings(item.get("tags", []), tags[:5]),
                }
            )
            matched = True
        else:
            merged.append(item)

    if not matched:
        merged.insert(
            0,
            {
                "name": project_name,
                "priority": 1,
                "tags": tags[:5],
            },
        )

    return merged


def resolve_profile_draft(
    *,
    original_text: str,
    profile_info: dict,
    existing_profile: CompanyProfile | None = None,
) -> NormalizedProfileDraft | None:
    explicit_project = profile_info.get("project_name")
    explicit_company = profile_info.get("company_name")

    chosen_project = None
    if explicit_project and not is_generic_name(explicit_project):
        chosen_project = explicit_project.strip()
    elif explicit_company and not is_generic_name(explicit_company):
        chosen_project = explicit_company.strip()
    else:
        chosen_project = extract_name_from_text(original_text, known_project_names(existing_profile))
        if chosen_project is None:
            chosen_project = infer_default_project_from_text(original_text)
        if chosen_project is None:
            chosen_project = primary_project_name(existing_profile)

    if not chosen_project or is_generic_name(chosen_project):
        return None

    base_profile = None
    if existing_profile and chosen_project in known_project_names(existing_profile):
        base_profile = existing_profile
    else:
        base_profile = get_default_profile(chosen_project)

    stage_str = normalize_text(profile_info.get("stage"))
    valid_stages = {stage.value: stage for stage in CompanyStage}
    stage = (
        valid_stages.get(stage_str)
        or (base_profile.stage if base_profile and base_profile.stage else None)
        or CompanyStage.MVP
    )

    sector_tags = normalize_sector_tags(profile_info.get("sector_tags"))
    if base_profile:
        sector_tags = merge_unique_strings(sector_tags, base_profile.sector_tags)
    if not sector_tags:
        sector_tags = ["crypto"]

    ecosystems = normalize_ecosystems(profile_info.get("target_ecosystems"))
    if base_profile:
        ecosystems = merge_unique_strings(ecosystems, base_profile.target_ecosystems)

    company_name = (
        explicit_company.strip()
        if explicit_company and not is_generic_name(explicit_company)
        else (
            base_profile.company_name
            if base_profile and not is_generic_name(base_profile.company_name)
            else chosen_project
        )
    )

    description = (
        (profile_info.get("project_description") or "").strip()
        or (base_profile.product_summary if base_profile and base_profile.product_summary else "")
        or original_text[:140]
    )

    return NormalizedProfileDraft(
        company_name=company_name,
        project_name=chosen_project,
        stage=stage,
        sector_tags=sector_tags,
        target_ecosystems=ecosystems,
        description=description,
    )


def repair_profile_identity(profile: CompanyProfile | None) -> CompanyProfile | None:
    if profile is None:
        return None
    if primary_project_name(profile) is not None:
        return profile

    inference_source = " ".join(
        part
        for part in [
            profile.product_summary or "",
            profile.description or "",
            " ".join(profile.sector_tags),
            " ".join(profile.subsector_tags),
            " ".join(profile.target_ecosystems),
        ]
        if part
    )
    inferred_project = infer_default_project_from_text(inference_source)
    if inferred_project is None:
        return profile

    default_profile = get_default_profile(inferred_project)
    if default_profile is None:
        return profile

    merged_tags = merge_unique_strings(profile.sector_tags, default_profile.sector_tags)
    merged_ecosystems = merge_unique_strings(profile.target_ecosystems, default_profile.target_ecosystems)
    merged_projects = merge_projects(profile.projects or default_profile.projects, inferred_project, merged_tags)

    return CompanyProfile(
        id=profile.id,
        company_name=(
            profile.company_name
            if not is_generic_name(profile.company_name)
            else default_profile.company_name
        ),
        stage=profile.stage or default_profile.stage,
        sector_tags=merged_tags,
        subsector_tags=merge_unique_strings(profile.subsector_tags, default_profile.subsector_tags),
        projects=merged_projects,
        description=profile.description,
        geography=profile.geography or default_profile.geography,
        funding_goal=profile.funding_goal or default_profile.funding_goal,
        product_summary=profile.product_summary or default_profile.product_summary,
        target_ecosystems=merged_ecosystems,
        telegram_user_id=profile.telegram_user_id,
        updated_at=profile.updated_at,
    )
