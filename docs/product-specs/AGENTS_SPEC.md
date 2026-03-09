# AGENTS_SPEC — src/agents/

## BaseAgent (추상 클래스)

모든 agent는 이 클래스를 상속한다.

```python
# src/agents/base_agent.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import structlog

log = structlog.get_logger()

@dataclass
class AgentResult:
    success: bool
    data: dict | None = None
    error: str | None = None
    elapsed_ms: int = 0

class BaseAgent(ABC):
    """모든 agent의 기반 클래스."""

    name: str = "base"

    def __init__(self, store: EntityStore, config: Config):
        self.store = store
        self.config = config
        self.log = log.bind(agent=self.name)

    async def run(self, input_data: dict) -> AgentResult:
        """
        실행 진입점. 로깅 + 에러 핸들링 포함.
        하위 클래스는 _execute()만 구현.
        """
        start = datetime.now()
        self.log.info("agent.start", input_keys=list(input_data.keys()))
        try:
            result = await self._execute(input_data)
            elapsed = int((datetime.now() - start).total_seconds() * 1000)
            self.log.info("agent.complete", elapsed_ms=elapsed)
            return AgentResult(success=True, data=result, elapsed_ms=elapsed)
        except Exception as e:
            elapsed = int((datetime.now() - start).total_seconds() * 1000)
            self.log.error("agent.fail", error=str(e), elapsed_ms=elapsed)
            return AgentResult(success=False, error=str(e), elapsed_ms=elapsed)

    @abstractmethod
    async def _execute(self, input_data: dict) -> dict:
        """하위 클래스가 구현하는 실제 로직."""
        ...
```

---

## Agent 1: Discovery Agent (Phase 2)

**파일:** `src/agents/discovery.py`
**역할:** 웹에서 펀딩 기회를 검색 + fetch + parse하여 raw 데이터 반환

```python
# src/agents/discovery.py

from src.agents.base_agent import BaseAgent, AgentResult
from src.core.types import DiscoveryInput, DiscoveryOutput, ProgramCategory

class DiscoveryAgent(BaseAgent):
    name = "discovery"

    async def _execute(self, input_data: dict) -> dict:
        """
        1. Tavily API로 검색 쿼리 실행
        2. 결과 URL들을 httpx로 fetch
        3. LLM(Haiku)으로 HTML → structured data 파싱
        4. raw_opportunities 리스트 반환
        """
        inp = DiscoveryInput(**input_data)
        # 구현

    async def _search(self, query: str, category: str | None) -> list[str]:
        """
        Tavily search API 호출.
        반환: 관련 URL 목록 (최대 10개).
        """

    async def _fetch_page(self, url: str) -> str:
        """
        httpx로 페이지 fetch.
        timeout: 15초.
        에러 시 빈 문자열 반환 (skip, 에러 로깅).
        """

    async def _parse_opportunities(
        self, html: str, url: str, category: str | None
    ) -> list[dict]:
        """
        LLM(Haiku)으로 HTML에서 펀딩 기회 추출.

        추출 필드:
        - org_name, program_name, category
        - deadline (없으면 null — 추측 금지)
        - budget_note
        - apply_url
        - description
        - source_url

        프롬프트 제약:
        - "deadline이 명시되지 않은 경우 null을 반환하라"
        - "금액이 명시되지 않은 경우 null을 반환하라"
        - "apply URL이 없으면 빈 문자열 반환"
        """
```

### Discovery Agent LLM 프롬프트 구조

```
SYSTEM: You are a funding opportunity extractor. Given a web page, extract structured data.

RULES:
- Extract ONLY what is explicitly stated on the page
- If deadline is not explicitly mentioned, return null
- If budget/amount is not stated, return null
- Never guess or infer dates from general knowledge
- Return apply_url only if a direct application link exists

OUTPUT FORMAT (JSON array):
[{
  "org_name": str,
  "program_name": str,
  "category": "grant" | "accelerator" | "vc_cohort" | "ecosystem_builder",
  "deadline": str | null,       // ISO format or null
  "budget_note": str | null,    // "$50K-$500K" 등
  "apply_url": str | null,
  "description": str,
  "source_url": str             // 원본 URL
}]
```

---

## Agent 2: Verification Agent (Phase 2)

**파일:** `src/agents/verification.py`
**역할:** 기회의 사실(deadline, status, apply_url)을 검증하고 confidence 산출

