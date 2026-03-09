"""
Matching Agent 테스트 — fit/urgency/value/priority 계산 정확성.

실행: pytest tests/test_matching.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from src.agents.matching import (
    MatchingAgent,
    calculate_expected_value,
    calculate_fit_score,
    calculate_priority_score,
    calculate_urgency_score,
)
from src.core.config import Config
from src.core.types import (
    CompanyProfile,
    CompanyStage,
    MatchingInput,
    Opportunity,
    OpportunityStatus,
    Organization,
    OrgType,
    OutputStatus,
    Program,
    ProgramCategory,
    generate_id,
)
from src.db.entity_store import EntityStore


# ============================================================
# Fixtures
# ============================================================


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    db_path = tmp_path / "test_matching.db"
    async with EntityStore(db_path) as s:
        await s.init_schema()
        yield s


@pytest.fixture
def cfg():
    return Config()


@pytest_asyncio.fixture
async def setup_data(store: EntityStore):
    """테스트용 데이터 셋업."""
    org = Organization(
        id="org_test",
        normalized_name="test foundation",
        display_name="Test Foundation",
        org_type=OrgType.FOUNDATION,
        sector_tags=["ai", "crypto", "defi"],
    )
    await store.create_organization(org)

    program = Program(
        id="prg_test",
        org_id="org_test",
        normalized_name="test grant",
        display_name="Test Grant",
        category=ProgramCategory.GRANT,
    )
    await store.create_program(program)

    opp = Opportunity(
        id="opp_test",
        program_id="prg_test",
        status=OpportunityStatus.OPEN,
        days_left=5,
        budget_amount=200000.0,
        budget_note="$200K",
        apply_url="https://test.com/apply",
        output_status=OutputStatus.VERIFIED,
        fact_confidence=0.90,
        source_tier=1,
    )
    await store.create_opportunity(opp)

    profile = CompanyProfile(
        id="cp_test",
        company_name="Test Corp",
        stage=CompanyStage.MVP,
        sector_tags=["ai", "crypto", "blockchain"],
        projects=[
            {"name": "TestProject", "priority": 1, "tags": ["ai", "crypto"]},
        ],
    )
    await store.create_company_profile(profile)

    return {"org": org, "program": program, "opp": opp, "profile": profile}


# ============================================================
# Urgency Score Tests (PRD 기준)
# ============================================================


def test_urgency_d0_3():
    """D0-3 → 1.0"""
    assert calculate_urgency_score(0, OpportunityStatus.OPEN) == 1.0
    assert calculate_urgency_score(3, OpportunityStatus.OPEN) == 1.0


def test_urgency_d4_7():
    """D4-7 → 0.8"""
    assert calculate_urgency_score(4, OpportunityStatus.OPEN) == 0.8
    assert calculate_urgency_score(7, OpportunityStatus.OPEN) == 0.8


def test_urgency_d8_14():
    """D8-14 → 0.6"""
    assert calculate_urgency_score(8, OpportunityStatus.OPEN) == 0.6
    assert calculate_urgency_score(14, OpportunityStatus.OPEN) == 0.6


def test_urgency_d15_30():
    """D15-30 → 0.4"""
    assert calculate_urgency_score(15, OpportunityStatus.OPEN) == 0.4
    assert calculate_urgency_score(30, OpportunityStatus.OPEN) == 0.4


def test_urgency_rolling():
    """rolling → 0.3"""
    assert calculate_urgency_score(None, OpportunityStatus.ROLLING) == 0.3


def test_urgency_unknown():
    """unknown days_left → 0.1"""
    assert calculate_urgency_score(None, OpportunityStatus.OPEN) == 0.1


def test_urgency_closed():
    """closed → 0.0"""
    assert calculate_urgency_score(10, OpportunityStatus.CLOSED) == 0.0


# ============================================================
# Fit Score Tests
# ============================================================


def test_fit_score_perfect_match():
    """동일 태그 → 높은 점수."""
    score = calculate_fit_score(
        opp_tags=["ai", "crypto"],
        profile_tags=["ai", "crypto"],
        project_tags=[],
    )
    assert score >= 0.7


def test_fit_score_no_overlap():
    """겹치는 태그 없음 → 낮은 점수."""
    score = calculate_fit_score(
        opp_tags=["gaming", "nft"],
        profile_tags=["ai", "biotech"],
        project_tags=[],
    )
    assert score <= 0.3


def test_fit_score_partial_overlap():
    """일부 겹침 → 중간 점수."""
    score = calculate_fit_score(
        opp_tags=["ai", "crypto", "defi"],
        profile_tags=["ai", "biotech"],
        project_tags=["blockchain"],
    )
    assert 0.1 < score < 0.8


def test_fit_score_no_tags():
    """태그 없음 → 기본값."""
    score = calculate_fit_score([], [], [])
    assert score == 0.0


# ============================================================
# Expected Value Tests
# ============================================================


def test_expected_value_high():
    """$500K+ → 1.0"""
    assert calculate_expected_value(500000) == 1.0
    assert calculate_expected_value(1000000) == 1.0


def test_expected_value_medium():
    """$200K → 0.8"""
    assert calculate_expected_value(200000) == 0.8


def test_expected_value_low():
    """$50K → 0.4"""
    assert calculate_expected_value(50000) == 0.4


def test_expected_value_undisclosed():
    """None → 0.3"""
    assert calculate_expected_value(None) == 0.3


# ============================================================
# Priority Score Tests (4-factor)
# ============================================================


def test_priority_default_weights():
    """기본 가중치: 0.35 + 0.35 + 0.15 + 0.15"""
    score = calculate_priority_score(
        fit=0.8, urgency=0.6, value=0.5, confidence=0.9
    )
    # 0.8*0.35 + 0.6*0.35 + 0.5*0.15 + 0.9*0.15
    # = 0.28 + 0.21 + 0.075 + 0.135 = 0.70
    assert abs(score - 0.70) < 0.01


def test_priority_urgent_weights():
    """urgent: urgency 가중치 0.50"""
    default = calculate_priority_score(0.5, 1.0, 0.5, 0.5, "default")
    urgent = calculate_priority_score(0.5, 1.0, 0.5, 0.5, "urgent")
    assert urgent > default  # urgency 높으면 urgent가 더 높아야 함


def test_priority_highest_money_weights():
    """highest_money: value 가중치 0.50"""
    default = calculate_priority_score(0.5, 0.5, 1.0, 0.5, "default")
    money = calculate_priority_score(0.5, 0.5, 1.0, 0.5, "highest_money")
    assert money > default


def test_priority_best_ecosystem_weights():
    """best_ecosystem_match: fit 가중치 0.50"""
    default = calculate_priority_score(1.0, 0.5, 0.5, 0.5, "default")
    eco = calculate_priority_score(1.0, 0.5, 0.5, 0.5, "best_ecosystem_match")
    assert eco > default


# ============================================================
# MatchingAgent Integration Tests
# ============================================================


@pytest.mark.asyncio
async def test_matching_agent_run(store: EntityStore, cfg: Config, setup_data):
    """MatchingAgent 전체 실행."""
    agent = MatchingAgent(store, cfg)
    result = await agent.run(
        MatchingInput(
            opportunity_id="opp_test",
            company_profile_id="cp_test",
        )
    )

    assert result.success is True
    assert result.data["opportunity_id"] == "opp_test"
    assert result.data["fit_score"] > 0
    assert result.data["priority_score"] > 0
    assert result.data["urgency_score"] == 0.8  # days_left=5 → D4-7
    assert result.data["why_fit"] != ""
    assert result.data["next_action"] != ""


@pytest.mark.asyncio
async def test_matching_agent_persist(store: EntityStore, cfg: Config, setup_data):
    """persist=True일 때 fit_recommendations에 저장."""
    agent = MatchingAgent(store, cfg)
    result = await agent.run(
        MatchingInput(
            opportunity_id="opp_test",
            company_profile_id="cp_test",
            persist=True,
        )
    )

    assert result.success is True

    # DB에서 저장 확인
    rec = await store.get_fit_recommendation("opp_test", "cp_test")
    assert rec is not None
    assert rec.fit_score > 0


@pytest.mark.asyncio
async def test_matching_invalid_opp(store: EntityStore, cfg: Config):
    """존재하지 않는 opportunity → 실패."""
    agent = MatchingAgent(store, cfg)
    result = await agent.run(
        MatchingInput(
            opportunity_id="nonexistent",
            company_profile_id="cp_test",
        )
    )
    assert result.success is False
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_batch_rank(store: EntityStore, cfg: Config, setup_data):
    """batch_rank 정렬."""
    # 추가 opp 생성
    opp2 = Opportunity(
        id="opp_test2",
        program_id="prg_test",
        status=OpportunityStatus.ROLLING,
        budget_amount=500000.0,
        apply_url="https://test.com/apply2",
        output_status=OutputStatus.VERIFIED,
        fact_confidence=0.85,
    )
    await store.create_opportunity(opp2)

    agent = MatchingAgent(store, cfg)
    ranked = await agent.batch_rank(
        opportunity_ids=["opp_test", "opp_test2"],
        profile_id="cp_test",
        intent="default",
        top_n=5,
    )

    assert len(ranked) == 2
    # priority_score 내림차순
    assert ranked[0].priority_score >= ranked[1].priority_score
