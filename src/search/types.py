"""
Agentic RAG Search — 타입 정의.

search 모듈 내부에서만 사용되는 타입.
외부 인터페이스는 src.core.types의 DiscoveryInput/DiscoveryOutput을 그대로 유지.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.types import CompanyProfile


@dataclass
class SearchResult:
    """검색 엔진 1건의 결과."""
    url: str
    title: str = ""
    snippet: str = ""
    score: float = 0.0           # 엔진 제공 점수 (0-1 정규화)
    engine: str = ""             # "tavily" | "serper" | "brave" | "ddg"
    published_date: str | None = None  # ISO date string


@dataclass
class RankedResult:
    """리랭킹 후 결과 (점수 포함)."""
    url: str
    title: str = ""
    snippet: str = ""
    composite_score: float = 0.0  # 종합 점수
    domain_authority: float = 0.0
    engine_agreement: int = 1     # 몇 개 엔진에서 나왔는가
    relevance: float = 0.0
    freshness: float = 0.0
    engines: list[str] = field(default_factory=list)


@dataclass
class FetchedPage:
    """페치된 페이지 콘텐츠."""
    url: str
    content: str = ""            # 마크다운 또는 plain text
    content_length: int = 0
    fetch_method: str = ""       # "jina" | "httpx"
    success: bool = True
    error: str | None = None


@dataclass
class ExtractedOpportunity:
    """LLM으로 추출된 단일 기회 (페이지별)."""
    organization: str = ""
    program: str = ""
    category: str = ""
    status: str = ""
    deadline: str | None = None
    budget: str | None = None
    apply_url: str | None = None
    description: str | None = None
    focus_areas: list[str] = field(default_factory=list)
    source_url: str = ""
    confidence: float = 0.0


@dataclass
class SearchRound:
    """검색 라운드 메타데이터."""
    round_number: int
    queries: list[str] = field(default_factory=list)
    urls_found: int = 0
    urls_fetched: int = 0
    opportunities_extracted: int = 0


@dataclass
class SearchContext:
    """Agentic RAG 루프 전체 상태."""
    original_query: str
    category: str | None = None
    max_rounds: int = 3

    # 라운드별 기록
    rounds: list[SearchRound] = field(default_factory=list)

    # 누적 결과
    all_urls_seen: set[str] = field(default_factory=set)
    all_opportunities: list[ExtractedOpportunity] = field(default_factory=list)
    fetched_pages: list[FetchedPage] = field(default_factory=list)

    # 충분성 평가
    is_sufficient: bool = False
    gap_reasons: list[str] = field(default_factory=list)

    @property
    def current_round(self) -> int:
        return len(self.rounds)

    @property
    def unique_apply_urls(self) -> int:
        """apply_url이 있는 고유 기회 수."""
        return len({
            o.apply_url for o in self.all_opportunities
            if o.apply_url
        })

    @property
    def total_unique_opportunities(self) -> int:
        """고유 기회 수 (org+program 기준 dedup)."""
        seen = set()
        for o in self.all_opportunities:
            key = (o.organization.lower().strip(), o.program.lower().strip())
            seen.add(key)
        return len(seen)


# ============================================================
# Discovery Loop 타입 (autoresearch 패턴)
# ============================================================


@dataclass
class DiscoveryRound:
    """Discovery loop의 단일 라운드 메타데이터."""
    round_number: int
    queries_used: list[str] = field(default_factory=list)
    source_type: str = "web"           # "web" | "mixed"
    raw_found: int = 0                 # 검색에서 반환된 raw 기회 수
    after_dedup: int = 0               # 누적 known set 대비 dedup 후
    new_programs: int = 0              # 이번 라운드에서 새로 발견한 프로그램 수
    elapsed_seconds: float = 0.0
    gap_reasons: list[str] = field(default_factory=list)


@dataclass
class DiscoveryContext:
    """Discovery loop 전체 상태.

    autoresearch의 실험 브랜치 상태에 해당.
    각 라운드의 결과를 누적 추적하고, 중단 조건을 판단한다.
    """
    profile: "CompanyProfile"
    max_rounds: int = 6
    stall_threshold: int = 2           # N회 연속 new_programs=0이면 중단

    # 라운드 기록
    rounds: list[DiscoveryRound] = field(default_factory=list)

    # 누적 결과
    all_raw_opps: list[dict] = field(default_factory=list)
    ingested_opp_ids: list[str] = field(default_factory=list)

    # 발견된 프로그램/조직 추적 (novelty 판별용)
    known_program_keys: set[str] = field(default_factory=set)   # "org::program"
    known_org_names: set[str] = field(default_factory=set)
    known_urls: set[str] = field(default_factory=set)

    # 중단 판단
    consecutive_zero_rounds: int = 0

    @property
    def current_round(self) -> int:
        return len(self.rounds)

    @property
    def should_stop(self) -> bool:
        """autoresearch 중단 조건: max_rounds 도달 OR 연속 stall."""
        if self.current_round >= self.max_rounds:
            return True
        if self.consecutive_zero_rounds >= self.stall_threshold:
            return True
        return False

    @property
    def category_distribution(self) -> dict[str, int]:
        """발견된 기회의 카테고리별 분포."""
        dist: dict[str, int] = {}
        for opp in self.all_raw_opps:
            cat = opp.get("category", "unknown")
            dist[cat] = dist.get(cat, 0) + 1
        return dist

    @property
    def ecosystem_coverage(self) -> set[str]:
        """target_ecosystems 중 결과에 등장한 에코시스템."""
        covered: set[str] = set()
        target = self.profile.target_ecosystems or []
        if not target:
            return covered

        for opp in self.all_raw_opps:
            text = " ".join([
                opp.get("description", "") or "",
                opp.get("organization", "") or "",
                opp.get("program", "") or "",
            ]).lower()
            for eco in target:
                if eco.lower() in text:
                    covered.add(eco.lower())
        return covered