```python
# src/agents/verification.py

class VerificationAgent(BaseAgent):
    name = "verification"

    async def _execute(self, input_data: dict) -> dict:
        """
        1. opportunity_id로 DB에서 기회 조회
        2. source_chain의 URL들 재방문
        3. 각 URL에서 facts 재추출
        4. 기존 facts와 비교 → confidence 계산
        5. observation 저장
        6. output_status 판정 (verified / pending / rejected)
        """
        inp = VerificationInput(**input_data)
        # 구현

    async def _verify_facts(
        self, opportunity: Opportunity, sources: list[str]
    ) -> tuple[OutputStatus, float, int]:
        """
        facts 검증 로직.

        반환: (output_status, fact_confidence, best_source_tier)

        규칙:
        - Tier 1-2 소스에서 deadline 확인 → verified 가능
        - Tier 4-5만 있으면 → pending (verified 불가)
        - apply_url 접근 불가 → rejected
        - deadline 검증 불가 시 null 유지 (추측 보간 금지)
        """

    def _calculate_confidence(
        self, observations: list[Observation]
    ) -> float:
        """
        confidence 계산.

        tier별 weight:
        - Tier 1: 0.95
        - Tier 2: 0.90
        - Tier 3: 0.80
        - Tier 4: 0.60
        - Tier 5: 0.40

        복수 소스 교차검증 시 보너스: +0.05 per additional source (max +0.10)
        """

    def _determine_source_tier(self, url: str) -> int:
        """
        URL 기반 source tier 판정.

        Tier 1: 공식 도메인 (ethereum.org, solana.org 등)
        Tier 2: 생태계 포탈 (docs.*, blog.official-domain.*)
        Tier 3: 블로그/뉴스 (medium.com, mirror.xyz, decrypt.co)
        Tier 4: 집계 사이트 (defiinvestor.io, cryptorank.io)
        Tier 5: SNS (twitter.com, t.me)
        """
```

### 재검증 스케줄

```python
REVERIFICATION_INTERVALS = {
    "deadline_soon":  6 * 3600,    # deadline ≤ 14일: 6시간
    "unknown":       12 * 3600,    # status=unknown: 12시간
    "open_rolling":  24 * 3600,    # open/rolling: 24시간
    "closed":        72 * 3600,    # closed: 72시간
}
```

---

## Agent 3: Matching Agent (Phase 3)

**파일:** `src/agents/matching.py`
**역할:** 사용자 프로필과 기회 간 fit_score + priority_score 계산

```python
# src/agents/matching.py

class MatchingAgent(BaseAgent):
    name = "matching"

    async def _execute(self, input_data: dict) -> dict:
        """
        PRD 기준 4-factor priority.

        1. opportunity 조회
        2. company_profile 조회
        3. fit_score 계산 (sector match + stage match + ecosystem relevance)
        4. urgency_score 계산 (deadline 기반)
        5. expected_value 계산 (funding amount 기반)
        6. confidence = fact_confidence
        7. priority_score = fit*0.35 + urgency*0.35 + value*0.15 + confidence*0.15
        8. persist=True면 fit_recommendations에 저장
        """
        inp = MatchingInput(**input_data)
        # 구현

    def _calculate_fit_score(
        self, profile: CompanyProfile, opportunity: Opportunity, program: Program, org: Organization
    ) -> float:
        """
        fit_score 계산 (0.0 ~ 1.0).

        로직:
        1. sector_tags overlap 수 → base_score
           - 0 overlap: 0.2
           - 1 overlap: 0.5
           - 2 overlap: 0.7
           - 3+ overlap: 0.85
        2. stage 호환성 보너스
           - 프로필 stage가 프로그램 요구 stage 이하: +0.1
           - 불일치: -0.2
        3. 최종 clamp: 0.0 ~ 1.0
        """

    def _calculate_urgency_score(self, deadline_at: datetime | None, status: str) -> float:
        """
        urgency_score 계산 (PRD 기준).

        days_left 기반:
        - D0-3: 1.0
        - D4-7: 0.8
        - D8-14: 0.6
        - D15-30: 0.4
        - rolling: 0.3
        - unknown: 0.1
        - closed: 0.0
        """

    def _calculate_expected_value(self, opportunity: Opportunity) -> float:
        """
        expected_value 계산.

        budget_amount 기반:
        - $500K+: 1.0
        - $200K-$500K: 0.8
        - $50K-$200K: 0.6
        - $10K-$50K: 0.4
        - <$10K: 0.2
        - 미공개: 0.3
        """

    def _calculate_priority_score(
        self, fit: float, urgency: float, value: float, confidence: float,
        intent: str = "default"
    ) -> float:
        """
        priority_score = 4-factor 가중 합산 (PRD 기준).

        WEIGHTS[intent]:
        - default: fit*0.35 + urgency*0.35 + value*0.15 + confidence*0.15
        - urgent: fit*0.15 + urgency*0.55 + value*0.15 + confidence*0.15
        - highest_money: fit*0.20 + urgency*0.15 + value*0.50 + confidence*0.15
        - best_ecosystem_match: fit*0.55 + urgency*0.20 + value*0.10 + confidence*0.15
        """

    async def batch_rank(
        self,
        company_profile_id: str,
        category: ProgramCategory | None = None,
        top_n: int = 10,
        intent: str = "default"
    ) -> list[MatchingOutput]:
        """
        전체 eligible opportunity 대상 priority_score 계산 후 상위 N개 반환.

        1. list_opportunities_curated() 호출
        2. 각 기회에 대해 fit/urgency/value/confidence 계산
        3. intent별 가중치로 priority_score 산출
        4. 정렬 후 top_n 반환
        """
```

