"""
Funding Intelligence Agent — Verification Agent.

Source tier 기반 confidence 계산.
Tier 1-2만 verified 가능, Tier 4-5는 pending 유지.
Observation 레코드 생성 → opportunity 업데이트.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

from src.agents.base_agent import BaseAgent
from src.core.errors import VerificationError
from src.core.types import (
    AgentResult,
    ApplicationEndpoint,
    EndpointType,
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
    "arbitrum.foundation", "optimism.io", "a16zcrypto.com", "a16z.com",
    "paradigm.xyz", "polychain.capital", "sequoia.com",
    "alliancedao.com", "alliance.xyz", "ycombinator.com", "binance.com",
    "labs.binance.com", "outlierventures.io", "chain.link",
    "esp.ethereum.foundation", "build.avax.network", "avax.network",
    "nitroacc.xyz",
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

STATUS_RANK = {
    OpportunityStatus.OPEN: 4,
    OpportunityStatus.ROLLING: 3,
    OpportunityStatus.UPCOMING: 2,
    OpportunityStatus.UNKNOWN: 1,
    OpportunityStatus.CLOSED: 0,
}


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

        program = await self.store.get_program(opp.program_id)
        org = await self.store.get_organization(program.org_id) if program else None
        expected_terms = [
            opp.apply_url or "",
            program.display_name if program else "",
            program.normalized_name if program else "",
            org.display_name if org else "",
            org.normalized_name if org else "",
        ]

        # 각 source 검증
        observations: list[dict] = []
        best_tier = 5
        max_confidence = 0.0
        merged_status = opp.status
        has_actionable_support = False
        has_program_context_support = False
        has_closed_support = False

        for source_url in sources[:5]:  # 최대 5개 source
            try:
                result = await self._verify_source(source_url, opp_id, expected_terms)
                if result:
                    observations.append(result)
                    observed_status = result.get("observed_data", {}).get("status")
                    if observed_status:
                        merged_status = _merge_status(
                            merged_status,
                            OpportunityStatus(observed_status),
                        )
                    if result["source_tier"] < best_tier:
                        best_tier = result["source_tier"]
                    tier_conf = float(
                        result.get("confidence")
                        or TIER_CONFIDENCE.get(result["source_tier"], 0.40)
                    )
                    if tier_conf > max_confidence:
                        max_confidence = tier_conf
                    actionable_status = observed_status in {
                        OpportunityStatus.OPEN.value,
                        OpportunityStatus.ROLLING.value,
                        OpportunityStatus.UPCOMING.value,
                    }
                    if (
                        actionable_status
                        and result.get("observed_data", {}).get("content_verified")
                        and result.get("observed_data", {}).get("direct_apply_surface")
                        and result.get("observed_data", {}).get("current_window_evidence")
                    ):
                        has_actionable_support = True
                    if (
                        actionable_status
                        and result.get("observed_data", {}).get("content_verified")
                        and result.get("observed_data", {}).get("current_window_evidence")
                        and (
                            result.get("observed_data", {}).get("program_surface")
                            or result.get("observed_data", {}).get("expected_hits", 0) >= 1
                            or not result.get("observed_data", {}).get("external_form_surface")
                        )
                    ):
                        has_program_context_support = True
                    if observed_status == OpportunityStatus.CLOSED.value and tier_conf >= 0.70:
                        has_closed_support = True
            except Exception as e:
                self.log.warning(
                    "verification.source_error",
                    url=source_url,
                    error=str(e),
                )
                continue

        # output_status 결정 (PRD 기준)
        if has_closed_support and not has_actionable_support:
            output_status = OutputStatus.REJECTED
            merged_status = OpportunityStatus.CLOSED
        elif (
            has_actionable_support
            and has_program_context_support
            and best_tier <= 2
            and max_confidence >= 0.75
        ):
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
                confidence=float(
                    obs_data.get("confidence")
                    or TIER_CONFIDENCE.get(obs_data["source_tier"], 0.40)
                ),
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
            status=merged_status,
            output_status=output_status,
            fact_confidence=max_confidence,
            source_tier=best_tier,
            source_chain=current_chain,
        )

        await self._ensure_verified_endpoint(opp_id, opp.apply_url, sources, observations)

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
        self, url: str, opp_id: str, expected_terms: list[str] | None = None
    ) -> dict | None:
        """개별 source URL 검증."""
        tier = determine_source_tier(url)
        page = await self._fetch_page(url)
        if page is None:
            self.log.warning("verification.unreachable", url=url)
            return None

        analysis = _analyze_page_content(
            url=page["final_url"],
            text=page["text"],
            title=page["title"],
            expected_terms=expected_terms or [],
        )
        confidence = _adjust_confidence(
            tier=tier,
            status=analysis["status"],
            content_verified=analysis["content_verified"],
            application_surface=analysis["application_surface"],
            generic_homepage=analysis["generic_homepage"],
            current_window_evidence=analysis["current_window_evidence"],
            direct_apply_surface=analysis["direct_apply_surface"],
        )

        return {
            "source_url": page["final_url"],
            "source_tier": tier,
            "reachable": True,
            "confidence": confidence,
            "observed_data": {
                "url_verified": True,
                "tier": tier,
                "status": analysis["status"],
                "page_title": page["title"],
                "content_verified": analysis["content_verified"],
                "application_surface": analysis["application_surface"],
                "direct_apply_surface": analysis["direct_apply_surface"],
                "program_surface": analysis["program_surface"],
                "generic_homepage": analysis["generic_homepage"],
                "current_window_evidence": analysis["current_window_evidence"],
            },
        }

    async def _fetch_page(self, url: str) -> dict[str, str] | None:
        """verification용으로 페이지 텍스트를 fetch한다."""
        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers={"User-Agent": "FundingBot/1.0"},
            ) as client:
                resp = await client.get(url)
                if resp.status_code >= 400:
                    return None
                html = resp.text
                soup = BeautifulSoup(html, "lxml")
                title = (soup.title.get_text(" ", strip=True) if soup.title else "")[:200]
                return {
                    "final_url": str(resp.url),
                    "title": title,
                    "text": _extract_page_text(html)[:20000],
                }
        except Exception:
            return None

    async def _ensure_verified_endpoint(
        self,
        opp_id: str,
        apply_url: str | None,
        sources: list[str],
        observations: list[dict[str, Any]],
    ) -> None:
        """검증된 제출/공식 URL을 endpoint로 승격한다."""
        candidate_urls: list[str] = []
        if apply_url:
            candidate_urls.append(apply_url)
        for source in sources:
            if source not in candidate_urls:
                candidate_urls.append(source)

        verified_urls = {
            obs["source_url"]
            for obs in observations
            if obs.get("source_url")
            and obs.get("observed_data", {}).get("direct_apply_surface")
            and obs.get("observed_data", {}).get("content_verified")
            and obs.get("observed_data", {}).get("current_window_evidence")
            and obs.get("observed_data", {}).get("status") in {
                OpportunityStatus.OPEN.value,
                OpportunityStatus.ROLLING.value,
                OpportunityStatus.UPCOMING.value,
            }
        }
        await self.store.sync_active_endpoints(opp_id, sorted(verified_urls))
        if not verified_urls:
            return

        active_endpoints = await self.store.get_active_endpoints(opp_id)
        existing_urls = {endpoint.url for endpoint in active_endpoints}

        for url in candidate_urls:
            if not url or url not in verified_urls or url in existing_urls:
                continue
            endpoint = ApplicationEndpoint(
                id=generate_id("ep_"),
                opportunity_id=opp_id,
                endpoint_type=EndpointType.FORM,
                url=url,
                is_active=True,
                verified_at=datetime.now(timezone.utc),
            )
            await self.store.create_endpoint(endpoint)


def _infer_status_from_source(url: str) -> str | None:
    """URL alone only yields very weak status hints.

    Generic funding/build/apply paths are not enough to prove a live intake.
    Only explicit rolling/waitlist style paths may downgrade UNKNOWN.
    """
    url_lower = (url or "").lower()
    if any(token in url_lower for token in ("rolling", "evergreen")):
        return OpportunityStatus.ROLLING.value
    if any(token in url_lower for token in ("waitlist", "coming-soon", "coming_soon")):
        return OpportunityStatus.UPCOMING.value
    return None


def _merge_status(
    existing: OpportunityStatus,
    observed: OpportunityStatus,
) -> OpportunityStatus:
    """unknown을 actionable 상태로 승격하되, 약한 근거로 downgrade하지 않는다."""
    if observed == OpportunityStatus.CLOSED:
        return OpportunityStatus.CLOSED
    if observed == OpportunityStatus.UNKNOWN:
        return existing
    if existing == OpportunityStatus.CLOSED and observed != OpportunityStatus.CLOSED:
        return observed
    if STATUS_RANK[observed] > STATUS_RANK[existing]:
        return observed
    return existing


def _extract_page_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").lower().split())


def _is_generic_homepage(url: str, text: str) -> bool:
    parsed = urlparse(url)
    path = (parsed.path or "").strip("/")
    if path:
        return False

    normalized_text = _normalize_text(text)
    program_tokens = (
        "apply",
        "application",
        "accelerator",
        "cohort",
        "grant program",
        "grants",
        "builder program",
        "residency",
        "funding program",
    )
    if any(token in normalized_text for token in program_tokens):
        return False

    generic_fund_tokens = (
        "portfolio",
        "our team",
        "thesis",
        "we invest",
        "backing founders",
        "companies we back",
    )
    return any(token in normalized_text for token in generic_fund_tokens)


def _is_external_form_surface(url: str) -> bool:
    normalized_url = (url or "").lower()
    external_hosts = (
        "typeform.com",
        "docs.google.com/forms",
        "airtable.com",
        "hsforms.com",
        "hubspot.com",
        "hubspotpagebuilder.com",
    )
    return any(host in normalized_url for host in external_hosts)


def _is_direct_apply_surface(url: str) -> bool:
    normalized_url = (url or "").lower().strip()
    if not normalized_url:
        return False
    parsed = urlparse(normalized_url)
    host = parsed.netloc
    path = parsed.path or ""

    if any(host.endswith(form_host) for form_host in (
        "typeform.com",
        "airtable.com",
        "docs.google.com",
        "hsforms.com",
        "hubspot.com",
        "hubspotpagebuilder.com",
    )):
        return True

    direct_tokens = (
        "/apply",
        "/application",
        "/applications",
        "/register",
        "/signup",
        "/sign-up",
        "/form",
        "/forms/",
        "/to/",
    )
    return any(token in path for token in direct_tokens)


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


def _analyze_page_content(
    *,
    url: str,
    text: str,
    title: str,
    expected_terms: list[str],
) -> dict[str, Any]:
    raw_excerpt = f"{title} {text[:12000]}"
    normalized_text = _normalize_text(raw_excerpt)
    expected_hits = sum(
        1 for term in expected_terms if term and _normalize_text(term) in normalized_text
    )
    external_form_surface = _is_external_form_surface(url)
    direct_apply_surface = _is_direct_apply_surface(url) or external_form_surface
    exact_date = _extract_exact_date(raw_excerpt)
    today = datetime.now().date()
    future_deadline_evidence = exact_date is not None and exact_date.date() >= today
    past_deadline_evidence = exact_date is not None and exact_date.date() < today

    closed_patterns = (
        "no longer accepting responses",
        "applications are closed",
        "application closed",
        "submissions are closed",
        "this form is closed",
        "closed for submissions",
        "deadline has passed",
    )
    rolling_patterns = ("rolling", "rolling basis", "always open", "open year round", "evergreen")
    open_patterns = (
        "apply now",
        "applications open",
        "open applications",
        "submit your application",
        "apply here",
        "accepting applications",
        "application form",
    )
    upcoming_patterns = ("coming soon", "next cohort", "waitlist", "applications open soon", "upcoming")
    program_patterns = (
        "grant program",
        "grants",
        "accelerator",
        "cohort",
        "builder program",
        "residency",
        "funding",
        "support program",
    )

    application_surface = any(token in normalized_text for token in open_patterns)
    if direct_apply_surface:
        application_surface = True

    program_surface = any(token in normalized_text for token in program_patterns) or expected_hits >= 1
    generic_homepage = _is_generic_homepage(url, normalized_text)
    explicit_open_evidence = any(token in normalized_text for token in open_patterns)
    explicit_rolling_evidence = any(token in normalized_text for token in rolling_patterns)
    explicit_upcoming_evidence = any(token in normalized_text for token in upcoming_patterns)
    current_window_evidence = (
        explicit_open_evidence
        or explicit_rolling_evidence
        or explicit_upcoming_evidence
        or future_deadline_evidence
        or (direct_apply_surface and expected_hits >= 1)
    )

    if any(token in normalized_text for token in closed_patterns) or past_deadline_evidence:
        status = OpportunityStatus.CLOSED.value
    elif explicit_rolling_evidence:
        status = OpportunityStatus.ROLLING.value
    elif explicit_upcoming_evidence:
        status = OpportunityStatus.UPCOMING.value
    elif explicit_open_evidence or (direct_apply_surface and expected_hits >= 1):
        status = OpportunityStatus.OPEN.value
    else:
        status = _infer_status_from_source(url) or OpportunityStatus.UNKNOWN.value

    content_verified = not generic_homepage and (
        program_surface
        or (direct_apply_surface and expected_hits >= 1)
        or (application_surface and program_surface)
    )

    return {
        "status": status,
        "application_surface": application_surface,
        "direct_apply_surface": direct_apply_surface,
        "program_surface": program_surface,
        "generic_homepage": generic_homepage,
        "content_verified": content_verified,
        "expected_hits": expected_hits,
        "external_form_surface": external_form_surface,
        "current_window_evidence": current_window_evidence,
    }


def _adjust_confidence(
    *,
    tier: int,
    status: str,
    content_verified: bool,
    application_surface: bool,
    generic_homepage: bool,
    current_window_evidence: bool,
    direct_apply_surface: bool,
) -> float:
    base = TIER_CONFIDENCE.get(tier, 0.40)
    if generic_homepage:
        return min(base, 0.35)
    if status == OpportunityStatus.CLOSED.value:
        return min(0.90, max(base, 0.80))
    if not content_verified:
        return min(base, 0.45)
    if not current_window_evidence:
        return min(base, 0.55)
    if direct_apply_surface and application_surface and status in {
        OpportunityStatus.OPEN.value,
        OpportunityStatus.ROLLING.value,
        OpportunityStatus.UPCOMING.value,
    }:
        return min(0.95, max(base, 0.85))
    return min(0.80, base)
