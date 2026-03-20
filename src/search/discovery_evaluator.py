"""
Funding Intelligence Agent — DiscoveryEvaluator.

autoresearch 패턴의 "평가" 단계.
현재까지 발견된 결과를 분석하고 gap을 식별한다.

규칙 기반 (LLM 없음). 4가지 gap 검출:
  1. underrepresented_category  — 특정 카테고리 결과 부족
  2. missing_ecosystems          — target_ecosystems 중 미발견
  3. low_org_diversity           — 발견된 조직 수 부족
  4. low_apply_urls              — apply_url 비율 낮음
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from src.search.types import DiscoveryContext

logger = structlog.get_logger()

# 검색 대상 카테고리 (더 많은 유형 포함)
TARGET_CATEGORIES = {
    "grant", "accelerator", "vc_cohort", "ecosystem_builder",
    "builder_program", "hackathon_pipeline", "fund",
}

# 카테고리별 최소 기대 수 (이보다 적으면 gap) — 공격적
MIN_CATEGORY_COUNT = 5

# 최소 조직 다양성 — 공격적
MIN_ORG_DIVERSITY = 15

# apply_url 최소 비율
MIN_APPLY_URL_RATIO = 0.5


class DiscoveryEvaluator:
    """Discovery loop gap 분석기.

    autoresearch의 val_bpb 체크에 해당.
    "아직 더 찾아야 하는가?" 를 판단한다.
    """

    def __init__(self) -> None:
        self._log = logger.bind(component="discovery_evaluator")

    def evaluate(self, ctx: DiscoveryContext) -> list[str]:
        """현재 발견 결과의 gap을 분석한다.

        Args:
            ctx: DiscoveryContext — 누적 발견 상태

        Returns:
            gap_reason 문자열 리스트. 비면 "충분"을 의미.
            예: ["underrepresented_category:vc_cohort:found=0",
                 "missing_ecosystems:monad,bittensor"]
        """
        gaps: list[str] = []

        # ── 1. 카테고리 커버리지 ──
        gaps.extend(self._check_category_coverage(ctx))

        # ── 2. 에코시스템 커버리지 ──
        gaps.extend(self._check_ecosystem_coverage(ctx))

        # ── 3. 조직 다양성 ──
        gaps.extend(self._check_org_diversity(ctx))

        # ── 4. apply_url 비율 ──
        gaps.extend(self._check_apply_url_ratio(ctx))

        self._log.info(
            "discovery.evaluate",
            round=ctx.current_round,
            total_opps=len(ctx.all_raw_opps),
            gap_count=len(gaps),
            gaps=gaps[:5],
        )

        return gaps

    # ============================================================
    # Gap 검출 함수
    # ============================================================

    def _check_category_coverage(
        self, ctx: DiscoveryContext
    ) -> list[str]:
        """카테고리별 결과 분포 체크."""
        gaps: list[str] = []
        dist = ctx.category_distribution

        for cat in TARGET_CATEGORIES:
            count = dist.get(cat, 0)
            if count < MIN_CATEGORY_COUNT:
                gaps.append(
                    f"underrepresented_category:{cat}:found={count}"
                )

        return gaps

    def _check_ecosystem_coverage(
        self, ctx: DiscoveryContext
    ) -> list[str]:
        """target_ecosystems 커버리지 체크."""
        target = ctx.profile.target_ecosystems or []
        if not target:
            return []

        covered = ctx.ecosystem_coverage
        missing = [
            eco for eco in target
            if eco.lower() not in covered
        ]

        if missing:
            return [f"missing_ecosystems:{','.join(missing)}"]

        return []

    def _check_org_diversity(
        self, ctx: DiscoveryContext
    ) -> list[str]:
        """발견된 조직 수 다양성 체크."""
        org_count = len(ctx.known_org_names)
        if org_count < MIN_ORG_DIVERSITY:
            return [f"low_org_diversity:found={org_count}"]
        return []

    def _check_apply_url_ratio(
        self, ctx: DiscoveryContext
    ) -> list[str]:
        """apply_url 보유 비율 체크."""
        total = len(ctx.all_raw_opps)
        if total == 0:
            return []

        with_url = sum(
            1 for opp in ctx.all_raw_opps
            if opp.get("apply_url")
        )

        ratio = with_url / total
        if ratio < MIN_APPLY_URL_RATIO:
            return [f"low_apply_urls:{with_url}/{total}"]

        return []
