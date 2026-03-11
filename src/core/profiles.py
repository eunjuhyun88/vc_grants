"""
Funding Intelligence Agent — 기본 프로필 하드코딩.

DB 등록 전에도 /funding 커맨드가 동작하도록 기본 프로필을 제공한다.
"""

from __future__ import annotations

from src.core.types import CompanyProfile, CompanyStage


# ============================================================
# 기본 프로필
# ============================================================

HOOT_PROFILE = CompanyProfile(
    id="hoot-default",
    company_name="Holo Studio Co., Ltd.",
    stage=CompanyStage.MVP,
    sector_tags=[
        "ai_infra",
        "decentralized_ai",
        "crypto_infra",
        "distributed_compute",
        "personal_model_training",
    ],
    subsector_tags=[
        "agent_infra",
        "small_model_training",
        "torrent_coordination",
        "blockchain_compute",
    ],
    geography="global",
    funding_goal="grant,accelerator,seed_vc",
    product_summary=(
        "Personal data-driven small model training "
        "+ distributed computing + blockchain coordination"
    ),
    target_ecosystems=[
        "ethereum", "near", "solana", "arbitrum",
        "monad", "bittensor", "base",
    ],
    projects=[
        {"name": "HOOT", "tags": ["ai_infra", "distributed_compute"], "priority": 1},
        {"name": "StockClaw", "tags": ["crypto_analytics", "trading_infra"], "priority": 2},
        {"name": "MoltVC", "tags": ["ai_evaluation", "ai_benchmark"], "priority": 3},
        {"name": "PlayArts", "tags": ["ai_content", "creator_economy"], "priority": 4},
        {"name": "ClawGene", "tags": ["physical_ai", "desci"], "priority": 5},
    ],
)


DEFAULT_PROFILES: dict[str, CompanyProfile] = {
    "HOOT": HOOT_PROFILE,
    "hoot": HOOT_PROFILE,
}


def get_default_profile(name: str) -> CompanyProfile | None:
    """이름으로 기본 프로필 조회. 대소문자 무시."""
    return DEFAULT_PROFILES.get(name) or DEFAULT_PROFILES.get(name.upper())
