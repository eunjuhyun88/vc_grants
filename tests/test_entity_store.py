"""
EntityStore 테스트 — Phase 1 CRUD 검증.

실행: pytest tests/test_entity_store.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio

from src.core.types import (
    ApplicationEndpoint,
    CompanyProfile,
    CompanyStage,
    EndpointType,
    FitRecommendation,
    Observation,
    Opportunity,
    OpportunityStatus,
    Organization,
    OrgType,
    OutputStatus,
    Program,
    ProgramCategory,
    generate_id,
    normalize_org_name,
    normalize_url,
)
from src.db.entity_store import EntityStore


# ============================================================
# Fixtures
# ============================================================


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    """테스트용 임시 DB."""
    db_path = tmp_path / "test.db"
    async with EntityStore(db_path) as s:
        await s.init_schema()
        yield s


@pytest_asyncio.fixture
async def sample_org(store: EntityStore) -> Organization:
    """샘플 조직 생성."""
    org = Organization(
        id=generate_id("org_"),
        normalized_name="a16z crypto",
        display_name="a16z Crypto",
        domain="a16zcrypto.com",
        org_type=OrgType.VC,
        sector_tags=["crypto", "web3"],
        website_url="https://a16zcrypto.com",
    )
    await store.create_organization(org)
    return org


@pytest_asyncio.fixture
async def sample_program(store: EntityStore, sample_org: Organization) -> Program:
    """샘플 프로그램 생성."""
    program = Program(
        id=generate_id("prg_"),
        org_id=sample_org.id,
        normalized_name="speedrun",
        display_name="Speedrun",
        category=ProgramCategory.VC_COHORT,
        program_url="https://speedrun.xyz",
        description="Crypto accelerator by a16z",
    )
    await store.create_program(program)
    return program


@pytest_asyncio.fixture
async def sample_opportunity(
    store: EntityStore, sample_program: Program
) -> Opportunity:
    """샘플 기회 생성."""
    opp = Opportunity(
        id=generate_id("opp_"),
        program_id=sample_program.id,
        cycle_key="S2026",
        status=OpportunityStatus.OPEN,
        budget_amount=500000.0,
        budget_note="$500K",
        apply_url="https://speedrun.xyz/apply",
        output_status=OutputStatus.VERIFIED,
        fact_confidence=0.90,
        source_tier=1,
    )
    await store.create_opportunity(opp)
    return opp


# ============================================================
# Organization Tests
# ============================================================


@pytest.mark.asyncio
async def test_create_and_get_organization(store: EntityStore):
    """조직 생성 후 조회."""
    org = Organization(
        id=generate_id("org_"),
        normalized_name="ethereum",
        display_name="Ethereum Foundation",
        domain="ethereum.org",
        org_type=OrgType.FOUNDATION,
    )
    await store.create_organization(org)
    result = await store.get_organization(org.id)
    assert result is not None
    assert result.normalized_name == "ethereum"
    assert result.display_name == "Ethereum Foundation"
    assert result.org_type == OrgType.FOUNDATION


@pytest.mark.asyncio
async def test_organization_dedup_by_domain(store: EntityStore):
    """같은 domain으로 조직 조회."""
    org = Organization(
        id=generate_id("org_"),
        normalized_name="solana",
        display_name="Solana Foundation",
        domain="solana.org",
        org_type=OrgType.FOUNDATION,
    )
    await store.create_organization(org)
    result = await store.get_organization_by_domain("solana.org")
    assert result is not None
    assert result.id == org.id


@pytest.mark.asyncio
async def test_organization_by_name(store: EntityStore):
    """정규화된 이름으로 조직 조회."""
    org = Organization(
        id=generate_id("org_"),
        normalized_name="alliance dao",
        display_name="Alliance DAO",
        org_type=OrgType.ACCELERATOR,
    )
    await store.create_organization(org)
    result = await store.get_organization_by_name("alliance dao")
    assert result is not None
    assert result.id == org.id


@pytest.mark.asyncio
async def test_list_organizations_filter(store: EntityStore, sample_org: Organization):
    """org_type 필터로 조직 목록 조회."""
    # VC org 추가
    org2 = Organization(
        id=generate_id("org_"),
        normalized_name="paradigm",
        display_name="Paradigm",
        org_type=OrgType.VC,
    )
    await store.create_organization(org2)

    # Foundation org 추가
    org3 = Organization(
        id=generate_id("org_"),
        normalized_name="ethereum",
        display_name="Ethereum Foundation",
        org_type=OrgType.FOUNDATION,
    )
    await store.create_organization(org3)

    vc_list = await store.list_organizations(org_type=OrgType.VC)
    assert len(vc_list) >= 2  # sample_org + org2

    foundation_list = await store.list_organizations(org_type=OrgType.FOUNDATION)
    assert len(foundation_list) >= 1


@pytest.mark.asyncio
async def test_update_organization(store: EntityStore, sample_org: Organization):
    """조직 필드 업데이트."""
    await store.update_organization(
        sample_org.id,
        display_name="a16z Crypto (Updated)",
        sector_tags=["crypto", "web3", "defi"],
    )
    result = await store.get_organization(sample_org.id)
    assert result is not None
    assert result.display_name == "a16z Crypto (Updated)"
    assert "defi" in result.sector_tags


# ============================================================
# Program Tests
# ============================================================


@pytest.mark.asyncio
async def test_create_program_requires_org(store: EntityStore):
    """존재하지 않는 org_id로 프로그램 생성 시 FK 에러."""
    program = Program(
        id=generate_id("prg_"),
        org_id="nonexistent_org",
        normalized_name="fake program",
        category=ProgramCategory.GRANT,
    )
    with pytest.raises(Exception):
        await store.create_program(program)


@pytest.mark.asyncio
async def test_program_dedup_unique(
    store: EntityStore, sample_org: Organization, sample_program: Program
):
    """같은 org + name으로 중복 프로그램 생성 시 에러."""
    from src.core.errors import StoreError

    dup_program = Program(
        id=generate_id("prg_"),
        org_id=sample_org.id,
        normalized_name="speedrun",
        category=ProgramCategory.VC_COHORT,
    )
    with pytest.raises(StoreError):
        await store.create_program(dup_program)


@pytest.mark.asyncio
async def test_get_program_by_org_and_name(
    store: EntityStore, sample_org: Organization, sample_program: Program
):
    """조직 + 이름으로 프로그램 조회."""
    result = await store.get_program_by_org_and_name(sample_org.id, "speedrun")
    assert result is not None
    assert result.id == sample_program.id


@pytest.mark.asyncio
async def test_list_programs_by_category(
    store: EntityStore, sample_org: Organization, sample_program: Program
):
    """카테고리로 프로그램 필터."""
    # Grant 프로그램 추가
    grant = Program(
        id=generate_id("prg_"),
        org_id=sample_org.id,
        normalized_name="crypto grants",
        display_name="a16z Crypto Grants",
        category=ProgramCategory.GRANT,
    )
    await store.create_program(grant)

    vc_programs = await store.list_programs(category=ProgramCategory.VC_COHORT)
    assert any(p.id == sample_program.id for p in vc_programs)

    grant_programs = await store.list_programs(category=ProgramCategory.GRANT)
    assert any(p.id == grant.id for p in grant_programs)


# ============================================================
# Opportunity Tests
# ============================================================


@pytest.mark.asyncio
async def test_create_opportunity_requires_program(store: EntityStore):
    """program_id 없이 기회 생성 시 에러."""
    opp = Opportunity(
        id=generate_id("opp_"),
        program_id="nonexistent_program",
    )
    with pytest.raises(Exception):
        await store.create_opportunity(opp)


@pytest.mark.asyncio
async def test_get_opportunity(store: EntityStore, sample_opportunity: Opportunity):
    """ID로 기회 조회."""
    result = await store.get_opportunity(sample_opportunity.id)
    assert result is not None
    assert result.status == OpportunityStatus.OPEN
    assert result.budget_amount == 500000.0
    assert result.apply_url == "https://speedrun.xyz/apply"


@pytest.mark.asyncio
async def test_update_opportunity(store: EntityStore, sample_opportunity: Opportunity):
    """기회 필드 업데이트 (deadline 변경 시 UPDATE, 새 row 아님)."""
    await store.update_opportunity(
        sample_opportunity.id,
        status=OpportunityStatus.DEADLINE,
        days_left=7,
    )
    result = await store.get_opportunity(sample_opportunity.id)
    assert result is not None
    assert result.status == OpportunityStatus.DEADLINE
    assert result.days_left == 7


@pytest.mark.asyncio
async def test_curated_view_filter(
    store: EntityStore,
    sample_org: Organization,
    sample_program: Program,
    sample_opportunity: Opportunity,
):
    """verified + confidence >= 0.75 + tier <= 2만 반환."""
    # 조건 충족 opp (이미 sample_opportunity가 있음)
    results = await store.list_opportunities_curated(
        company_profile_id=None,
        min_confidence=0.75,
    )
    assert len(results) >= 1
    assert any(r["id"] == sample_opportunity.id for r in results)


@pytest.mark.asyncio
async def test_curated_view_excludes_closed(
    store: EntityStore, sample_program: Program
):
    """status='closed'는 curated view에서 제외."""
    closed_opp = Opportunity(
        id=generate_id("opp_"),
        program_id=sample_program.id,
        status=OpportunityStatus.CLOSED,
        apply_url="https://example.com/apply",
        output_status=OutputStatus.VERIFIED,
        fact_confidence=0.95,
        source_tier=1,
    )
    await store.create_opportunity(closed_opp)

    results = await store.list_opportunities_curated(min_confidence=0.75)
    assert not any(r["id"] == closed_opp.id for r in results)


@pytest.mark.asyncio
async def test_curated_view_excludes_no_apply_url(
    store: EntityStore, sample_program: Program
):
    """apply_url=None은 curated view에서 제외."""
    no_url_opp = Opportunity(
        id=generate_id("opp_"),
        program_id=sample_program.id,
        status=OpportunityStatus.OPEN,
        apply_url=None,
        output_status=OutputStatus.VERIFIED,
        fact_confidence=0.95,
        source_tier=1,
    )
    await store.create_opportunity(no_url_opp)

    results = await store.list_opportunities_curated(min_confidence=0.75)
    assert not any(r["id"] == no_url_opp.id for r in results)


@pytest.mark.asyncio
async def test_count_opportunities(
    store: EntityStore, sample_opportunity: Opportunity
):
    """기회 수 카운트."""
    count = await store.count_opportunities()
    assert count >= 1

    vc_count = await store.count_opportunities(category=ProgramCategory.VC_COHORT)
    assert vc_count >= 1


# ============================================================
# Observation Tests
# ============================================================


@pytest.mark.asyncio
async def test_create_observation(
    store: EntityStore, sample_opportunity: Opportunity
):
    """검증 증거 저장."""
    obs = Observation(
        id=generate_id("obs_"),
        opportunity_id=sample_opportunity.id,
        source_url="https://speedrun.xyz",
        source_tier=1,
        observed_data={"status": "open", "deadline": "2026-06-01"},
        confidence=0.95,
    )
    obs_id = await store.create_observation(obs)
    assert obs_id == obs.id

    observations = await store.list_observations(
        opportunity_id=sample_opportunity.id
    )
    assert len(observations) >= 1
    assert observations[0].source_tier == 1


# ============================================================
# Application Endpoint Tests
# ============================================================


@pytest.mark.asyncio
async def test_endpoint_crud(store: EntityStore, sample_opportunity: Opportunity):
    """엔드포인트 생성 및 활성 목록 조회."""
    ep = ApplicationEndpoint(
        id=generate_id("ep_"),
        opportunity_id=sample_opportunity.id,
        endpoint_type=EndpointType.FORM,
        url="https://speedrun.xyz/apply",
        is_active=True,
    )
    await store.create_endpoint(ep)

    endpoints = await store.get_active_endpoints(sample_opportunity.id)
    assert len(endpoints) >= 1
    assert endpoints[0].endpoint_type == EndpointType.FORM


# ============================================================
# Company Profile Tests
# ============================================================


@pytest.mark.asyncio
async def test_company_profile_crud(store: EntityStore):
    """프로필 생성, 조회, 업데이트."""
    profile = CompanyProfile(
        id="cp_test",
        company_name="Test Corp",
        stage=CompanyStage.MVP,
        sector_tags=["ai", "crypto"],
        projects=[{"name": "TestProject", "priority": 1, "tags": ["ai"]}],
        description="Test company",
        telegram_user_id=12345,
    )
    await store.create_company_profile(profile)

    result = await store.get_company_profile("cp_test")
    assert result is not None
    assert result.company_name == "Test Corp"
    assert result.stage == CompanyStage.MVP
    assert "ai" in result.sector_tags
    assert len(result.projects) == 1

    # Update
    await store.update_company_profile(
        "cp_test",
        stage=CompanyStage.SEED,
        sector_tags=["ai", "crypto", "defi"],
    )
    updated = await store.get_company_profile("cp_test")
    assert updated is not None
    assert updated.stage == CompanyStage.SEED
    assert "defi" in updated.sector_tags


@pytest.mark.asyncio
async def test_profile_by_telegram_user(store: EntityStore):
    """telegram_user_id로 프로필 조회."""
    profile = CompanyProfile(
        id="cp_tg",
        company_name="Telegram User Corp",
        telegram_user_id=99999,
    )
    await store.create_company_profile(profile)

    result = await store.get_profile_by_telegram_user(99999)
    assert result is not None
    assert result.id == "cp_tg"

    # 존재하지 않는 ID
    none_result = await store.get_profile_by_telegram_user(11111)
    assert none_result is None


@pytest.mark.asyncio
async def test_seed_data_load(store: EntityStore, tmp_path: Path):
    """seed JSON 파일로 프로필 로드."""
    seed_data = {
        "id": "cp_seed_test",
        "company_name": "Seed Corp",
        "stage": "idea",
        "sector_tags": ["ai"],
        "projects": [{"name": "SeedProject", "priority": 1, "tags": ["ai"]}],
        "description": "Seed test",
        "telegram_user_id": None,
    }
    seed_path = tmp_path / "seed_profile.json"
    seed_path.write_text(json.dumps(seed_data), encoding="utf-8")

    profile_id = await store.load_seed_profile(seed_path)
    assert profile_id == "cp_seed_test"

    result = await store.get_company_profile("cp_seed_test")
    assert result is not None
    assert result.company_name == "Seed Corp"

    # 중복 로드 시 기존 반환
    dup_id = await store.load_seed_profile(seed_path)
    assert dup_id == "cp_seed_test"


# ============================================================
# Utility Function Tests
# ============================================================


def test_normalize_org_name():
    """조직명 정규화."""
    assert normalize_org_name("Ethereum Foundation") == "ethereum"
    assert normalize_org_name("  Polygon Labs  ") == "polygon"
    assert normalize_org_name("a16z Crypto") == "a16z crypto"
    assert normalize_org_name("MakerDAO") == "makerdao"  # no space before suffix


def test_normalize_url():
    """URL 정규화."""
    assert normalize_url("http://example.com/apply/") == "https://example.com/apply"
    assert normalize_url("https://a16z.com/grants?ref=x#top") == "https://a16z.com/grants"


def test_generate_id():
    """ID 생성 형식 확인."""
    org_id = generate_id("org_")
    assert org_id.startswith("org_")
    assert len(org_id) == 16  # "org_" + 12 hex chars

    plain_id = generate_id()
    assert len(plain_id) == 12
