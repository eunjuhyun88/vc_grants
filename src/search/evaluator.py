"""
Sufficiency Evaluator — 충분성 평가 (규칙 기반, LLM 없음).

검색 결과가 충분한지 판단하고, 부족하면 갭 이유를 식별.
"""

from __future__ import annotations

import structlog

from src.search.types import SearchContext

logger = structlog.get_logger()

# ============================================================
# 충분성 기준
# ============================================================

MIN_APPLY_URLS = 5       # apply_url이 있는 고유 기회
MIN_TOTAL_OPPS = 8       # 총 고유 기회 수
MAX_ROUNDS = 3           # 최대 라운드 수


class SufficiencyEvaluator:
    """규칙 기반 충분성 평가기."""

    def evaluate(self, ctx: SearchContext) -> None:
        """SearchContext를 평가하고 is_sufficient / gap_reasons 업데이트.

        충분 조건 (OR):
        - apply_url 있는 고유 기회 ≥ 5
        - 총 고유 기회 ≥ 8
        - 라운드 ≥ 3 (최대)

        부족 시 갭 이유 식별.
        """
        gaps: list[str] = []

        apply_count = ctx.unique_apply_urls
        total_count = ctx.total_unique_opportunities
        round_num = ctx.current_round

        # 최대 라운드 도달 → 강제 충분
        if round_num >= ctx.max_rounds:
            ctx.is_sufficient = True
            ctx.gap_reasons = []
            logger.info(
                "search.evaluator.max_rounds_reached",
                round=round_num,
                apply_urls=apply_count,
                total=total_count,
            )
            return

        # 충분성 체크
        if apply_count >= MIN_APPLY_URLS:
            ctx.is_sufficient = True
            ctx.gap_reasons = []
            logger.info(
                "search.evaluator.sufficient_apply_urls",
                apply_urls=apply_count,
                total=total_count,
            )
            return

        if total_count >= MIN_TOTAL_OPPS:
            ctx.is_sufficient = True
            ctx.gap_reasons = []
            logger.info(
                "search.evaluator.sufficient_total",
                apply_urls=apply_count,
                total=total_count,
            )
            return

        # 부족 — 갭 이유 식별
        if apply_count < MIN_APPLY_URLS:
            gaps.append(
                f"missing_apply_urls: only {apply_count}/{MIN_APPLY_URLS}"
            )

        if total_count < MIN_TOTAL_OPPS:
            gaps.append(
                f"low_total: only {total_count}/{MIN_TOTAL_OPPS}"
            )

        # 카테고리 다양성 체크
        if ctx.category:
            categories_found = {
                o.category for o in ctx.all_opportunities if o.category
            }
            if ctx.category not in categories_found and total_count > 0:
                gaps.append(
                    f"category_mismatch: target={ctx.category}, "
                    f"found={categories_found}"
                )

        ctx.is_sufficient = False
        ctx.gap_reasons = gaps

        logger.info(
            "search.evaluator.insufficient",
            round=round_num,
            apply_urls=apply_count,
            total=total_count,
            gaps=gaps,
        )
