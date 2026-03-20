"""
Funding Intelligence Agent — 설정.

.env 파일에서 환경변수 로드 → Config 객체로 관리.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _parse_csv_keys(env_var: str) -> list[str]:
    """Comma-separated env var → list of non-empty strings."""
    raw = os.getenv(env_var, "")
    return [k.strip() for k in raw.split(",") if k.strip()] if raw else []


@dataclass
class Config:
    db_path: Path = Path(os.getenv("DB_PATH", "data/funding.db"))
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    # LLM 설정 — Groq primary, Gemini/Anthropic fallback
    groq_key: str = os.getenv("GROQ_API_KEY", "")
    groq_keys: list[str] = None  # type: ignore[assignment]  # populated in __post_init__
    gemini_key: str = os.getenv("GEMINI_API_KEY", "")
    anthropic_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    llm_provider: str = os.getenv("LLM_PROVIDER", "groq")  # groq | gemini | anthropic
    llm_model: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    llm_model_fast: str = os.getenv("LLM_MODEL_FAST", "llama-3.1-8b-instant")
    # Hugging Face
    hf_token: str = os.getenv("HF_TOKEN", "")
    hf_tokens: list[str] = None  # type: ignore[assignment]  # populated in __post_init__
    # 검색 설정 — 3엔진 병렬 (Tavily + Serper + Brave), DDG 폴백
    search_provider: str = os.getenv("SEARCH_PROVIDER", "multi")  # multi | duckduckgo
    tavily_key: str = os.getenv("TAVILY_API_KEY", "")
    serper_key: str = os.getenv("SERPER_API_KEY", "")
    serper_keys: list[str] = None  # type: ignore[assignment]  # populated in __post_init__
    brave_key: str = os.getenv("BRAVE_API_KEY", "")
    lunarcrush_key: str = os.getenv("LUNARCRUSH_API_KEY", "")
    social_watchlist_path: Path = Path(
        os.getenv("SOCIAL_WATCHLIST_PATH", "data/curated_social_accounts.json")
    )
    discovered_social_accounts_path: Path = Path(
        os.getenv("DISCOVERED_SOCIAL_ACCOUNTS_PATH", "data/discovered_social_accounts.json")
    )
    social_reference_seed_path: Path = Path(
        os.getenv("SOCIAL_REFERENCE_SEED_PATH", "data/seed_raw.json")
    )
    social_vc_registry_csv_path: Path = Path(
        os.getenv("SOCIAL_VC_REGISTRY_CSV_PATH", "output/spreadsheet/vc_list_final.csv")
    )
    social_watchlist_limit: int = int(os.getenv("SOCIAL_WATCHLIST_LIMIT", "10"))
    social_watch_terms_per_account: int = int(
        os.getenv("SOCIAL_WATCH_TERMS_PER_ACCOUNT", "3")
    )
    social_reference_watch_limit: int = int(
        os.getenv("SOCIAL_REFERENCE_WATCH_LIMIT", "120")
    )
    social_alert_poll_seconds: int = int(
        os.getenv("SOCIAL_ALERT_POLL_SECONDS", "300")
    )
    social_alert_batch_size: int = int(
        os.getenv("SOCIAL_ALERT_BATCH_SIZE", "5")
    )
    # 페이지 수집 — Jina Reader (JS 렌더링), httpx 폴백
    jina_key: str = os.getenv("JINA_API_KEY", "")
    # Crypto Data APIs
    coingecko_key: str = os.getenv("COINGECKO_API_KEY", "")
    rootdata_key: str = os.getenv("ROOTDATA_API_KEY", "")
    cryptorank_key: str = os.getenv("CRYPTORANK_API_KEY", "")
    # LLM Strong 모델 (종합 분석용)
    llm_model_strong: str = os.getenv(
        "LLM_MODEL_STRONG", "llama-3.3-70b-versatile"
    )
    # Agentic RAG 설정
    search_max_rounds: int = int(os.getenv("SEARCH_MAX_ROUNDS", "3"))
    search_max_pages: int = int(os.getenv("SEARCH_MAX_PAGES", "10"))
    # Discovery loop 설정 (autoresearch 패턴) — 공격적 탐색
    discovery_max_rounds: int = int(os.getenv("DISCOVERY_MAX_ROUNDS", "15"))
    discovery_stall_threshold: int = int(os.getenv("DISCOVERY_STALL_THRESHOLD", "3"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    def __post_init__(self) -> None:
        # Parse comma-separated rotation keys
        object.__setattr__(self, "groq_keys", _parse_csv_keys("GROQ_API_KEYS"))
        object.__setattr__(self, "hf_tokens", _parse_csv_keys("HF_TOKENS"))
        object.__setattr__(self, "serper_keys", _parse_csv_keys("SERPER_API_KEYS"))


config = Config()
