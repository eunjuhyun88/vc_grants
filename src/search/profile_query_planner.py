"""
Funding Intelligence Agent — ProfileQueryPlanner.

CompanyProfile의 sector_tags, target_ecosystems, stage를 분석해서
웹/소셜 검색에 쓸 쿼리를 자동 생성한다.

LLM 호출 없음. TAG_KEYWORDS 매핑 테이블 기반 deterministic 생성.
"""

from __future__ import annotations

from src.core.types import CompanyProfile


# ============================================================
# TAG → KEYWORD 매핑 (설계 문서 기준)
# ============================================================

TAG_KEYWORDS: dict[str, list[str]] = {
    "ai_infra": ["AI infrastructure", "AI infra"],
    "decentralized_ai": ["decentralized AI", "distributed AI"],
    "crypto_infra": ["crypto infrastructure", "blockchain infra", "web3", "blockchain"],
    "distributed_compute": ["distributed compute", "GPU network", "compute network"],
    "personal_model_training": ["AI model training", "personal AI"],
    "agent_infra": ["AI agent infrastructure", "agent framework"],
    "small_model_training": ["small language model", "SLM training"],
    "torrent_coordination": ["peer-to-peer coordination", "distributed coordination"],
    "blockchain_compute": ["blockchain compute", "onchain compute"],
    "crypto_analytics": ["crypto analytics", "blockchain analytics"],
    "trading_infra": ["trading infrastructure", "DeFi trading"],
    "ai_evaluation": ["AI evaluation", "AI benchmark"],
    "ai_benchmark": ["AI benchmark", "model evaluation"],
    "ai_content": ["AI content", "AI creative"],
    "creator_economy": ["creator economy", "creator tools"],
    "physical_ai": ["physical AI", "robotics AI"],
    "desci": ["DeSci", "decentralized science"],
    "defi": ["DeFi", "decentralized finance"],
    "nft": ["NFT", "digital collectibles"],
    "gaming": ["blockchain gaming", "web3 gaming"],
    "social": ["social protocol", "decentralized social"],
    "dao": ["DAO", "decentralized governance"],
    "zk": ["zero knowledge", "ZK proofs"],
    "privacy": ["privacy protocol", "confidential computing"],
    "layer2": ["layer 2", "L2 scaling"],
    "depin": ["DePIN", "decentralized physical infrastructure"],
}

RELATED_ECOSYSTEMS_BY_TAG: dict[str, list[str]] = {
    "ai_infra": ["ethereum", "near", "bittensor", "monad", "chainlink"],
    "decentralized_ai": ["bittensor", "near", "ethereum", "solana"],
    "crypto_infra": ["ethereum", "solana", "arbitrum", "base", "monad", "chainlink"],
    "distributed_compute": ["bittensor", "near", "avalanche", "monad"],
    "agent_infra": ["near", "ethereum", "base", "chainlink"],
}

# ============================================================
# 유사 프로젝트 (경쟁사 추적용)
# ============================================================

SIMILAR_PROJECTS: dict[str, list[str]] = {
    "ai_infra": ["bittensor", "prime intellect", "nous research", "modulus labs", "gensyn"],
    "decentralized_ai": ["bittensor", "ritual", "ora protocol", "vana"],
    "distributed_compute": ["gensyn", "akash", "render network", "io.net"],
    "crypto_infra": ["alchemy", "infura", "ankr", "pocket network"],
    "depin": ["helium", "filecoin", "theta network", "hivemapper"],
}


# ============================================================
# 쿼리 생성
# ============================================================

def generate_queries(profile: CompanyProfile) -> list[str]:
    """프로필 기반 검색 쿼리 생성.

    4개 축:
    1. sector + funding type 조합
    2. target ecosystem + grant/accelerator
    3. 새로운 VC+Ecosystem 코호트 발견
    4. 경쟁사/유사 프로젝트 기반 발견

    Returns:
        최대 20개 쿼리 (중복 제거 후)
    """
    queries: list[str] = []
    ecosystems = get_priority_ecosystems(profile)

    # ── 축 1: sector + funding type ──
    sector_keywords = _get_sector_keywords(profile.sector_tags)
    for kw in sector_keywords[:3]:
        queries.append(f"{kw} grant program apply 2026")
        queries.append(f"{kw} accelerator cohort open application")
        queries.append(f"{kw} ecosystem builder program funding")

    # ── 축 2: target ecosystem + grant/accelerator ──
    for eco in ecosystems[:6]:
        queries.append(f"{eco} ecosystem grants funding program 2026")
        queries.append(f"{eco} accelerator builder program apply")
        queries.append(f"{eco} official builder program apply 2026")

    # ── 축 2.5: ecosystem + thesis 맞춤 ──
    for eco in ecosystems[:4]:
        for kw in sector_keywords[:2]:
            queries.append(f"{eco} {kw} funding program")
            queries.append(f"{eco} {kw} accelerator apply 2026")

    # ── 축 3: 새로운 VC+Ecosystem 코호트 발견 (핵심) ──
    queries.extend([
        "crypto VC accelerator cohort 2026 apply",
        "web3 startup accelerator seed investment cohort",
        "blockchain founder residency program apply",
        "crypto ecosystem accelerator demo day 2026",
        "new web3 accelerator program launch apply",
        "VC backed crypto builder cohort application",
        "AI web3 accelerator seed funding open",
        "crypto infra founder program investment 2026",
        "ecosystem backed crypto cohort apply 2026",
        "builder program seed investment official apply",
    ])

    # ── 축 4: 경쟁사/유사 프로젝트 기반 발견 ──
    similar = _get_similar_projects(profile.sector_tags)
    for proj in similar[:3]:
        queries.append(f"{proj} funding grant received")
        queries.append(f"{proj} accelerator program joined")

    # dedup + limit
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        q_lower = q.lower().strip()
        if q_lower not in seen:
            seen.add(q_lower)
            unique.append(q)

    return unique[:20]


