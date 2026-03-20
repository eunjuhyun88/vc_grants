"""
Card Renderer 테스트 — Telegram MarkdownV2 출력 검증.

실행: pytest tests/test_card_renderer.py -v
"""

from __future__ import annotations

import pytest

from src.core.types import DailyBriefData, DossierCard, OpportunityCard
from src.interface.card_renderer import (
    _is_stale_date_text,
    escape_md,
    render_daily_brief,
    render_dossier_card,
    render_empty,
    render_error,
    render_funding_map,
    render_org_dossier,
    render_opportunity_card,
    render_ranked_list,
    render_social_alert_candidate,
)
from src.research.dossier_builder import FundingMap, OrganizationDossier, ProgramDossier


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


def test_render_opportunity_card_hides_stale_deadline():
    card = OpportunityCard(
        organization="Test Org",
        program="Old Cohort",
        category="accelerator",
        status="open",
        apply_url="https://test.com/apply",
        confidence=0.8,
        deadline="2026-03-01",
    )
    text = render_opportunity_card(card)
    assert "2026\\-03\\-01" not in text


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


def test_render_funding_map(sample_card):
    """Funding map 렌더링."""
    sample_card.description = "12-week accelerator with builder mentorship"
    sample_card.source_url = "https://nitroacc.xyz"
    funding_map = FundingMap(
        project_name="HOOT",
        tier1_ecosystems=["Bittensor", "NEAR"],
        tier2_ecosystems=["Ethereum", "Solana"],
        matched_ecosystems=["Monad", "Chainlink"],
        covered_target_ecosystems=["NEAR", "Solana"],
    )
    text = render_funding_map(
        project_name="HOOT",
        funding_map=funding_map,
        cards=[sample_card],
        coverage=0.5,
    )
    assert "FUNDING MAP FOR HOOT" in text
    assert "Bittensor" in text
    assert "Chainlink" in text
    assert "커버리지" in text
    assert "accelerator with builder mentorship" in text
    assert "[공식](https://nitroacc.xyz)" in text
    assert "[지원](https://esp.ethereum.foundation)" in text


def test_render_org_dossier(sample_card):
    """Organization dossier 상세 렌더링."""
    dossier = OrganizationDossier(
        organization="Monad",
        ecosystems=["Monad"],
        programs=["Nitro Accelerator"],
        partners=["Paradigm"],
        mentors=["Electric Capital"],
        portfolio_analogs=["Aethir"],
        matched_programs=["Nitro Accelerator"],
        official_urls=["https://monad.xyz", "https://nitroacc.xyz"],
        program_details=[
            ProgramDossier(
                organization="Monad",
                program="Nitro Accelerator",
                program_type="vc_cohort",
                description="12-week accelerator with mentorship and capital.",
                official_url="https://nitroacc.xyz",
                apply_url="https://nitroacc.xyz/apply",
                funding_range="Up to $500k per team",
                deadline_text="March 14, 2026",
                status_note="Applications close March 14, 2026",
            )
        ],
    )
    dossier_card = DossierCard(
        org_name="Monad",
        org_type="ecosystem",
        website="https://monad.xyz",
        confidence=0.8,
    )
    text = render_org_dossier(
        dossier=dossier,
        org_card=dossier_card,
        opportunity_cards=[sample_card],
    )
    assert "Monad" in text
    assert "Nitro Accelerator" in text
    assert "Paradigm" in text
    assert "Electric Capital" in text
    assert "accelerator with mentorship and capital" in text
    assert "March 14, 2026" in text
    assert "[공식](https://nitroacc.xyz)" in text
    assert "[지원](https://nitroacc.xyz/apply)" in text


def test_render_org_dossier_hides_stale_program_date(sample_card):
    dossier = OrganizationDossier(
        organization="Monad",
        program_details=[
            ProgramDossier(
                organization="Monad",
                program="Old Program",
                deadline_text="March 01, 2026",
                status_note=None,
            )
        ],
    )
    text = render_org_dossier(dossier=dossier, org_card=None, opportunity_cards=[sample_card])
    assert "March 01, 2026" not in text


def test_render_social_alert_candidate():
    text = render_social_alert_candidate(
        {
            "organization_name": "Monad",
            "program_name": "Nitro Accelerator",
            "category": "vc_cohort",
            "status": "open",
            "apply_url": "https://nitroacc.xyz/apply",
            "program_url": "https://nitroacc.xyz",
            "source_url": "https://x.com/monad/status/2021278828484567142",
            "matched_account": "monad",
            "monitoring_round": "ecosystem-operators",
            "signal_type": "applications_open",
            "deadline_at": "2026-03-14T00:00:00+00:00",
            "days_left": 1,
            "fact_confidence": 0.92,
        }
    )
    assert "NEW VERIFIED SOCIAL FUNDING SIGNAL" in text
    assert "Monad" in text
    assert "Nitro Accelerator" in text
    assert "2026\\-03\\-14" in text
    assert "[공식](https://nitroacc.xyz)" in text
    assert "[지원](https://nitroacc.xyz/apply)" in text
    assert "[소셜 근거](https://x.com/monad/status/2021278828484567142)" in text


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


def test_is_stale_date_text():
    assert _is_stale_date_text("2026-03-01") is True
    assert _is_stale_date_text("March 01, 2026") is True
    assert _is_stale_date_text("Rolling") is False
