"""
Card Renderer 테스트 — Telegram MarkdownV2 출력 검증.

실행: pytest tests/test_card_renderer.py -v
"""

from __future__ import annotations

import pytest

from src.core.types import DailyBriefData, DossierCard, OpportunityCard
from src.interface.card_renderer import (
    escape_md,
    render_daily_brief,
    render_dossier_card,
    render_empty,
    render_error,
    render_opportunity_card,
    render_ranked_list,
)


# ============================================================
# escape_md Tests
# ============================================================


def test_escape_md_special_chars():
    """특수문자 이스케이프."""
    assert escape_md("hello_world") == r"hello\_world"
    assert escape_md("a*b*c") == r"a\*b\*c"
    assert escape_md("test.com") == r"test\.com"
    assert escape_md("(hello)") == r"\(hello\)"


def test_escape_md_plain_text():
    """일반 텍스트는 변경 없음."""
    assert escape_md("hello world") == "hello world"
    assert escape_md("abc123") == "abc123"


# ============================================================
# OpportunityCard Tests
# ============================================================


@pytest.fixture
def sample_card() -> OpportunityCard:
    return OpportunityCard(
        organization="Ethereum Foundation",
        program="ESP Grants",
        category="grant",
        status="open",
        apply_url="https://esp.ethereum.foundation",
        confidence=0.95,
        deadline="2026-06-01",
        days_left=14,
        budget="$50K-$500K",
    )


@pytest.fixture
def card_with_fit() -> OpportunityCard:
    return OpportunityCard(
        organization="a16z Crypto",
        program="Speedrun",
        category="vc_cohort",
        status="deadline",
        apply_url="https://speedrun.xyz/apply",
        confidence=0.90,
        deadline="2026-04-15",
        days_left=3,
        budget="$500K",
        fit_score=0.85,
        priority_score=0.78,
        why_fit="높은 적합도: ai, crypto 분야 매칭",
        next_action="긴급! 3일 내 지원서 제출 필요",
    )


def test_render_opportunity_card_basic(sample_card):
    """기본 카드 렌더링."""
    text = render_opportunity_card(sample_card)
    assert "Ethereum Foundation" in text
    assert "ESP Grants" in text
    assert "Grant" in text
    assert "OPEN" in text
    assert "$50K" in text
    assert "지원하기" in text
    assert "esp.ethereum.foundation" in text


def test_render_opportunity_card_with_index(sample_card):
    """인덱스 포함 렌더링."""
    text = render_opportunity_card(sample_card, index=1)
    assert "*1\\.*" in text


def test_render_opportunity_card_with_fit(card_with_fit):
    """fit 데이터 포함 카드."""
    text = render_opportunity_card(card_with_fit)
    assert "적합도" in text
    assert "우선순위" in text
    assert "ai" in text or "crypto" in text
    assert "긴급" in text
    # 3일 마감 → 🔥 표시
    assert "🔥" in text


def test_render_opportunity_card_no_deadline():
    """마감일 없는 카드."""
    card = OpportunityCard(
        organization="Test Org",
        program="Test Program",
        category="grant",
        status="rolling",
        apply_url="https://test.com",
        confidence=0.80,
    )
    text = render_opportunity_card(card)
    assert "ROLLING" in text
    assert "D-" not in text  # 마감일 없음


# ============================================================
# Ranked List Tests
# ============================================================


def test_render_ranked_list(sample_card, card_with_fit):
    """리스트 렌더링."""
    text = render_ranked_list(
        [sample_card, card_with_fit],
        title="테스트 목록",
    )
    assert "테스트 목록" in text
    assert "총 2건" in text
    assert "*1\\.*" in text
    assert "*2\\.*" in text


def test_render_ranked_list_empty():
    """빈 리스트."""
    text = render_ranked_list([])
    assert "데이터가 없습니다" in text


def test_render_ranked_list_max_items(sample_card):
    """max_items 초과 시 truncate."""
    cards = [sample_card] * 15
    text = render_ranked_list(cards, max_items=10)
    assert "외 5건" in text


# ============================================================
# Dossier Card Tests
# ============================================================


def test_render_dossier_card():
    """Dossier 카드 렌더링."""
    dossier = DossierCard(
        org_name="Paradigm",
        org_type="vc",
        website="https://paradigm.xyz",
        portfolio_count=50,
        avg_check_size="$5M-$30M",
        focus_areas=["DeFi", "Infrastructure", "L1/L2"],
        confidence=0.85,
    )
    text = render_dossier_card(dossier)
    assert "Paradigm" in text
    assert "paradigm.xyz" in text
    assert "50" in text
    assert "DeFi" in text


# ============================================================
# Daily Brief Tests
# ============================================================


def test_render_daily_brief(sample_card, card_with_fit):
    """일일 브리핑 렌더링."""
    brief = DailyBriefData(
        top_opportunities=[sample_card],
        new_today=[card_with_fit],
        deadline_soon=[card_with_fit],
        changes=[{"description": "ESP Grant 마감일 변경"}],
    )
    text = render_daily_brief(brief)
    assert "일일 펀딩 브리핑" in text
    assert "마감 임박" in text
    assert "새로 발견" in text
    assert "변경사항" in text


def test_render_daily_brief_empty():
    """빈 브리핑."""
    brief = DailyBriefData()
    text = render_daily_brief(brief)
    assert "업데이트가 없습니다" in text


# ============================================================
# Utility Functions Tests
# ============================================================


def test_render_empty_with_category():
    """카테고리별 빈 메시지."""
    text = render_empty("grant")
    assert "Grant" in text


def test_render_empty_generic():
    """일반 빈 메시지."""
    text = render_empty()
    assert "데이터가 없습니다" in text


def test_render_error():
    """에러 메시지."""
    text = render_error()
    assert "⚠️" in text
    assert "DB" in text


def test_render_error_custom():
    """커스텀 에러 메시지."""
    text = render_error("커스텀 에러 발생")
    assert "커스텀 에러 발생" in text