def generate_social_queries(profile: CompanyProfile) -> list[str]:
    """소셜 검색(LunarCrush)용 쿼리 생성.

    웹 검색보다 짧고 키워드 위주.
    """
    queries: list[str] = []
    ecosystems = get_priority_ecosystems(profile)

    # ecosystem별 펀딩 관련
    for eco in ecosystems[:6]:
        queries.append(f"{eco} grants")
        queries.append(f"{eco} accelerator")
        queries.append(f"{eco} builder program")

    # 일반 펀딩 키워드
    queries.extend([
        "crypto accelerator apply",
        "web3 grants program open",
        "blockchain funding round seed",
        "AI crypto accelerator cohort",
    ])

    # dedup
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        q_lower = q.lower().strip()
        if q_lower not in seen:
            seen.add(q_lower)
            unique.append(q)

    return unique[:15]


def generate_social_watch_terms(profile: CompanyProfile) -> list[str]:
    """VC/L1/L2 계정 watchlist 기반 소셜 탐색에 쓸 신호 용어 생성.

    일반 social query보다 더 짧고, 계정 타게팅 쿼리에 섞을 키워드만 남긴다.
    """
    terms: list[str] = []
    ecosystems = get_priority_ecosystems(profile)
    sector_keywords = _get_sector_keywords([
        *profile.sector_tags,
        *profile.subsector_tags,
    ])

    for ecosystem in ecosystems[:4]:
        terms.append(f"{ecosystem} grant")
        terms.append(f"{ecosystem} funding")
        terms.append(f"{ecosystem} accelerator")

    for keyword in sector_keywords[:3]:
        terms.append(f"{keyword} grant")
        terms.append(f"{keyword} accelerator")
        terms.append(f"{keyword} investment")

    terms.extend([
        "applications open",
        "cohort",
        "builder program",
        "ecosystem fund",
        "seed investment",
        "backed",
    ])

    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        key = term.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        unique.append(term)

    return unique[:18]


def get_matching_keywords(profile: CompanyProfile) -> list[str]:
    """참조 데이터 매칭용 키워드 리스트 반환.

    sector_tags 원본 + TAG_KEYWORDS 매핑의 자연어 + target_ecosystems
    + funding_goal에 따른 discovery intent keywords.
    """
    keywords: list[str] = []

    for tag in profile.sector_tags:
        keywords.append(tag)
        keywords.extend(TAG_KEYWORDS.get(tag, []))

    for tag in profile.subsector_tags:
        keywords.append(tag)
        keywords.extend(TAG_KEYWORDS.get(tag, []))

    keywords.extend(get_priority_ecosystems(profile))

    funding_goal = (profile.funding_goal or "").lower()
    if "grant" in funding_goal:
        keywords.extend(["grant", "grants", "funding"])
    if "accelerator" in funding_goal:
        keywords.extend(["accelerator", "cohort", "incubator", "builder program"])
    if "seed_vc" in funding_goal or "seed vc" in funding_goal or "vc" in funding_goal:
        keywords.extend(["vc", "venture", "seed investment", "vc cohort"])

    # dedup preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower not in seen:
            seen.add(kw_lower)
            unique.append(kw)

    return unique


# ============================================================
# Internal helpers
# ============================================================

def _get_sector_keywords(sector_tags: list[str]) -> list[str]:
    """sector_tags → 검색용 자연어 키워드 추출."""
    keywords: list[str] = []
    for tag in sector_tags:
        mapped = TAG_KEYWORDS.get(tag, [])
        if mapped:
            keywords.append(mapped[0])  # 첫 번째 매핑만 사용
        else:
            # 매핑이 없으면 tag 자체를 사용 (underscore → space)
            keywords.append(tag.replace("_", " "))
    return keywords


def get_priority_ecosystems(profile: CompanyProfile) -> list[str]:
    """프로필 target_ecosystems + sector 기반 관련 ecosystem 확장."""
    ecosystems: list[str] = list(profile.target_ecosystems or [])
    seen = {eco.lower() for eco in ecosystems}

    for tag in [*profile.sector_tags, *profile.subsector_tags]:
        for eco in RELATED_ECOSYSTEMS_BY_TAG.get(tag, []):
            if eco.lower() in seen:
                continue
            seen.add(eco.lower())
            ecosystems.append(eco)

    return ecosystems


def _get_similar_projects(sector_tags: list[str]) -> list[str]:
    """sector_tags → 유사 프로젝트 리스트."""
    projects: list[str] = []
    seen: set[str] = set()
    for tag in sector_tags:
        for proj in SIMILAR_PROJECTS.get(tag, []):
            if proj.lower() not in seen:
                seen.add(proj.lower())
                projects.append(proj)
    return projects[:5]
