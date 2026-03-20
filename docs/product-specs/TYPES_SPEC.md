# TYPES_SPEC — src/core/types.py

이 파일의 모든 타입은 프로젝트 전체에서 공유된다. 다른 모듈에서 별도 타입 정의 금지.

---

## Enums

```python
from enum import StrEnum

class OrgType(StrEnum):
    VC = "vc"
    ECOSYSTEM = "ecosystem"
    FOUNDATION = "foundation"
    ACCELERATOR = "accelerator"

class ProgramCategory(StrEnum):
    """PRD 기준 4가지 카테고리."""
    GRANT = "grant"                        # Grants ($10k-$200k, rolling, milestone based)
    ACCELERATOR = "accelerator"            # Accelerators (8-12 week cohort, demo day)
    VC_COHORT = "vc_cohort"                # VC Cohorts (seed investment, $200k-$1M)
    ECOSYSTEM_BUILDER = "ecosystem_builder" # Ecosystem Builder Programs (grant + support)

class OpportunityStatus(StrEnum):
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

class SourceTier(int):
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
```

---

## Core Dataclasses

```python
from dataclasses import dataclass, field
from datetime import datetime

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
    display_name: str | None = None
    category: ProgramCategory
    program_url: str | None = None
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

@dataclass
class Opportunity:
    id: str
    program_id: str                        # NOT NULL — Program 없이 생성 불가
    cycle_key: str | None = None
    status: OpportunityStatus = OpportunityStatus.UNKNOWN
    deadline_at: datetime | None = None    # null = rolling 또는 미확인
    days_left: int | None = None           # 계산값
    budget_amount: float | None = None
    budget_currency: str = "USD"
    budget_note: str | None = None
    apply_url: str | None = None           # null이면 output 제외
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
    source_url: str
    source_tier: int
    observed_data: dict = field(default_factory=dict)
    confidence: float = 0.0
    observed_at: datetime | None = None

@dataclass
class CompanyProfile:
    id: str
    company_name: str
    stage: CompanyStage | None = None
    sector_tags: list[str] = field(default_factory=list)
    projects: list[dict] = field(default_factory=list)  # [{name, priority, tags}]
    description: str | None = None
    telegram_user_id: int | None = None   # Telegram 사용자 연결
    updated_at: datetime | None = None

@dataclass
class FitRecommendation:
    """PRD v1.1 기준 5-factor priority."""
    id: str
    opportunity_id: str
    company_profile_id: str
    project_name: str | None = None
    fit_score: float
    priority_score: float | None = None    # fit*0.35 + urgency*0.25 + actionability*0.20 + value*0.10 + confidence*0.10
    why_fit: str | None = None
    next_action: str | None = None
    urgency_score: float | None = None
    actionability_score: float | None = None
    expected_value: float | None = None
    confidence_score: float | None = None
    confidence: float | None = None        # fact_confidence
    computed_at: datetime | None = None
```

---

## Output DTO (Telegram 전용)

```python
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
    deadline: str | None = None       # "2026-04-01" | "Rolling" | None
    days_left: int | None = None
    budget: str | None = None         # "$50K–$500K" | None

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
```

---

## Agent I/O 타입

```python
@dataclass
class DiscoveryInput:
    query: str
    category: ProgramCategory | None = None
    sources: list[str] = field(default_factory=list)

@dataclass
class DiscoveryOutput:
    raw_opportunities: list[dict]
    source_urls: list[str]
    fetched_at: str

@dataclass
class VerificationInput:
    opportunity_id: str
    sources: list[str] = field(default_factory=list)

@dataclass
class VerificationOutput:
    opportunity_id: str
    output_status: OutputStatus
    fact_confidence: float
    source_tier: int
    evidence: list[dict]
    verified_at: str

@dataclass
class MatchingInput:
    opportunity_id: str
    company_profile_id: str
    persist: bool = False

@dataclass
class MatchingOutput:
    """PRD v1.1 기준 5-factor."""
    opportunity_id: str
    project_name: str | None
    fit_score: float
    priority_score: float      # fit*0.35 + urgency*0.25 + actionability*0.20 + value*0.10 + confidence*0.10
    why_fit: str
    next_action: str
    urgency_score: float
    actionability_score: float
    expected_value: float
    confidence_score: float
```

---

## 유틸리티 함수

```python
import re
import uuid
from urllib.parse import urlparse

def generate_id(prefix: str = "") -> str:
    """UUID 기반 ID 생성. prefix 예: 'org_', 'prg_', 'opp_'"""
    return f"{prefix}{uuid.uuid4().hex[:12]}"

def normalize_org_name(name: str) -> str:
    """조직명 정규화."""
    name = name.lower().strip()
    name = re.sub(r'\s+', ' ', name)
    for suffix in ['foundation', 'labs', 'protocol', 'network', 'dao', 'inc', 'corp', 'co']:
        name = re.sub(rf'\s+{suffix}$', '', name)
    return name

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
```
