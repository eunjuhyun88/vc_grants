"""
Funding Intelligence Agent — Matching Agent.

5-factor priority: fit*0.35 + urgency*0.25 + actionability*0.20 + expected_value*0.10 + confidence*0.10
LLM 없이 순수 계산 (deterministic).
PRIORITY_ALGORITHM.md canonical contract 구현.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import structlog

from src.agents.base_agent import BaseAgent
from src.core.errors import MatchingError
from src.core.profile_identity import GENERIC_NAME_STOPWORDS
from src.core.types import (
    AgentResult,
    CompanyProfile,
    FitRecommendation,
    MatchingInput,
    MatchingOutput,
    Opportunity,
    OpportunityStatus,
    ProgramCategory,
    RankingIntent,
    calculate_days_left,
    generate_id,
)

logger = structlog.get_logger()

# ============================================================
# Intent별 가중치 프리셋 (PRIORITY_ALGORITHM.md 기준)
# ============================================================
INTENT_WEIGHTS: dict[str, dict[str, float]] = {
    "default": {
        "fit": 0.35, "urgency": 0.25, "actionability": 0.20,
        "expected_value": 0.10, "confidence": 0.10,
    },
    "urgent": {
        "fit": 0.20, "urgency": 0.45, "actionability": 0.15,
        "expected_value": 0.10, "confidence": 0.10,
    },
    "biggest_check": {
        "fit": 0.20, "urgency": 0.10, "actionability": 0.15,
        "expected_value": 0.45, "confidence": 0.10,
    },
    "ready_now": {
        "fit": 0.25, "urgency": 0.15, "actionability": 0.35,
        "expected_value": 0.10, "confidence": 0.15,
    },
    "best_fit": {
        "fit": 0.50, "urgency": 0.15, "actionability": 0.15,
        "expected_value": 0.10, "confidence": 0.10,
    },
}

# ============================================================
# Strategic Value 기본값 (카테고리별)
# ============================================================
STRATEGIC_VALUE_BY_CATEGORY: dict[str, float] = {
    "grant": 0.5,
    "accelerator": 0.7,
    "vc_cohort": 0.8,
    "builder_program": 0.6,
    "residency": 0.6,
    "fund": 0.9,
    "hackathon_pipeline": 0.4,
    "ecosystem_builder": 0.6,
}

CATEGORY_REASON_LABEL: dict[str, str] = {
    "grant": "grant",
    "accelerator": "accelerator",
    "vc_cohort": "vc cohort",
    "builder_program": "builder program",
    "residency": "residency",
    "fund": "fund",
    "hackathon_pipeline": "pipeline",
    "ecosystem_builder": "builder program",
}

# ============================================================
# Urgency Score 테이블 (PRIORITY_ALGORITHM.md 기준)
# ============================================================
# D0-3: 1.0, D4-7: 0.85, D8-14: 0.70, D15-30: 0.50
# rolling: 0.35, upcoming: 0.25, unknown: 0.10, closed: 0.00

TAG_SYNONYMS: dict[str, list[str]] = {
    "ai_infra": ["ai infrastructure", "ai infra", "ml infrastructure", "ai tooling"],
    "decentralized_ai": ["decentralized ai", "distributed ai", "ai network"],
    "crypto_infra": ["crypto infrastructure", "blockchain infrastructure", "protocol infrastructure", "onchain infrastructure"],
    "distributed_compute": ["distributed compute", "gpu network", "compute network", "decentralized compute"],
    "personal_model_training": ["model training", "ai model training", "fine tuning", "small model training"],
    "agent_infra": ["agent infrastructure", "agent framework", "ai agent infrastructure"],
    "small_model_training": ["small language model", "small model", "slm", "model training"],
    "torrent_coordination": ["peer to peer", "p2p coordination", "distributed coordination"],
    "blockchain_compute": ["blockchain compute", "onchain compute", "verifiable compute"],
    "crypto_analytics": ["crypto analytics", "blockchain analytics", "onchain analytics"],
    "trading_infra": ["trading infrastructure", "trading analytics", "market infrastructure"],
    "ai_evaluation": ["ai evaluation", "model evaluation", "evaluation infrastructure"],
    "ai_benchmark": ["ai benchmark", "benchmarking infrastructure", "model evaluation"],
    "desci": ["desci", "decentralized science", "science"],
    "physical_ai": ["physical ai", "robotics", "embodied ai"],
}

ECOSYSTEM_SYNONYMS: dict[str, list[str]] = {
    "ethereum": ["ethereum", "esp", "ef"],
    "solana": ["solana"],
    "near": ["near"],
    "arbitrum": ["arbitrum"],
    "monad": ["monad", "nitro accelerator", "nitro"],
    "bittensor": ["bittensor", "subnet"],
    "chainlink": ["chainlink", "build"],
    "avalanche": ["avalanche", "avax", "infrabuidl"],
    "polygon": ["polygon"],
    "base": ["base"],
}

GENERIC_REASON_TERMS = {
    "ai", "crypto", "web3", "blockchain", "compute", "model", "training",
    "grant", "funding", "accelerator", "program", "protocol",
}


def calculate_urgency_score(
    days_left: int | None,
    status: OpportunityStatus,
) -> float:
    """마감일 기반 urgency score 계산."""
    if status == OpportunityStatus.CLOSED:
        return 0.0
    if status == OpportunityStatus.ROLLING:
        return 0.35
    if status == OpportunityStatus.UPCOMING:
        return 0.25

    if days_left is None:
        return 0.1  # unknown

    if days_left <= 3:
        return 1.0
    if days_left <= 7:
        return 0.85
    if days_left <= 14:
        return 0.70
    if days_left <= 30:
        return 0.50
    return 0.2  # 30일 초과


def _normalize_blob(value: str | None) -> str:
    return " ".join((value or "").lower().split())


def _split_tag(tag: str) -> list[str]:
    parts = [part.strip() for part in tag.replace("-", "_").split("_") if part.strip()]
    joined = " ".join(parts)
    return [joined, *parts] if joined else parts


def _expand_terms(values: list[str], synonym_map: dict[str, list[str]] | None = None) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    synonym_map = synonym_map or {}

    for value in values:
        if not value:
            continue
        normalized = value.lower().strip()
        variants = [normalized]
        variants.extend(_split_tag(normalized))
        variants.extend(synonym_map.get(normalized, []))

        for variant in variants:
            variant_norm = _normalize_blob(variant)
            if not variant_norm or variant_norm in seen:
                continue
            seen.add(variant_norm)
            terms.append(variant_norm)

    return terms


def _extract_summary_terms(summary: str | None) -> list[str]:
    if not summary:
        return []

    phrases = [
        "distributed compute",
        "blockchain coordination",
        "model training",
        "personal data",
        "small model",
        "ai infrastructure",
        "decentralized ai",
        "agent infrastructure",
    ]
    text = _normalize_blob(summary)
    matched_phrases = [phrase for phrase in phrases if phrase in text]

    stopwords = {
        "with", "that", "this", "their", "about", "project", "platform",
        "network", "blockchain", "crypto", "web3", "compute", "model",
        "tooling", "infrastructure", "agent", "agents", "training",
    }
    words = [
        token for token in re.split(r"[^a-z0-9]+", text)
        if len(token) >= 4 and token not in stopwords
    ]
    return _expand_terms(matched_phrases + words[:8])


def _term_match_weight(term: str) -> float:
    generic_terms = {
        "ai", "ml", "web3", "crypto", "protocol", "grant", "funding",
        "program", "compute", "blockchain", "tooling", "model",
    }
    normalized = _normalize_blob(term)
    if normalized in generic_terms:
        return 0.15
    if " " in normalized:
        return 0.60
    if len(normalized) >= 10:
        return 0.45
    return 0.30


def _phrase_match_score(text: str, terms: list[str], neutral_if_empty: float = 0.0) -> tuple[float, list[str]]:
    if not terms:
        return neutral_if_empty, []

    normalized_text = f" {_normalize_blob(text)} "
    matched_terms: list[str] = []

    for term in terms:
        if f" {term} " in normalized_text or term in normalized_text:
            matched_terms.append(term)

    if not matched_terms:
        return 0.0, []

    score = min(1.0, sum(_term_match_weight(term) for term in matched_terms) / 1.8)
    return score, matched_terms


def _funding_fit_score(program_category: str | None, funding_goal: str | None) -> float:
    goal = _normalize_blob(funding_goal)
    if not goal or not program_category:
        return 0.7

    category = (program_category or "").lower()
    wants_grant = "grant" in goal
    wants_accelerator = "accelerator" in goal or "cohort" in goal
    wants_seed_vc = "seed_vc" in goal or "seed vc" in goal or "vc" in goal

    if category == "grant":
        return 1.0 if wants_grant else 0.55
    if category in {"accelerator", "vc_cohort", "residency", "hackathon_pipeline"}:
        return 1.0 if wants_accelerator else 0.65
    if category == "fund":
        return 0.95 if wants_seed_vc else 0.55
    if category in {"builder_program", "ecosystem_builder"}:
        return 0.85 if wants_grant or wants_accelerator else 0.6
    return 0.7


def _geo_fit_score(geography: str | None, opportunity_text: str) -> float:
    geo = _normalize_blob(geography)
    text = _normalize_blob(opportunity_text)
    if not geo or geo == "global":
        return 1.0
    if "global" in text or "remote" in text or "worldwide" in text:
        return 1.0
    if geo in text:
        return 1.0
    if any(region in text for region in ("us only", "europe only", "eu only")):
        return 0.4
    return 0.7


def calculate_fit_assessment(
    opp_tags: list[str],
    profile_tags: list[str],
    project_tags: list[str],
    *,
    opportunity_text: str = "",
    target_ecosystems: list[str] | None = None,
    subsector_tags: list[str] | None = None,
    product_summary: str | None = None,
    stage_match: bool = True,
    program_category: str | None = None,
    funding_goal: str | None = None,
    geography: str | None = None,
) -> tuple[float, list[str]]:
    """프로필/프로그램/기회 컨텍스트를 함께 보는 fit assessment."""
    if not profile_tags and not project_tags:
        return 0.0, []

    combined_text = " ".join([
        opportunity_text,
        " ".join(opp_tags),
    ])

    sector_terms = _expand_terms(profile_tags, TAG_SYNONYMS)
    project_terms = _expand_terms(project_tags + list(subsector_tags or []), TAG_SYNONYMS)
    thesis_terms = _expand_terms(project_tags + list(subsector_tags or []), TAG_SYNONYMS)
    thesis_terms.extend(term for term in _extract_summary_terms(product_summary) if term not in thesis_terms)
    ecosystem_terms = _expand_terms(list(target_ecosystems or []), ECOSYSTEM_SYNONYMS)

    sector_fit, matched_sector = _phrase_match_score(combined_text, sector_terms, neutral_if_empty=0.1)
    thesis_fit, matched_thesis = _phrase_match_score(combined_text, thesis_terms, neutral_if_empty=0.1)
    ecosystem_fit, matched_ecosystems = _phrase_match_score(combined_text, ecosystem_terms, neutral_if_empty=0.6 if not ecosystem_terms else 0.0)
    stage_fit = 1.0 if stage_match else 0.4
    funding_fit = _funding_fit_score(program_category, funding_goal)
    geo_fit = _geo_fit_score(geography, combined_text)

    fit = (
        sector_fit * 0.35
        + stage_fit * 0.20
        + thesis_fit * 0.20
        + ecosystem_fit * 0.15
        + funding_fit * 0.05
        + geo_fit * 0.05
    )

    matched_terms = _expand_terms(
        matched_sector[:4] + matched_thesis[:4] + matched_ecosystems[:3] + project_terms[:2]
    )
    return round(min(1.0, max(0.0, fit)), 4), matched_terms[:8]


def calculate_fit_score(
    opp_tags: list[str],
    profile_tags: list[str],
    project_tags: list[str],
) -> float:
    """기존 단순 태그 overlap fit score.

    외부 호출과 테스트는 이 간단한 semantics를 유지하고,
    실제 매칭 경로는 calculate_fit_assessment()를 사용한다.
    """
    if not profile_tags and not project_tags:
        return 0.0

    all_user_tags = set(t.lower() for t in profile_tags)
    all_user_tags.update(t.lower() for t in project_tags)
    opp_tag_set = set(t.lower() for t in opp_tags)

    if not opp_tag_set or not all_user_tags:
        return 0.05

    intersection = opp_tag_set & all_user_tags
    union = opp_tag_set | all_user_tags
    overlap = len(intersection) / len(union) if union else 0.0
    return min(1.0, max(0.0, overlap * 2))


def calculate_actionability_score(
    has_apply_url: bool,
    has_verified_endpoint: bool,
    status: OpportunityStatus,
    stage_match: bool,
) -> float:
    """지금 실제로 지원 가능한지 판단하는 actionability score.

    PRIORITY_ALGORITHM.md 스펙:
    endpoint_readiness*0.35 + status_readiness*0.25
    + requirement_fit*0.20 + material_readiness*0.20
    """
    # endpoint_readiness
    if has_verified_endpoint:
        endpoint = 1.0
    elif has_apply_url:
        endpoint = 0.6
    else:
        endpoint = 0.1

    # status_readiness
    status_map = {
        "open": 1.0, "rolling": 0.8, "upcoming": 0.4,
        "unknown": 0.2, "closed": 0.0,
    }
    status_r = status_map.get(status.value, 0.2)

    # requirement_fit (V1: stage 기반 간소 판단)
    req_fit = 0.8 if stage_match else 0.3

    # material_readiness (V1: stage 기반 추정)
    material = 0.7 if stage_match else 0.4

    return endpoint * 0.35 + status_r * 0.25 + req_fit * 0.20 + material * 0.20


def calculate_money_value(budget_amount: float | None) -> float:
    """펀딩 금액 기반 money value 계산. PRIORITY_ALGORITHM.md 테이블."""
    if budget_amount is None:
        return 0.3  # undisclosed

    if budget_amount >= 500000:
        return 1.0
    if budget_amount >= 200000:
        return 0.8
    if budget_amount >= 50000:
        return 0.6
    if budget_amount >= 10000:
        return 0.4
    return 0.2


def calculate_expected_value(
    budget_amount: float | None,
    category: str | None = None,
) -> float:
    """듀얼 expected value = money_value*0.60 + strategic_value*0.40.

    PRIORITY_ALGORITHM.md 스펙.
    """
    money = calculate_money_value(budget_amount)
    strategic = STRATEGIC_VALUE_BY_CATEGORY.get(category or "", 0.5)
    return money * 0.60 + strategic * 0.40


def calculate_confidence_score(
    source_tier: int | None,
    evidence_count: int,
    has_contradictions: bool,
    field_completeness: float,
    last_verified_at: datetime | None,
) -> float:
    """evidence quality 종합 confidence score.

    PRIORITY_ALGORITHM.md 스펙:
    source_quality*0.35 + evidence_agreement*0.25
    + field_completeness*0.20 + verification_freshness*0.20
    """
    # source_quality
    tier_scores = {1: 1.0, 2: 0.80, 3: 0.50, 4: 0.25, 5: 0.10}
    sq = tier_scores.get(source_tier or 5, 0.10)

    # evidence_agreement
    ea = min(1.0, evidence_count * 0.3)
    if has_contradictions:
        ea *= 0.5

    # field_completeness (외부에서 0.0-1.0 계산)
    fc = field_completeness

    # verification_freshness
    if last_verified_at:
        now = datetime.now(timezone.utc)
        # last_verified_at이 naive면 UTC로 취급
        if last_verified_at.tzinfo is None:
            from datetime import timezone as tz
            last_verified_at = last_verified_at.replace(tzinfo=tz.utc)
        hours_ago = (now - last_verified_at).total_seconds() / 3600
        if hours_ago <= 24:
            vf = 1.0
        elif hours_ago <= 168:   # 7일
            vf = 0.80
        elif hours_ago <= 720:   # 30일
            vf = 0.50
        else:
            vf = 0.20
    else:
        vf = 0.20

    return sq * 0.35 + ea * 0.25 + fc * 0.20 + vf * 0.20


def _calculate_field_completeness(opp: Opportunity) -> float:
    """핵심 5필드 충족률 계산."""
    fields_present = 0
    total_fields = 5

    if opp.status and opp.status != OpportunityStatus.UNKNOWN:
        fields_present += 1
    if opp.apply_url:
        fields_present += 1
    if opp.deadline_at or opp.status == OpportunityStatus.ROLLING:
        fields_present += 1
    if opp.budget_amount or opp.budget_note:
        fields_present += 1
    # program category는 항상 있으므로 1
    fields_present += 1

    return fields_present / total_fields


def calculate_priority_score(
    fit: float,
    urgency: float,
    actionability: float,
    expected_value: float,
    confidence: float,
    intent: str = "default",
) -> float:
    """5-factor 가중 priority score 계산. PRIORITY_ALGORITHM.md."""
    weights = INTENT_WEIGHTS.get(intent, INTENT_WEIGHTS["default"])
    return (
        fit * weights["fit"]
        + urgency * weights["urgency"]
        + actionability * weights["actionability"]
        + expected_value * weights["expected_value"]
        + confidence * weights["confidence"]
    )


class MatchingAgent(BaseAgent):
    """매칭 + 우선순위 계산 Agent."""

    async def _execute(self, input_data: Any) -> AgentResult:
        if not isinstance(input_data, MatchingInput):
            raise MatchingError(
                message="input_data must be MatchingInput",
                fix="MatchingInput(opportunity_id='...', company_profile_id='...') 전달",
                context={"received": type(input_data).__name__},
            )

        opp_id = input_data.opportunity_id
        profile_id = input_data.company_profile_id
        persist = input_data.persist

        # 데이터 조회
        opp = await self.store.get_opportunity(opp_id)
        if opp is None:
            raise MatchingError(
                message=f"Opportunity not found: {opp_id}",
                fix="올바른 opportunity_id 전달",
                context={"opportunity_id": opp_id},
            )

        profile = await self.store.get_company_profile(profile_id)
        if profile is None:
            raise MatchingError(
                message=f"CompanyProfile not found: {profile_id}",
                fix="올바른 company_profile_id 전달 또는 프로필 먼저 등록",
                context={"company_profile_id": profile_id},
            )

        # Organization + Program 정보 가져오기 (opp → program → org)
        program = await self.store.get_program(opp.program_id)
        org_tags: list[str] = []
        program_category: str | None = None
        opportunity_context_parts: list[str] = []
        if program:
            program_category = program.category.value
            opportunity_context_parts.extend(
                filter(
                    None,
                    [
                        program.display_name,
                        program.normalized_name,
                        program.description,
                        program.program_url,
                    ],
                )
            )
            org = await self.store.get_organization(program.org_id)
            if org:
                org_tags = org.sector_tags
                opportunity_context_parts.extend(
                    filter(
                        None,
                        [
                            org.display_name,
                            org.normalized_name,
                            org.domain,
                            org.website_url,
                            " ".join(org.sector_tags),
                        ],
                    )
                )
        opportunity_context_parts.extend(filter(None, [opp.apply_url, opp.budget_note]))
        opportunity_context_parts.extend(opp.source_chain or [])
        opportunity_context_text = " ".join(opportunity_context_parts)

        # 최적 프로젝트 매칭
        best_project, project_tags = self._find_best_project(
            profile, org_tags
        )

        # days_left 계산
        days_left = opp.days_left
        if days_left is None and opp.deadline_at:
            days_left = calculate_days_left(opp.deadline_at)

        # endpoint 정보 조회
        endpoints = await self.store.get_active_endpoints(opp_id)
        has_verified_endpoint = len(endpoints) > 0

        # stage 매칭 여부 (V1 간소: 프로필 stage 기반)
        stage_match = self._check_stage_match(profile, program_category)

        # 5-factor 계산
        fit, matched_terms = calculate_fit_assessment(
            org_tags,
            profile.sector_tags,
            project_tags,
            opportunity_text=opportunity_context_text,
            target_ecosystems=profile.target_ecosystems,
            subsector_tags=profile.subsector_tags,
            product_summary=profile.product_summary,
            stage_match=stage_match,
            program_category=program_category,
            funding_goal=profile.funding_goal,
            geography=profile.geography,
        )
        urgency = calculate_urgency_score(days_left, opp.status)
        actionability = calculate_actionability_score(
            has_apply_url=bool(opp.apply_url),
            has_verified_endpoint=has_verified_endpoint,
            status=opp.status,
            stage_match=stage_match,
        )
        value = calculate_expected_value(opp.budget_amount, program_category)
        confidence = calculate_confidence_score(
            source_tier=opp.source_tier,
            evidence_count=len(opp.evidence_json),
            has_contradictions=False,  # V1: contradiction 감지 미구현
            field_completeness=_calculate_field_completeness(opp),
            last_verified_at=opp.updated_at,
        )

        priority = calculate_priority_score(
            fit, urgency, actionability, value, confidence,
        )

        # why_fit / next_action 생성
        why_fit = self._generate_why_fit(
            fit, matched_terms, program_category, opp.status.value
        )
        next_action = self._generate_next_action(opp, days_left)

        output = MatchingOutput(
            opportunity_id=opp_id,
            project_name=best_project,
            fit_score=round(fit, 3),
            priority_score=round(priority, 3),
            why_fit=why_fit,
            next_action=next_action,
            urgency_score=round(urgency, 3),
            actionability_score=round(actionability, 3),
            expected_value=round(value, 3),
            confidence=round(confidence, 3),
        )

        # DB 저장 (persist=True)
        if persist:
            rec = FitRecommendation(
                id=generate_id("fit_"),
                opportunity_id=opp_id,
                company_profile_id=profile_id,
                project_name=best_project,
                fit_score=fit,
                priority_score=priority,
                why_fit=why_fit,
                next_action=next_action,
                urgency_score=urgency,
                actionability_score=actionability,
                expected_value=value,
                confidence=confidence,
                computed_at=datetime.now(timezone.utc),
            )
            await self.store.upsert_fit_recommendation(rec)

        self.log.info(
            "matching.complete",
            opportunity_id=opp_id,
            fit=round(fit, 3),
            priority=round(priority, 3),
        )

        return AgentResult(success=True, data=output.__dict__)

    async def batch_rank(
        self,
        opportunity_ids: list[str],
        profile_id: str,
        intent: str = "default",
        top_n: int = 10,
    ) -> list[MatchingOutput]:
        """여러 기회를 batch로 매칭 + intent별 정렬."""
        results: list[MatchingOutput] = []

        profile = await self.store.get_company_profile(profile_id)
        if profile is None:
            return results

        for opp_id in opportunity_ids:
            try:
                agent_result = await self.run(
                    MatchingInput(
                        opportunity_id=opp_id,
                        company_profile_id=profile_id,
                        persist=True,
                    )
                )
                if agent_result.success:
                    output = MatchingOutput(**agent_result.data)
                    # intent별 재계산
                    output.priority_score = calculate_priority_score(
                        output.fit_score,
                        output.urgency_score,
                        output.actionability_score,
                        output.expected_value,
                        output.confidence,
                        intent,
                    )
                    results.append(output)
            except Exception as e:
                self.log.warning(
                    "matching.batch_skip",
                    opportunity_id=opp_id,
                    error=str(e),
                )
                continue

        # priority_score 내림차순 정렬
        results.sort(key=lambda x: x.priority_score, reverse=True)
        return results[:top_n]

    def _find_best_project(
        self, profile: CompanyProfile, opp_tags: list[str]
    ) -> tuple[str | None, list[str]]:
        """프로필 프로젝트 중 최적 매칭 찾기."""
        if not profile.projects:
            return None, []

        opp_set = set(t.lower() for t in opp_tags)
        best_name = None
        best_tags: list[str] = []
        best_overlap = -1
        best_priority = 10_000

        for proj in profile.projects:
            p_tags = [t.lower() for t in proj.get("tags", [])]
            overlap = len(set(p_tags) & opp_set)
            # priority 기반 tiebreaker (낮을수록 우선)
            priority = int(proj.get("priority", 99))
            project_name = (proj.get("name") or "").strip()

            if overlap > best_overlap or (
                overlap == best_overlap and priority < best_priority
            ):
                best_overlap = overlap
                best_priority = priority
                best_name = (
                    project_name
                    if project_name and project_name.lower() not in GENERIC_NAME_STOPWORDS
                    else None
                )
                best_tags = proj.get("tags", [])

        if best_name:
            return best_name, best_tags

        company_name = (profile.company_name or "").strip()
        if company_name and company_name.lower() not in GENERIC_NAME_STOPWORDS:
            return company_name, best_tags
        return None, best_tags

    def _check_stage_match(
        self, profile: CompanyProfile, program_category: str | None
    ) -> bool:
        """프로필 stage가 프로그램 카테고리에 적합한지 간소 판단.

        V1: grant/accelerator는 early stage, vc_cohort/fund는 seed+.
        """
        if not profile.stage or not program_category:
            return True  # 정보 없으면 매칭 가정

        early_stages = {"idea", "mvp", "seed"}
        growth_stages = {"seed", "series_a", "series_b", "growth"}

        stage_val = profile.stage.value
        cat = program_category

        if cat in ("grant", "accelerator", "builder_program", "hackathon_pipeline"):
            return stage_val in early_stages
        if cat in ("vc_cohort", "fund"):
            return stage_val in growth_stages
        return True  # residency 등은 제한 없음

    def _generate_why_fit(
        self,
        fit_score: float,
        matched_terms: list[str],
        program_category: str | None,
        status: str,
    ) -> str:
        """매칭 이유 텍스트 생성 (LLM 없이)."""
        category_label = CATEGORY_REASON_LABEL.get(program_category or "", "opportunity")
        formatted_terms: list[str] = []
        seen: set[str] = set()
        for term in matched_terms:
            normalized = _normalize_blob(term).replace("_", " ")
            if not normalized or normalized in seen or normalized in GENERIC_REASON_TERMS:
                continue
            seen.add(normalized)
            formatted_terms.append(normalized)
        if not formatted_terms:
            return f"{category_label} 기준 기본 적합성 확인"

        thesis_terms = " / ".join(formatted_terms[:3])
        status_suffix = ""
        if status in {"open", "rolling", "upcoming"}:
            status_suffix = f" · 현재 {status}"
        if fit_score >= 0.7:
            return f"{category_label} 기준 {thesis_terms} thesis fit 높음{status_suffix}"
        if fit_score >= 0.4:
            return f"{category_label} 기준 {thesis_terms} 관점에서 일부 매칭{status_suffix}"
        return f"{thesis_terms} 관련성 확인{status_suffix}"

    def _generate_next_action(
        self, opp: Opportunity, days_left: int | None
    ) -> str:
        """다음 행동 추천 (LLM 없이)."""
        if opp.status == OpportunityStatus.CLOSED:
            return "마감됨 — 다음 라운드 모니터링"

        if days_left is not None:
            if days_left <= 3:
                return f"긴급! {days_left}일 내 지원서 제출 필요"
            if days_left <= 7:
                return f"{days_left}일 남음 — 이번 주 내 지원서 작성"
            if days_left <= 14:
                return f"{days_left}일 남음 — 지원서 준비 시작"
            return f"{days_left}일 남음 — 요건 검토 후 준비"

        if opp.status == OpportunityStatus.ROLLING:
            return "Rolling 접수 — 가능한 빨리 지원"

        return "상세 요건 확인 후 지원 준비"
