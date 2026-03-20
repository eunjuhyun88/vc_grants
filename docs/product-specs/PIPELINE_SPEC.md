# PIPELINE_SPEC — src/core/pipeline.py + 오케스트레이션

## Pipeline 개요

```
[Trigger]
  → Discovery Agent (search + fetch + parse)
  → Entity Resolution (dedup — Phase 6, MVP에서는 단순 insert)
  → Verification Agent (fact check + confidence)
  → DB 저장 (entity_store)
  → Matching Agent (fit + priority 계산)
  → fit_recommendations 저장
  → [완료]
```

---

## src/core/pipeline.py

```python
from src.db.entity_store import EntityStore
from src.agents.discovery import DiscoveryAgent
from src.agents.verification import VerificationAgent
from src.agents.matching import MatchingAgent
from src.core.opportunity_ingestor import OpportunityIngestor
from src.core.opportunity_verifier import OpportunityVerifier
from src.core.opportunity_matcher import OpportunityMatcher
from src.core.types import *
from src.core.config import config
from src.core.errors import PipelineError
import structlog

log = structlog.get_logger()

class FundingPipeline:
    def __init__(self, store: EntityStore):
        self.store = store
        self.discovery = DiscoveryAgent(store, config)
        self.verification = VerificationAgent(store, config)
        self.matching = MatchingAgent(store, config)
        self.ingestor = OpportunityIngestor(store)
        self.opportunity_verifier = OpportunityVerifier(store, self.verification)
        self.opportunity_matcher = OpportunityMatcher(store, self.matching)

    async def run_discovery_pipeline(
        self,
        query: str,
        category: ProgramCategory | None = None,
        company_profile_id: str | None = None,
        sources: list[str] | None = None,
        hint_queries: list[str] | None = None,
    ) -> PipelineResult:
        """
        전체 파이프라인 실행.

        단계:
        1. Discovery: 검색 + fetch + parse
        2. Ingest: raw → OpportunityIngestor → Organization + Program + Opportunity 생성
        3. Verification: OpportunityVerifier가 verification source 수집 + agent 실행
        4. Matching: OpportunityMatcher가 matching 실행 + shared rank policy 처리

        에러 처리: 단계별 실패 시 partial result 유지.
        - Discovery 실패 → 빈 결과 반환
        - 개별 opportunity ingest 실패 → 해당 건만 skip
        - Verification 실패 → output_status='pending' 유지
        - Matching 실패 → fit_score 없이 진행

        runtime 확장:
        - `sources`: user-pasted URLs나 reference bootstrap source를 direct fetch path로 주입
        - `hint_queries`: promoted autoresearch reflection이 밀어주는 query variants를 discovery agent에 추가 주입
        """

    async def ingest_raw_opportunity(self, raw: dict) -> str | None:
        """
        raw opportunity → OpportunityIngestor를 통해 DB 저장.

        1. org_name → normalize → organization 조회/생성
        2. program_name → normalize → program 조회/생성
        3. opportunity 생성

        반환: opportunity_id (실패 시 None)

        MVP에서는 Entity Resolution 생략 — 단순 이름 매칭.
        """

    async def _verify_opportunities(self, opp_ids: list[str]) -> dict:
        """
        opportunity 목록 일괄 검증.

        OpportunityVerifier를 통해 source dedup / limit / sync policy를 공통 처리한다.
        실패한 건은 skip (output_status='pending' 유지).
        """

    async def _match_opportunities(
        self, opp_ids: list[str], company_profile_id: str
    ) -> dict:
        """
        opportunity 목록 일괄 fit 계산.

        OpportunityMatcher를 통해 공통 matching execution path를 재사용한다.
        반환: {opp_id: MatchingOutput}
        실패한 건은 skip (fit_score 없음).
        """
```

### PipelineResult

```python
@dataclass
class PipelineResult:
    total_discovered: int = 0
    total_ingested: int = 0
    total_verified: int = 0
    total_matched: int = 0
    errors: list[str] = field(default_factory=list)
    elapsed_ms: int = 0

    @property
    def summary(self) -> str:
        return (
            f"발견: {self.total_discovered} | "
            f"저장: {self.total_ingested} | "
            f"검증: {self.total_verified} | "
            f"매칭: {self.total_matched} | "
            f"에러: {len(self.errors)}"
        )
```

---

## 스케줄러 (Phase 8)

