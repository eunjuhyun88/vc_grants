"""
Funding Intelligence Agent — ReferenceDataEngine.

유저의 정규화된 CSV 데이터를 메모리에 로드하고,
프로필 기반으로 관련 항목을 필터링하는 참조 데이터 검색 엔진.

DB 구축 없이 CSV 파일에서 직접 로드.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from src.core.types import CompanyProfile
from src.search.profile_query_planner import get_matching_keywords

logger = structlog.get_logger()


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
    ) -> list[ReferenceResult]:
        """프로필 기반 매칭 검색.

        Args:
            profile: CompanyProfile (sector_tags, target_ecosystems 등)
            top_n: 반환할 최대 결과 수

        Returns:
            match_score 내림차순으로 정렬된 상위 N개 결과.
        """
        if not self._loaded:
            self.load()

        keywords = get_matching_keywords(profile)
        if not keywords:
            return []

        results: list[ReferenceResult] = []

        for rec in self._records:
            # 매칭 대상 텍스트: description + sector_tags + organization + program + industry
            match_text = " ".join([
                rec.get("description", ""),
                rec.get("sector_tags", ""),
                rec.get("organization", ""),
                rec.get("program", ""),
                rec.get("industry_category", ""),
                rec.get("funding_range", ""),
            ])

            score = _text_match_score(match_text, keywords)

            if score > 0.10:  # 최소 threshold
                results.append(ReferenceResult(
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
                    match_score=score,
                ))

        results.sort(key=lambda r: r.match_score, reverse=True)
        return results[:top_n]

    def to_raw_opportunities(
        self, results: list[ReferenceResult]
    ) -> list[dict[str, Any]]:
        """ReferenceResult → raw_opportunity dict 변환.

        FundingPipeline._ingest_raw_opportunity()와 호환되는 형식.
        """
        raw_opps: list[dict[str, Any]] = []

        for r in results:
            # program_type → category 매핑
            category = _map_program_type(r.program_type)

            raw_opps.append({
                "organization": r.organization,
                "program": r.program or f"{r.organization} {category}",
                "category": category,
                "status": "unknown",   # 참조 데이터는 현재 상태 모름
                "apply_url": r.apply_url or r.website,
                "budget": r.max_amount or r.funding_range,
                "source_url": r.website or r.apply_url,
                "source_type": "reference_data",
                "description": r.description,
                "focus_areas": _parse_sector_tags(r.sector_tags),
                "confidence": 0.60,      # 참조 데이터 기본 신뢰도
                "source_tier": 3,        # 집계 수준
                "fact_confidence": 0.60,
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
