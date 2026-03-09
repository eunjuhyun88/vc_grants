"""
Funding Intelligence Agent — Verification Agent.

Source tier 기반 confidence 계산.
Tier 1-2만 verified 가능, Tier 4-5는 pending 유지.
Observation 레코드 생성 → opportunity 업데이트.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from bs4 import BeautifulSoup

from src.agents.base_agent import BaseAgent
from src.core.errors import VerificationError
from src.core.types import (
    AgentResult,
    Observation,
    OpportunityStatus,
    OutputStatus,
    VerificationInput,
    VerificationOutput,
    generate_id,
)

logger = structlog.get_logger()

# ============================================================
# Source Tier → Confidence 매핑 (PRD 기준)
# ============================================================
TIER_CONFIDENCE: dict[int, float] = {
    1: 0.95,  # 공식 사이트
    2: 0.90,  # ecosystem 파트너
    3: 0.70,  # 블로그
    4: 0.50,  # 집계 사이트
    5: 0.40,  # SNS
}

# ============================================================
# Source Tier 판별 규칙
# ============================================================
TIER_1_DOMAINS = [
    "ethereum.org", "solana.org", "near.org", "polygon.technology",
    "arbitrum.foundation", "optimism.io", "a16zcrypto.com",
    "paradigm.xyz", "polychain.capital", "sequoia.com",
    "alliancedao.com", "ycombinator.com", "binance.com",
]

TIER_2_DOMAINS = [
    "mirror.xyz", "medium.com", "blog.chain.link",
    "docs.alchemy.com", "thegraph.com",
]

TIER_4_DOMAINS = [
    "cryptorank.io", "rootdata.com", "coinmarketcap.com",
    "coingecko.com", "defillama.com",
]

TIER_5_DOMAINS = [
    "twitter.com", "x.com", "t.me", "discord.com",
    "reddit.com", "farcaster.xyz",
]


def determine_source_tier(url: str) -> int:
    """URL에서 source tier 판별."""
    from urllib.parse import urlparse

    domain = urlparse(url).netloc.lower().replace("www.", "")

    if any(d in domain for d in TIER_1_DOMAINS):
        return 1
    if any(d in domain for d in TIER_2_DOMAINS):
        return 2
    if any(d in domain for d in TIER_4_DOMAINS):
        return 4
    if any(d in domain for d in TIER_5_DOMAINS):
        return 5
    return 3  # 기본: 블로그 수준


class VerificationAgent(BaseAgent):
    """사실 검증 + confidence 계산 Agent."""

    async def _execute(self, input_data: Any) -> AgentResult:
        if not isinstance(input_data, VerificationInput):
            raise VerificationError(
                message="input_data must be VerificationInput",
                fix="VerificationInput(opportunity_id='...') 형태로 전달",
                context={"received": type(input_data).__name__},
            )

        opp_id = input_data.opportunity_id
        sources = input_data.sources

        self.log.info("verification.start", opportunity_id=opp_id)

        # 기회 조회
        opp = await self.store.get_opportunity(opp_id)
        if opp is None:
            raise VerificationError(
                message=f"Opportunity not found: {opp_id}",
                fix="올바른 opportunity_id를 전달하거나 먼저 기회를 생성",
                context={"opportunity_id": opp_id},
            )

        # apply_url이 있으면 source 목록에 추가
        if opp.apply_url and opp.apply_url not in sources:
            sources = [opp.apply_url] + sources

        # 각 source 검증
        observations: list[dict] = []
        best_tier = 5
        max_confidence = 0.0

        for source_url in sources[:5]:  # 최대 5개 source
            try:
                result = await self._verify_source(source_url, opp_id)
                if result:
                    observations.append(result)
                    if result["source_tier"] < best_tier:
                        best_tier = result["source_tier"]
                    tier_conf = TIER_CONFIDENCE.get(
                        result["source_tier"], 0.40
                    )
                    if tier_conf > max_confidence:
                        max_confidence = tier_conf
            except Exception as e:
                self.log.warning(
                    "verification.source_error",
                    url=source_url,
                    error=str(e),
                )
                continue

        # output_status 결정 (PRD 기준)
        if best_tier <= 2 and max_confidence >= 0.75:
            output_status = OutputStatus.VERIFIED
        else:
            output_status = OutputStatus.PENDING

        # Observation 레코드 저장
        evidence: list[dict] = []
        for obs_data in observations:
            obs = Observation(
                id=generate_id("obs_"),
                opportunity_id=opp_id,
                source_url=obs_data["source_url"],
                source_tier=obs_data["source_tier"],
                observed_data=obs_data.get("observed_data", {}),
                confidence=TIER_CONFIDENCE.get(obs_data["source_tier"], 0.40),
                observed_at=datetime.now(timezone.utc),
            )
            await self.store.create_observation(obs)
            evidence.append({
                "source_url": obs.source_url,
                "source_tier": obs.source_tier,
                "confidence": obs.confidence,
            })

        # source_chain에 검증된 URL 추가
        current_chain = list(opp.source_chain) if opp.source_chain else []
        for obs_data in observations:
            obs_url = obs_data["source_url"]
            if obs_url and obs_url not in current_chain:
                current_chain.append(obs_url)

        # Opportunity 업데이트
        await self.store.update_opportunity(
            opp_id,
            output_status=output_status,
            fact_confidence=max_confidence,
            source_tier=best_tier,
            source_chain=current_chain,
        )

        output = VerificationOutput(
            opportunity_id=opp_id,
            output_status=output_status,
            fact_confidence=max_confidence,
            source_tier=best_tier,
            evidence=evidence,
            verified_at=datetime.now(timezone.utc).isoformat(),
        )

        self.log.info(
            "verification.complete",
            opportunity_id=opp_id,
            output_status=output_status.value,
            confidence=max_confidence,
            tier=best_tier,
        )

        return AgentResult(success=True, data=output.__dict__)

    async def _verify_source(
        self, url: str, opp_id: str
    ) -> dict | None:
        """개별 source URL 검증."""
        tier = determine_source_tier(url)

        # 실제 URL 접근 가능 여부 확인
        is_reachable = await self._check_url_reachable(url)

        if not is_reachable:
            self.log.warning("verification.unreachable", url=url)
            return None

        return {
            "source_url": url,
            "source_tier": tier,
            "reachable": is_reachable,
            "observed_data": {
                "url_verified": True,
                "tier": tier,
            },
        }

    async def _check_url_reachable(self, url: str) -> bool:
        """URL 접근 가능 여부 확인 (HEAD 요청)."""
        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers={"User-Agent": "FundingBot/1.0"},
            ) as client:
                resp = await client.head(url)
                return resp.status_code < 400
        except Exception:
            # HEAD 실패 시 GET 시도
            try:
                async with httpx.AsyncClient(
                    timeout=10.0,
                    follow_redirects=True,
                    headers={"User-Agent": "FundingBot/1.0"},
                ) as client:
                    resp = await client.get(url)
                    return resp.status_code < 400
            except Exception:
                return False