```python
# src/core/scheduler.py

import asyncio
from datetime import datetime, timedelta

class FundingScheduler:
    def __init__(self, pipeline: FundingPipeline, store: EntityStore):
        self.pipeline = pipeline
        self.store = store

    async def run(self):
        """메인 스케줄 루프."""
        while True:
            await self._scheduled_discovery()
            await self._scheduled_verification()
            await self._scheduled_monitoring()
            await asyncio.sleep(3600)  # 1시간 주기

    async def _scheduled_discovery(self):
        """
        주기적 Discovery sweep.
        카테고리별로 기본 검색 쿼리 실행.

        검색 쿼리 목록:
        - "AI infrastructure grants 2026"
        - "blockchain accelerator cohort 2026"
        - "Web3 ecosystem grants open"
        - "decentralized AI funding"
        """

    async def _scheduled_verification(self):
        """
        재검증 스케줄.

        대상 선정 (REVERIFICATION_INTERVALS 기반):
        - deadline ≤ 14일: 마지막 검증 후 6시간 경과
        - status=unknown: 12시간 경과
        - open/rolling: 24시간 경과
        - closed: 72시간 경과
        """

    async def _scheduled_monitoring(self):
        """
        변화 감지 스케줄.
        모든 active opportunity 대상.
        MonitoringAgent 호출.
        """
```

---

## CLI 진입점

```python
# src/core/pipeline.py (하단)

import argparse
import asyncio

async def main():
    parser = argparse.ArgumentParser(description="Funding Pipeline")
    parser.add_argument("--query", type=str, required=True, help="검색 쿼리")
    parser.add_argument("--category", type=str, default=None,
                        choices=["grant", "accelerator", "vc_cohort", "ecosystem_builder"])
    parser.add_argument("--profile", type=str, default=None,
                        help="company_profile_id (fit 계산용)")
    parser.add_argument("--init-db", action="store_true", help="DB 초기화")
    args = parser.parse_args()

    async with EntityStore() as store:
        if args.init_db:
            await store.init_schema()
            log.info("DB initialized")
            return

        pipeline = FundingPipeline(store)
        result = await pipeline.run_discovery_pipeline(
            query=args.query,
            category=args.category,
            company_profile_id=args.profile,
        )
        print(result.summary)

if __name__ == "__main__":
    asyncio.run(main())
```

### 사용 예시

```bash
# DB 초기화
python -m src.core.pipeline --init-db

# Grant 검색
python -m src.core.pipeline --query "AI infrastructure grants" --category grant

# 프로필로 fit 포함 실행
python -m src.core.pipeline --query "decentralized AI funding" --profile cp_hoot

# Accelerator 검색
python -m src.core.pipeline --query "blockchain accelerator 2026" --category accelerator

# Ecosystem Builder 검색
python -m src.core.pipeline --query "Web3 ecosystem builder program" --category ecosystem_builder
```

---

## 에러 복구 정책

| 실패 지점 | 동작 | 데이터 영향 |
|-----------|------|-----------|
| Tavily API 실패 | 빈 결과 반환 | 기존 DB 영향 없음 |
| 개별 URL fetch 실패 | 해당 URL skip | 다른 URL 계속 처리 |
| LLM parse 실패 | 해당 결과 skip | raw 데이터 로깅 |
| DB insert 중복 | dedup 로직 실행 | 기존 데이터 유지 |
| Verification 실패 | pending 유지 | 다음 주기에 재시도 |
| Matching 실패 | fit 없이 진행 | 목록에는 표시 (fit 없이) |
| Telegram 전송 실패 | 재시도 (3회) | 메시지 큐에 보관 |

**원칙:** 파이프라인 전체가 하나의 에러로 중단되면 안 됨. 부분 성공 허용.

---

## 테스트: tests/test_pipeline.py

```python
async def test_full_pipeline_e2e():
    """검색 → ingest → 검증 → 매칭 전체 흐름."""

async def test_pipeline_partial_failure():
    """일부 URL fetch 실패해도 나머지 처리."""

async def test_ingest_creates_org_program_opportunity():
    """ingest가 organization + program + opportunity 3개 테이블 생성."""

async def test_ingest_dedup_same_org():
    """같은 조직을 두 번 ingest하면 하나만 생성."""

async def test_pipeline_no_profile_skips_matching():
    """profile_id 없으면 matching 단계 skip."""

async def test_pipeline_result_summary():
    """PipelineResult.summary 형식 확인."""
```
