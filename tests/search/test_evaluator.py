"""
SufficiencyEvaluator 단위 테스트.

순수 규칙 기반 — 외부 의존성 없음.
"""

from __future__ import annotations

import pytest

from src.search.evaluator import (
    MAX_ROUNDS,
    MIN_APPLY_URLS,
    MIN_TOTAL_OPPS,
    SufficiencyEvaluator,
)
from src.search.types import ExtractedOpportunity, SearchContext, SearchRound


def _make_opp(
    org: str = "Org",
    program: str = "Program",
    apply_url: str | None = None,
    category: str = "grant",
) -> ExtractedOpportunity:
    return ExtractedOpportunity(
        organization=org,
        program=program,
        apply_url=apply_url,
        category=category,
    )


class TestSufficiencyEvaluator:
    def test_empty_context_insufficient(self):
        evaluator = SufficiencyEvaluator()
        ctx = SearchContext(original_query="test")
        evaluator.evaluate(ctx)
        assert ctx.is_sufficient is False
        assert len(ctx.gap_reasons) > 0

    def test_sufficient_with_apply_urls(self):
        evaluator = SufficiencyEvaluator()
        ctx = SearchContext(original_query="test")
        # 5개 고유 apply_url
        for i in range(MIN_APPLY_URLS):
            ctx.all_opportunities.append(
                _make_opp(
                    org=f"Org{i}",
                    program=f"Program{i}",
                    apply_url=f"https://apply{i}.com",
                )
            )
        evaluator.evaluate(ctx)
        assert ctx.is_sufficient is True
        assert ctx.gap_reasons == []

    def test_sufficient_with_total_count(self):
        evaluator = SufficiencyEvaluator()
        ctx = SearchContext(original_query="test")
        # 8개 고유 기회 (apply_url 없어도)
        for i in range(MIN_TOTAL_OPPS):
            ctx.all_opportunities.append(
                _make_opp(org=f"Org{i}", program=f"Program{i}")
            )
        evaluator.evaluate(ctx)
        assert ctx.is_sufficient is True

    def test_max_rounds_forces_sufficient(self):
        evaluator = SufficiencyEvaluator()
        ctx = SearchContext(original_query="test", max_rounds=MAX_ROUNDS)
        # 최대 라운드만큼 빈 라운드 추가
        for i in range(MAX_ROUNDS):
            ctx.rounds.append(SearchRound(round_number=i + 1))
        evaluator.evaluate(ctx)
        assert ctx.is_sufficient is True

    def test_gap_missing_apply_urls(self):
        evaluator = SufficiencyEvaluator()
        ctx = SearchContext(original_query="test")
        # 3개만 — 부족
        for i in range(3):
            ctx.all_opportunities.append(
                _make_opp(
                    org=f"Org{i}",
                    program=f"Program{i}",
                    apply_url=f"https://apply{i}.com",
                )
            )
        evaluator.evaluate(ctx)
        assert ctx.is_sufficient is False
        assert any("missing_apply_urls" in g for g in ctx.gap_reasons)

    def test_gap_low_total(self):
        evaluator = SufficiencyEvaluator()
        ctx = SearchContext(original_query="test")
        ctx.all_opportunities.append(_make_opp())
        evaluator.evaluate(ctx)
        assert any("low_total" in g for g in ctx.gap_reasons)

    def test_category_mismatch_detected(self):
        evaluator = SufficiencyEvaluator()
        ctx = SearchContext(original_query="test", category="accelerator")
        # grant만 있음
        ctx.all_opportunities.append(
            _make_opp(category="grant")
        )
        evaluator.evaluate(ctx)
        assert any("category_mismatch" in g for g in ctx.gap_reasons)

    def test_duplicate_opportunities_deduped_in_count(self):
        evaluator = SufficiencyEvaluator()
        ctx = SearchContext(original_query="test")
        # 같은 org+program 3번 반복 → 고유 1개
        for _ in range(3):
            ctx.all_opportunities.append(
                _make_opp(
                    org="Same Org",
                    program="Same Program",
                    apply_url="https://apply.com",
                )
            )
        evaluator.evaluate(ctx)
        assert ctx.total_unique_opportunities == 1
        assert ctx.unique_apply_urls == 1
        assert ctx.is_sufficient is False