### Priority Weights 상수 (PRD 기준)

```python
PRIORITY_WEIGHTS = {
    "default":              {"fit": 0.35, "urgency": 0.35, "value": 0.15, "confidence": 0.15},
    "urgent":               {"fit": 0.15, "urgency": 0.55, "value": 0.15, "confidence": 0.15},
    "highest_money":        {"fit": 0.20, "urgency": 0.15, "value": 0.50, "confidence": 0.15},
    "best_ecosystem_match": {"fit": 0.55, "urgency": 0.20, "value": 0.10, "confidence": 0.15},
}
```

---

## Agent 4: Research Agent (Phase 7)

**파일:** `src/agents/research.py`

```python
class ResearchAgent(BaseAgent):
    name = "research"

    async def _execute(self, input_data: dict) -> dict:
        """
        1. org_id로 조직 조회
        2. 공식 사이트, Crunchbase 검색
        3. LLM(Sonnet)으로 dossier 생성
        4. organization_dossiers에 저장
        """

    async def _build_dossier(self, org: Organization, raw_data: list[str]) -> dict:
        """
        LLM 기반 dossier 생성.
        PROVIDED_FACTS만 사용. 추측에 confidence < 0.7 마킹.
        """
```

---

## Agent 5: Entity Resolution (Phase 6)

**파일:** `src/agents/entity_resolution.py`

```python
class EntityResolutionAgent(BaseAgent):
    name = "entity_resolution"

    async def _execute(self, input_data: dict) -> dict:
        """
        1. raw_entity 수신
        2. DB에서 기존 entity 검색 (domain → name → alias)
        3. confidence 계산
        4. action 결정: create / merge / review_queue
        """

    def _match_organization(self, raw: dict) -> tuple[str, str, float]:
        """
        조직 매칭. 반환: (action, matched_id, confidence)

        1단계: domain 일치 → confidence 1.0 → merge
        2단계: normalized_name 일치 → confidence 0.90 → merge
        3단계: alias 매칭 → confidence 계산
        confidence ≥ 0.85 → auto merge
        confidence < 0.85 → review_queue
        """
```

---

## Agent 6: Monitoring Agent (Phase 8)

**파일:** `src/agents/monitoring.py`

```python
class MonitoringAgent(BaseAgent):
    name = "monitoring"

    async def _execute(self, input_data: dict) -> dict:
        """
        1. 대상 opportunity 목록 조회
        2. 각 기회의 소스 URL 재방문
        3. 기존 facts와 비교
        4. 변화 감지 시 change_events 저장
        5. 기존 opportunity UPDATE (새 row 생성 금지)
        """

    async def _detect_changes(
        self, opportunity: Opportunity, fresh_data: dict
    ) -> list[dict]:
        """
        변화 감지. 반환: change_event 목록.

        감지 대상:
        - deadline 변경
        - status 변경 (open→closed 등)
        - budget 변경
        - apply_url 변경/비활성화
        """
```

---

## Agent 7: Briefing Agent (Phase 9)

**파일:** `src/agents/briefing.py`

```python
class BriefingAgent(BaseAgent):
    name = "briefing"

    async def _execute(self, input_data: dict) -> dict:
        """
        LLM 호출 없음. DB 직접 조회 후 card_renderer 통과.

        1. priority 상위 5개 기회 조회
        2. 오늘 추가된 기회 조회
        3. D-7 이내 마감 기회 조회
        4. 오늘 change_events 조회
        5. DailyBriefData 구성 → 반환
        """
```

---

## 테스트: tests/test_agents.py

```python
# Discovery
async def test_discovery_returns_raw_opportunities():
    """검색 결과가 raw_opportunities 리스트로 반환."""

async def test_discovery_null_deadline_when_not_found():
    """deadline이 페이지에 없으면 null 반환 (추측 금지)."""

# Verification
async def test_verification_tier12_can_verify():
    """Tier 1-2 소스만 verified 가능."""

async def test_verification_tier45_stays_pending():
    """Tier 4-5만 있으면 pending 유지."""

async def test_verification_no_deadline_guess():
    """deadline 검증 불가 시 null 유지."""

# Matching
async def test_matching_fit_score_sector_overlap():
    """sector_tags overlap 수에 따라 fit_score 변동."""

async def test_matching_urgency_d3():
    """D0-3 → urgency 1.0."""

async def test_matching_priority_formula():
    """priority_score = 가중 합산 정확성."""

async def test_batch_rank_returns_top_n():
    """batch_rank가 상위 N개만 반환."""

async def test_matching_different_profiles_different_scores():
    """다른 프로필은 같은 기회에 다른 fit_score."""
```
