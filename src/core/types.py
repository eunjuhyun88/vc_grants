"""
Funding Intelligence Agent — 공유 타입 정의.

이 파일의 모든 타입은 프로젝트 전체에서 공유된다. 다른 모듈에서 별도 타입 정의 금지.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse

# Python 3.11+ has StrEnum; for 3.9/3.10, provide a compatible shim
if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        """StrEnum backport for Python < 3.11."""
        pass


# ============================================================
# Enums
# ============================================================

class OrgType(StrEnum):
    """ENTITY_MODEL.md org_type."""
    VC = "vc"
    ECOSYSTEM = "ecosystem"
    FOUNDATION = "foundation"
    ACCELERATOR = "accelerator"
    ACCELERATOR_OPERATOR = "accelerator_operator"
    HYBRID = "hybrid"


class ProgramCategory(StrEnum):
    """ENTITY_MODEL.md 기준 7가지 program_type."""
    GRANT = "grant"                         # Grants ($10k-$200k, rolling, milestone based)
    ACCELERATOR = "accelerator"             # Accelerators (8-12 week cohort, demo day)
    VC_COHORT = "vc_cohort"                 # VC Cohorts (seed investment, $200k-$1M)
    BUILDER_PROGRAM = "builder_program"     # Builder Programs (grant + support, ecosystem)
    RESIDENCY = "residency"                 # Time-bound residency programs
    FUND = "fund"                           # Generic VC open form / fund
    HACKATHON_PIPELINE = "hackathon_pipeline"  # Hackathon → funding pipeline
    # 하위 호환: 기존 'ecosystem_builder' → 'builder_program'으로 마이그레이션 예정
    ECOSYSTEM_BUILDER = "ecosystem_builder"  # DEPRECATED: builder_program 사용


# ============================================================
# Display Bucket 매핑 (ENTITY_MODEL.md)
# ============================================================

DISPLAY_BUCKET_MAP: dict[str, str] = {
    "grant": "grants",
    "accelerator": "cohorts",
    "vc_cohort": "cohorts",
    "builder_program": "grants",
    "residency": "cohorts",
    "fund": "funds",
    "hackathon_pipeline": "cohorts",
    "ecosystem_builder": "grants",  # deprecated 호환
}

# display_bucket → category 역매핑
BUCKET_TO_CATEGORIES: dict[str, list[str]] = {
    "grants": ["grant", "builder_program", "ecosystem_builder"],
    "cohorts": ["accelerator", "vc_cohort", "residency", "hackathon_pipeline"],
    "funds": ["fund"],
}


class OpportunityStatus(StrEnum):
    """ENTITY_MODEL.md recruiting_status. 'deadline'은 status가 아님 — deadline_at 필드 참조."""
    OPEN = "open"
    ROLLING = "rolling"
    UPCOMING = "upcoming"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class OutputStatus(StrEnum):
    VERIFIED = "verified"
    PENDING = "pending"
    REJECTED = "rejected"


class EndpointType(StrEnum):
    FORM = "form"
    EMAIL = "email"
    TYPEFORM = "typeform"
    AIRTABLE = "airtable"


class SourceTier:
    """1=공식, 2=ecosystem, 3=블로그, 4=집계, 5=SNS"""
    OFFICIAL = 1
    ECOSYSTEM = 2
    BLOG = 3
    AGGREGATOR = 4
    SNS = 5


class CompanyStage(StrEnum):
    IDEA = "idea"
    MVP = "mvp"
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B = "series_b"
    GROWTH = "growth"


class SubmissionStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    REJECTED = "rejected"
    ACCEPTED = "accepted"


class RankingIntent(StrEnum):
    DEFAULT = "default"
    URGENT = "urgent"
    BIGGEST_CHECK = "biggest_check"
    READY_NOW = "ready_now"
    BEST_FIT = "best_fit"


# ============================================================
# Core Dataclasses
# ============================================================

@dataclass
class Organization:
    id: str
    normalized_name: str
    display_name: str | None = None
    domain: str | None = None
    org_type: OrgType | None = None
    sector_tags: list[str] = field(default_factory=list)
    website_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Program:
    id: str
    org_id: str
    normalized_name: str
    category: ProgramCategory
    display_name: str | None = None
    program_url: str | None = None
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Opportunity:
    id: str
    program_id: str                         # NOT NULL — Program 없이 생성 불가
    cycle_key: str | None = None
    status: OpportunityStatus = OpportunityStatus.UNKNOWN
    deadline_at: datetime | None = None     # null = rolling 또는 미확인
    days_left: int | None = None            # 계산값
    budget_amount: float | None = None
    budget_currency: str = "USD"
    budget_note: str | None = None
    apply_url: str | None = None            # null이면 output 제외
    output_status: OutputStatus = OutputStatus.PENDING
    fact_confidence: float = 0.0
    source_tier: int | None = None
    evidence_json: list[dict] = field(default_factory=list)
    source_chain: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class ApplicationEndpoint:
    id: str
    opportunity_id: str
    endpoint_type: EndpointType | None = None
    url: str = ""
    is_active: bool = True
    verified_at: datetime | None = None
    created_at: datetime | None = None


@dataclass
class Observation:
    id: str
    opportunity_id: str | None = None
    org_id: str | None = None
    source_url: str = ""
    source_tier: int = 5
    observed_data: dict = field(default_factory=dict)
    confidence: float = 0.0
    observed_at: datetime | None = None


@dataclass
class SocialMonitoringEvent:
    """소셜 탐색 provenance + alert 후보 관리."""
    id: str
    source_url: str
    matched_account: str = ""
    matched_account_type: str = ""
    monitoring_round: str = ""
    organization: str = ""
    program: str = ""
    category: str = ""
    signal_type: str = ""
    apply_url: str | None = None
    source_tier: int = 5
    confidence: float = 0.0
    promoted_opportunity_id: str | None = None
    verification_status: str = "pending"      # pending | verified | rejected
    notified: bool = False
    discovered_at: datetime | None = None
    notified_at: datetime | None = None


@dataclass
class CompanyProfile:
    """ENTITY_MODEL.md CompanyProfile. 매칭 기준 정보."""
    id: str
    company_name: str
    stage: CompanyStage | None = None
    sector_tags: list[str] = field(default_factory=list)
    subsector_tags: list[str] = field(default_factory=list)
    projects: list[dict] = field(default_factory=list)   # [{name, priority, tags}]
    description: str | None = None
    geography: str | None = None                         # 예: "South Korea", "Global"
    funding_goal: str | None = None                      # 예: "$500K-$1M"
    product_summary: str | None = None
    target_ecosystems: list[str] = field(default_factory=list)  # 예: ["ethereum", "solana"]
    telegram_user_id: int | None = None                  # Telegram 사용자 연결
    updated_at: datetime | None = None


@dataclass
class FitRecommendation:
    """PRIORITY_ALGORITHM.md 5-factor priority scoring."""
    id: str
    opportunity_id: str
    company_profile_id: str
    project_name: str | None = None
    fit_score: float = 0.0
    priority_score: float | None = None     # 5-factor 가중 합산
    why_fit: str | None = None
    next_action: str | None = None
    urgency_score: float | None = None
    actionability_score: float | None = None
    expected_value: float | None = None
    confidence: float | None = None
    computed_at: datetime | None = None


# ============================================================
# Output DTO (Telegram 전용)
# ============================================================

@dataclass
class OpportunityCard:
    """Telegram 출력용 DTO. card_renderer가 이것만 받는다."""
    # 필수
    organization: str
    program: str
    category: str
    status: str
    apply_url: str
    confidence: float

    # 선택
    deadline: str | None = None         # "2026-04-01" | "Rolling" | None
    days_left: int | None = None
    budget: str | None = None           # "$50K-$500K" | None
    source_url: str | None = None       # 프로그램 정보 페이지 URL
    description: str | None = None      # 프로그램 한줄 설명

    # fit 데이터 (있을 때만)
    fit_score: float | None = None
    priority_score: float | None = None
    why_fit: str | None = None
    next_action: str | None = None


@dataclass
class DossierCard:
    """조직 dossier 출력용 DTO."""
    org_name: str
    org_type: str
    website: str | None = None
    portfolio_count: int | None = None
    avg_check_size: str | None = None
    focus_areas: list[str] = field(default_factory=list)
    decision_makers: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class DailyBriefData:
    """일일 브리핑 데이터 컨테이너."""
    top_opportunities: list[OpportunityCard] = field(default_factory=list)
    new_today: list[OpportunityCard] = field(default_factory=list)
    deadline_soon: list[OpportunityCard] = field(default_factory=list)
    changes: list[dict] = field(default_factory=list)


# ============================================================
# Agent Result (공통 반환 타입)
# ============================================================

@dataclass
class AgentResult:
    """모든 Agent의 공통 반환 타입."""
    success: bool
    data: dict = field(default_factory=dict)
    error: str | None = None
    elapsed_ms: float = 0.0


# ============================================================
# Agent I/O 타입
# ============================================================

@dataclass
class DiscoveryInput:
    query: str
    category: ProgramCategory | None = None
    sources: list[str] = field(default_factory=list)
    hint_queries: list[str] = field(default_factory=list)


@dataclass
class DiscoveryOutput:
    raw_opportunities: list[dict] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    fetched_at: str = ""


@dataclass
class VerificationInput:
    opportunity_id: str
    sources: list[str] = field(default_factory=list)


@dataclass
class VerificationOutput:
    opportunity_id: str
    output_status: OutputStatus = OutputStatus.PENDING
    fact_confidence: float = 0.0
    source_tier: int = 5
    evidence: list[dict] = field(default_factory=list)
    verified_at: str = ""


@dataclass
class MatchingInput:
    opportunity_id: str
    company_profile_id: str
    persist: bool = False


@dataclass
class MatchingOutput:
    """PRIORITY_ALGORITHM.md 5-factor."""
    opportunity_id: str
    project_name: str | None = None
    fit_score: float = 0.0
    priority_score: float = 0.0     # 5-factor weighted sum
    why_fit: str = ""
    next_action: str = ""
    urgency_score: float = 0.0
    actionability_score: float = 0.0
    expected_value: float = 0.0
    confidence: float = 0.0


# ============================================================
# 유틸리티 함수
# ============================================================

def generate_id(prefix: str = "") -> str:
    """UUID 기반 ID 생성. prefix 예: 'org_', 'prg_', 'opp_'"""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def normalize_org_name(name: str) -> str:
    """조직명 정규화. 관사 제거, 접미사 제거, 공백 정규화."""
    name = name.lower().strip()
    name = re.sub(r'\s+', ' ', name)
    # 관사 제거 ("The Ethereum Foundation" → "ethereum foundation")
    name = re.sub(r'^(the|a|an)\s+', '', name)
    # 접미사 제거
    for suffix in ['foundation', 'labs', 'protocol', 'network', 'dao', 'inc', 'corp', 'co', 'ltd']:
        name = re.sub(rf'\s+{suffix}$', '', name)
    return name.strip()


def extract_domain(url: str) -> str | None:
    """URL에서 도메인 추출 (www. 제거). dedup용."""
    if not url:
        return None
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")
        return domain if domain else None
    except Exception:
        return None


def normalize_url(url: str) -> str:
    """URL 정규화 — dedup용."""
    parsed = urlparse(url)
    scheme = 'https'
    path = parsed.path.rstrip('/')
    return f"{scheme}://{parsed.netloc}{path}"


def calculate_days_left(deadline_at: datetime | None) -> int | None:
    """마감까지 남은 일수 계산."""
    if deadline_at is None:
        return None
    delta = deadline_at - datetime.now()
    return max(0, delta.days)


def serialize_json_field(value: list | dict | None) -> str | None:
    """list/dict → JSON string (DB 저장용)."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def deserialize_json_field(value: str | None) -> list | dict | None:
    """JSON string → list/dict (DB 읽기용)."""
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None
