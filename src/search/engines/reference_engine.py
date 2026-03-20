"""
Funding Intelligence Agent — ReferenceDataEngine.

유저의 정규화된 CSV 데이터를 메모리에 로드하고,
프로필 기반으로 관련 항목을 필터링하는 참조 데이터 검색 엔진.

DB 구축 없이 CSV 파일에서 직접 로드.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import structlog

from src.core.types import CompanyProfile
from src.search.profile_query_planner import (
    get_matching_keywords,
    get_priority_ecosystems,
)

logger = structlog.get_logger()

PRIORITY_SOURCE_LIMIT = 24


# ============================================================
# Reference Data Result
# ============================================================

@dataclass
class ReferenceResult:
    """참조 데이터 매칭 결과."""
    source_file: str            # "grant_list_final.csv" 등
    organization: str
    program: str
    program_type: str           # "grant", "accelerator", "vc_fund"
    website: str = ""
    apply_url: str = ""
    funding_range: str = ""
    max_amount: str = ""
    description: str = ""
    sector_tags: str = ""
    industry_category: str = ""
    status_note: str = ""
    match_score: float = 0.0


# ============================================================
# Reference Data Engine
# ============================================================

# 기본 데이터 경로
DEFAULT_DATA_DIR = Path("output/spreadsheet")

# 로드할 CSV 파일 목록
CSV_FILES = {
    "grants": "grant_list_final.csv",
    "accelerators": "accelerator_list_final.csv",
    "vcs": "vc_list_final.csv",
    "funds": "fund_list_final.csv",
}

CURATED_FILES = [
    Path("data/curated_priority_programs.json"),
]


class ReferenceDataEngine:
    """유저 참조 데이터 (CSV) 검색 엔진.

    앱 시작 시 CSV를 메모리에 로드하고,
    프로필의 sector_tags + target_ecosystems로 매칭되는 항목을 반환한다.
    """

    def __init__(self, data_dir: Path | str | None = None) -> None:
        self._data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self._records: list[dict[str, str]] = []
        self._loaded = False
        self._log = logger.bind(component="reference_engine")

    @property
    def loaded(self) -> bool:
        return self._loaded

    @property
    def record_count(self) -> int:
        return len(self._records)

    def load(self) -> int:
        """CSV 파일들을 메모리에 로드. 앱 시작 시 1회 호출.

        Returns:
            로드된 총 레코드 수.
        """
        self._records.clear()

        for category, filename in CSV_FILES.items():
            filepath = self._data_dir / filename
            if not filepath.exists():
                self._log.warning(
                    "reference.file_not_found",
                    file=str(filepath),
                )
                continue

            try:
                count = self._load_csv(filepath, category)
                self._log.info(
                    "reference.loaded",
                    file=filename,
                    records=count,
                )
            except Exception as e:
                self._log.error(
                    "reference.load_error",
                    file=filename,
                    error=str(e),
                )

        for filepath in CURATED_FILES:
            if not filepath.exists():
                continue
            try:
                count = self._load_json(filepath)
                self._log.info(
                    "reference.loaded",
                    file=filepath.name,
                    records=count,
                )
            except Exception as e:
                self._log.error(
                    "reference.load_error",
                    file=filepath.name,
                    error=str(e),
                )

        self._loaded = True
        self._log.info(
            "reference.load_complete",
            total_records=len(self._records),
        )
        return len(self._records)

    def search(
        self,
        profile: CompanyProfile,
        top_n: int = 20,
        priority_terms: list[str] | None = None,
    ) -> list[ReferenceResult]:
        """프로필 기반 매칭 검색.

        Args:
            profile: CompanyProfile (sector_tags, target_ecosystems 등)
            top_n: 반환할 최대 결과 수
            priority_terms: runtime reflection이 밀어주는 프로그램/검색 seed

        Returns:
            match_score 내림차순으로 정렬된 상위 N개 결과.
        """
        if not self._loaded:
            self.load()

        keywords = get_matching_keywords(profile)
        priority_ecosystems = get_priority_ecosystems(profile)
        priority_terms = [term for term in (priority_terms or []) if term]
        if not keywords:
            return []

        results_by_key: dict[str, ReferenceResult] = {}

        for rec in self._records:
            # 매칭 대상 텍스트: description + sector_tags + organization + program + industry
            match_text = " ".join([
                rec.get("description", ""),
                rec.get("sector_tags", ""),
                rec.get("organization", ""),
                rec.get("program", ""),
                rec.get("program_type", ""),
                rec.get("industry_category", ""),
                rec.get("funding_range", ""),
                rec.get("status_note", ""),
            ])

            score = _text_match_score(match_text, keywords)
            score += _funding_goal_bonus(profile.funding_goal, rec.get("program_type", ""))
            score += _industry_bonus(profile, rec)
            score += _ecosystem_bonus(priority_ecosystems, rec)
            score += _quality_bonus(rec)
            score += min(0.36, _priority_record_score(rec, priority_terms) * 0.08)

            if score > 0.10:  # 최소 threshold
                result = ReferenceResult(
                    source_file=rec.get("_source_file", ""),
                    organization=rec.get("organization", ""),
                    program=rec.get("program", ""),
                    program_type=rec.get("program_type", "grant"),
                    website=rec.get("website", ""),
                    apply_url=rec.get("apply_url", ""),
                    funding_range=rec.get("funding_range", ""),
                    max_amount=rec.get("max_amount", ""),
                    description=rec.get("description", ""),
                    sector_tags=rec.get("sector_tags", ""),
                    industry_category=rec.get("industry_category", ""),
                    status_note=rec.get("status_note", ""),
                    match_score=round(min(1.35, score), 4),
                )
                key = _result_key(result)
                existing = results_by_key.get(key)
                if existing is None or result.match_score > existing.match_score:
                    results_by_key[key] = result

        results = list(results_by_key.values())
        results.sort(key=lambda r: r.match_score, reverse=True)
        return results[:top_n]

    def bootstrap_sources(
        self,
        profile: CompanyProfile,
        top_n: int = 12,
        priority_terms: list[str] | None = None,
    ) -> list[str]:
        """공식/apply URL을 direct-fetch seed로 제공한다.

        deep mode가 검색 엔진 quota에 막혀도 reference registry 기반으로
        공식 페이지를 직접 읽을 수 있게 해 주는 bootstrap path다.
        """
        if not self._loaded:
            self.load()

        ranked = self.search(profile, top_n=max(top_n * 2, 20))
        priority_terms = [term for term in (priority_terms or []) if term]
        sources: list[str] = []
        seen: set[str] = set()

        if priority_terms:
            for rec in sorted(
                self._records,
                key=lambda row: _priority_record_score(row, priority_terms),
                reverse=True,
            ):
                if _priority_record_score(rec, priority_terms) <= 0:
                    break
                for url in (rec.get("apply_url", ""), rec.get("website", "")):
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    sources.append(url)
                    if len(sources) >= min(top_n, PRIORITY_SOURCE_LIMIT):
                        return sources

        # priority terms와 직접 맞는 항목을 먼저 올린다.
        prioritized = ranked
        if priority_terms:
            priority_lower = [term.lower() for term in priority_terms]
            prioritized = sorted(
                ranked,
                key=lambda item: any(
                    term in " ".join([item.organization, item.program, item.description]).lower()
                    for term in priority_lower
                ),
                reverse=True,
            )

        for item in prioritized:
            for url in (item.apply_url, item.website):
                if not url or url in seen:
                    continue
                seen.add(url)
                sources.append(url)
                if len(sources) >= top_n:
                    return sources

        return sources

    def to_raw_opportunities(
        self, results: list[ReferenceResult]
    ) -> list[dict[str, Any]]:
        """ReferenceResult → raw_opportunity dict 변환.

        FundingPipeline.ingest_raw_opportunity()와 호환되는 형식.
        """
        raw_opps: list[dict[str, Any]] = []

        for r in results:
            # program_type → category 매핑
            category = _map_program_type(r.program_type)
            status = _parse_status_note(r.status_note)
            program_url = (r.website or "").strip()
            apply_url = _select_apply_url(r)
            primary_url = apply_url or program_url
            source_tier = _infer_source_tier(primary_url)

            # generic VC homepage / stale row / current evidence 없는 row는 raw opp로 승격하지 않는다.
            if status == "closed":
                continue
            if category == "fund" and not apply_url:
                continue
            if not apply_url and status not in {"open", "rolling", "upcoming"}:
                continue

            raw_opps.append({
                "organization": r.organization,
                "program": r.program or f"{r.organization} {category}",
                "category": category,
                "status": status,
                "apply_url": apply_url,
                "program_url": program_url,
                "budget": r.max_amount or r.funding_range,
                "source_url": apply_url or program_url,
                "source_type": "reference_data",
                "description": r.description,
                "focus_areas": _parse_sector_tags(r.sector_tags),
                "confidence": _reference_confidence(status, apply_url, program_url),
                "source_tier": source_tier,
                "fact_confidence": _reference_confidence(status, apply_url, program_url),
            })

        return raw_opps

    # ============================================================
    # Internal
    # ============================================================

    def _load_csv(self, filepath: Path, category: str) -> int:
        """단일 CSV 파일 로드."""
        count = 0
        with open(filepath, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 빈 행 건너뛰기
                if not row.get("organization") and not row.get("program"):
                    continue

                # review_required=yes인 레코드 제외
                if row.get("review_required", "").lower() == "yes":
                    continue

                row["_source_file"] = filepath.name
                row["_category"] = category
                self._records.append(row)
                count += 1

        return count

    def _load_json(self, filepath: Path) -> int:
        """curated JSON 파일 로드."""
        payload = json.loads(filepath.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("curated priority file must be a list")

        count = 0
        for row in payload:
            if not isinstance(row, dict):
                continue
            if not row.get("organization") and not row.get("program"):
                continue
            row["_source_file"] = filepath.name
            row["_category"] = "curated"
            self._records.append({str(k): "" if v is None else str(v) for k, v in row.items()})
            count += 1
        return count


# ============================================================
# 유틸리티 함수
# ============================================================

def _text_match_score(text: str, keywords: list[str]) -> float:
    """키워드가 텍스트에 얼마나 포함되는지 점수 계산.

    키워드 수가 많아도 1~2개 매칭으로 의미있는 점수를 주기 위해
    절대 매칭 수 기반 로그 스케일 점수를 사용한다.

    Args:
        text: 매칭 대상 텍스트
        keywords: 검색 키워드 리스트

    Returns:
        0.0 ~ 1.0 매칭 점수
    """
    if not keywords or not text:
        return 0.0

    text_lower = text.lower()
    matched = sum(1 for kw in keywords if kw.lower() in text_lower)

    if matched == 0:
        return 0.0

    # 절대 매칭 수 기반 점수:
    # 1개 매칭 = 0.15, 2개 = 0.30, 3개 = 0.45, 4개 = 0.55, 5+ = 0.65+
    return min(1.0, matched * 0.15)


def _map_program_type(program_type: str) -> str:
    """CSV의 program_type → Pipeline 호환 category."""
    mapping = {
        "grant": "grant",
        "accelerator": "accelerator",
        "vc_fund": "fund",
        "vc_cohort": "vc_cohort",
        "fund": "fund",
        "builder_program": "builder_program",
        "residency": "residency",
    }
    return mapping.get(program_type.lower(), "grant")


def _parse_sector_tags(tags_str: str) -> list[str]:
    """CSV의 sector_tags 문자열을 리스트로 변환."""
    if not tags_str:
        return []
    # "ai,crypto,infra" → ["ai", "crypto", "infra"]
    return [t.strip() for t in tags_str.split(",") if t.strip()]


def _funding_goal_bonus(funding_goal: str | None, program_type: str) -> float:
    """프로필 funding goal에 맞는 program_type에 보너스를 부여한다."""
    goal = (funding_goal or "").lower()
    ptype = (program_type or "").lower()

    if ptype == "grant" and "grant" in goal:
        return 0.12
    if ptype in {"accelerator", "residency", "builder_program"} and "accelerator" in goal:
        return 0.25
    if ptype == "vc_cohort" and ("seed_vc" in goal or "vc" in goal or "accelerator" in goal):
        return 0.35
    if ptype in {"fund", "vc_fund"} and ("seed_vc" in goal or "vc" in goal):
        return 0.12
    return 0.0


def _industry_bonus(profile: CompanyProfile, record: dict[str, str]) -> float:
    """industry/category와 프로필 섹터가 강하게 맞을 때 보너스."""
    industry = (record.get("industry_category") or "").lower()
    if not industry:
        return 0.0

    sectors = {tag.lower() for tag in profile.sector_tags}
    if "web3" in industry and {"crypto_infra", "defi", "gaming", "social", "dao"} & sectors:
        return 0.15
    if "ai" in industry and {"ai_infra", "ai_evaluation", "decentralized_ai"} & sectors:
        return 0.15
    return 0.0


def _ecosystem_bonus(priority_ecosystems: list[str], record: dict[str, str]) -> float:
    """프로필 우선 ecosystem과 조직/프로그램 텍스트가 겹치면 보너스."""
    if not priority_ecosystems:
        return 0.0

    text = " ".join([
        record.get("organization", ""),
        record.get("program", ""),
        record.get("description", ""),
        record.get("website", ""),
        record.get("apply_url", ""),
    ]).lower()

    matched = sum(1 for eco in priority_ecosystems if eco.lower() in text)
    if matched == 0:
        return 0.0
    return min(0.24, matched * 0.08)


def _quality_bonus(record: dict[str, str]) -> float:
    """reference row가 실제 actionability를 가질수록 작은 보너스를 준다."""
    bonus = 0.0
    if record.get("_source_file") == "curated_priority_programs.json":
        bonus += 0.12
    if record.get("apply_url"):
        bonus += 0.08
    if record.get("website"):
        bonus += 0.04
    if record.get("status_note"):
        bonus += 0.05
    if record.get("description"):
        bonus += 0.03
    return min(0.25, bonus)


def _parse_status_note(status_note: str) -> str:
    """정규화 CSV의 status_note를 pipeline status 값으로 변환."""
    note = (status_note or "").lower().strip()
    if not note:
        return "unknown"

    if any(token in note for token in ("rolling", "롤링", "always open", "상시")):
        return "rolling"
    if any(token in note for token in ("upcoming", "예정", "coming soon", "next cohort")):
        return "upcoming"

    parsed_date = _extract_exact_date(note)
    if parsed_date is not None and parsed_date.date() < datetime.now().date():
        return "closed"

    if any(
        token in note for token in (
            "진행중", "open", "applications open",
            "applications close", "open until", "closes ",
        )
    ):
        return "open"
    if any(token in note for token in ("closed", "마감", "ended", "not accepting")):
        return "closed"
    return "unknown"


def _infer_source_tier(url: str) -> int:
    """참조 데이터의 URL 형태를 기준으로 보수적으로 source tier를 추정."""
    url_lower = (url or "").lower()
    if not url_lower:
        return 3
    if any(host in url_lower for host in ("docs.google.com", "typeform.com", "airtable.com")):
        return 3
    if any(host in url_lower for host in ("x.com", "twitter.com", "t.me", "discord.com")):
        return 5
    return 2


def _result_key(result: ReferenceResult) -> str:
    org = (result.organization or "").strip().lower()
    program = (result.program or "").strip().lower()
    url = (result.apply_url or result.website or "").strip().lower()
    return f"{org}::{program}::{result.program_type.lower()}::{url}"


def _priority_record_score(record: dict[str, str], priority_terms: list[str]) -> float:
    if not priority_terms:
        return 0.0

    text = _normalize_priority_text(
        " ".join([
            record.get("organization", ""),
            record.get("program", ""),
            record.get("description", ""),
            record.get("website", ""),
            record.get("apply_url", ""),
        ])
    )
    if not text:
        return 0.0

    score = 0.0
    for term in priority_terms:
        normalized_term = _normalize_priority_text(term)
        if not normalized_term:
            continue
        if normalized_term in text:
            score += 1.0
        elif all(part in text for part in normalized_term.split()):
            score += 0.7

    if record.get("apply_url"):
        score += 0.15
    if record.get("website"):
        score += 0.10
    if record.get("status_note"):
        score += 0.05
    return score


def _normalize_priority_text(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return " ".join(cleaned.split())


def _extract_exact_date(text: str) -> datetime | None:
    for pattern, fmt in (
        (r"\b\d{4}-\d{2}-\d{2}\b", "%Y-%m-%d"),
        (
            r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},\s+\d{4}\b",
            "%B %d, %Y",
        ),
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        try:
            return datetime.strptime(match.group(0), fmt)
        except ValueError:
            continue
    return None


def _is_direct_apply_surface(url: str) -> bool:
    url_lower = (url or "").lower().strip()
    if not url_lower:
        return False
    parsed = urlparse(url_lower)
    host = parsed.netloc
    path = parsed.path or ""

    if any(host.endswith(form_host) for form_host in ("typeform.com", "airtable.com", "docs.google.com")):
        return True

    apply_like_tokens = (
        "/apply",
        "/application",
        "/accelerator/apply",
        "/grants/apply",
        "/to/",
        "/forms/",
        "apply?",
    )
    return any(token in path for token in apply_like_tokens)


def _is_program_specific_page(url: str) -> bool:
    url_lower = (url or "").lower().strip()
    if not url_lower:
        return False

    parsed = urlparse(url_lower)
    path = (parsed.path or "").strip("/")
    if not path:
        return False

    program_tokens = (
        "grant",
        "grants",
        "funding",
        "accelerator",
        "cohort",
        "residency",
        "program",
        "build",
        "village",
        "colosseum",
        "support",
        "catalyst",
    )
    return any(token in path for token in program_tokens)


def _select_apply_url(result: ReferenceResult) -> str:
    direct_apply = (result.apply_url or "").strip()
    website = (result.website or "").strip()

    if _is_direct_apply_surface(direct_apply):
        return direct_apply
    if _is_direct_apply_surface(website):
        return website
    return ""


def _reference_confidence(status: str, apply_url: str, program_url: str) -> float:
    if status in {"open", "rolling", "upcoming"} and apply_url:
        return 0.78
    if status == "unknown" and _is_program_specific_page(program_url):
        return 0.55
    return 0.45
