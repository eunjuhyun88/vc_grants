"""
Funding Intelligence Agent — Matching Agent.

4-factor priority: fit*0.35 + urgency*0.35 + value*0.15 + confidence*0.15
LLM 없이 순수 계산 (deterministic).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from src.agents.base_agent import BaseAgent
from src.core.errors import MatchingError
from src.core.types import (
    AgentResult,
    CompanyProfile,
    FitRecommendation,
    MatchingInput,
    MatchingOutput,
    Opportunity,
    OpportunityStatus,
    RankingIntent,
    calculate_days_left,
    generate_id,
)

logger = structlog.get_logger()

# ============================================================
# Intent별 가중치 프리셋 (PRD 기준)
# ============================================================
INTENT_WEIGHTS: dict[str, dict[str, float]] = {
    "default": {
        "fit": 0.35,
        "urgency": 0.35,
        "value": 0.15,
        "confidence": 0.15,
    },
    "urgent": {
        "fit": 0.20,
        "urgency": 0.50,
        "value": 0.15,
        "confidence": 0.15,
    },
    "highest_money": {
        "fit": 0.20,
        "urgency": 0.15,
        "value": 0.50,
        "confidence": 0.15,
    },
    "best_ecosystem_match": {
        "fit": 0.50,
        "urgency": 0.20,
        "value": 0.15,
        "confidence": 0.15,
    },
}

# ============================================================
# Urgency Score 테이블 (PRD 기준)
# ============================================================
# D0-3: 1.0, D4-7: 0.8, D8-14: 0.6, D15-30: 0.4
# rolling: 0.3, unknown: 0.1, closed: 0.0


def calculate_urgency_score(
    days_left: int | None,
    status: OpportunityStatus,
) -> float:
    """마감일 기반 urgency score 계산."""
    if status == OpportunityStatus.CLOSED:
        return 0.0
    if status == OpportunityStatus.ROLLING:
        return 0.3

    if days_left is None:
        return 0.1  # unknown

    if days_left <= 3:
        return 1.0
    if days_left <= 7:
        return 0.8
    if days_left <= 14:
        return 0.6
    if days_left <= 30:
        return 0.4
    return 0.2  # 30일 초과


def calculate_fit_score(
    opp_tags: list[str],
    profile_tags: list[str],
    project_tags: list[str],
) -> float:
    """태그 overlap 기반 fit score 계산."""
    if not profile_tags and not project_tags:
        return 0.0

    # 프로필 태그 + 프로젝트 태그 통합
    all_user_tags = set(t.lower() for t in profile_tags)
    all_user_tags.update(t.lower() for t in project_tags)

    opp_tag_set = set(t.lower() for t in opp_tags)

    if not opp_tag_set or not all_user_tags:
        return 0.3  # 태그 없으면 기본값

    # Jaccard-like overlap
    intersection = opp_tag_set & all_user_tags
    union = opp_tag_set | all_user_tags

    overlap = len(intersection) / len(union) if union else 0.0

    # 0.0 ~ 1.0 범위로 스케일링 (최소 0.1)
    return min(1.0, max(0.1, overlap * 2))


def calculate_expected_value(budget_amount: float | None) -> float:
    """펀딩 금액 기반 expected value 계산."""
    if budget_amount is None:
        return 0.3  # undisclosed

    if budget_amount >= 500000:
        return 1.0
    if budget_amount >= 200000:
        return 0.8
    if budget_amount >= 100000:
        return 0.6
    if budget_amount >= 50000:
        return 0.4
    if budget_amount >= 10000:
        return 0.3
    return 0.2


def calculate_priority_score(
    fit: float,
    urgency: float,
    value: float,
    confidence: float,
    intent: str = "default",
) -> float:
    """4-factor 가중 priority score 계산."""
    weights = INTENT_WEIGHTS.get(intent, INTENT_WEIGHTS["default"])
    return (
        fit * weights["fit"]
        + urgency * weights["urgency"]
        + value * weights["value"]
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

        # Organization 태그 가져오기 (opp → program → org)
        program = await self.store.get_program(opp.program_id)
        org_tags: list[str] = []
        if program:
            org = await self.store.get_organization(program.org_id)
            if org:
                org_tags = org.sector_tags

        # 최적 프로젝트 매칭
        best_project, project_tags = self._find_best_project(
            profile, org_tags
        )

        # days_left 계산
        days_left = opp.days_left
        if days_left is None and opp.deadline_at:
            days_left = calculate_days_left(opp.deadline_at)

        # 4-factor 계산
        fit = calculate_fit_score(org_tags, profile.sector_tags, project_tags)
        urgency = calculate_urgency_score(days_left, opp.status)
        value = calculate_expected_value(opp.budget_amount)
        confidence = opp.fact_confidence

        priority = calculate_priority_score(
            fit, urgency, value, confidence
        )

        # why_fit / next_action 생성
        why_fit = self._generate_why_fit(
            fit, org_tags, profile.sector_tags, project_tags
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

        for proj in profile.projects:
            p_tags = [t.lower() for t in proj.get("tags", [])]
            overlap = len(set(p_tags) & opp_set)
            # priority 기반 tiebreaker (낮을수록 우선)
            priority = proj.get("priority", 99)

            if overlap > best_overlap or (
                overlap == best_overlap and priority < 99
            ):
                best_overlap = overlap
                best_name = proj.get("name")
                best_tags = proj.get("tags", [])

        return best_name, best_tags

    def _generate_why_fit(
        self,
        fit_score: float,
        opp_tags: list[str],
        profile_tags: list[str],
        project_tags: list[str],
    ) -> str:
        """매칭 이유 텍스트 생성 (LLM 없이)."""
        all_user = set(t.lower() for t in profile_tags)
        all_user.update(t.lower() for t in project_tags)
        opp_set = set(t.lower() for t in opp_tags)

        matched = sorted(all_user & opp_set)

        if not matched:
            return "분야 직접 매칭은 없으나 관련 가능성 있음"

        tag_str = ", ".join(matched[:5])
        if fit_score >= 0.7:
            return f"높은 적합도: {tag_str} 분야 매칭"
        if fit_score >= 0.4:
            return f"중간 적합도: {tag_str} 분야 일부 매칭"
        return f"기본 매칭: {tag_str}"

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
