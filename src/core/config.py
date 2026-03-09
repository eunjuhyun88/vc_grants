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


@dataclass(frozen=True)
class Config:
    db_path: Path = Path(os.getenv("DB_PATH", "data/funding.db"))
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    # LLM 설정 (Groq 우선, Anthropic 폴백)
    groq_key: str = os.getenv("GROQ_API_KEY", "")
    anthropic_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    llm_provider: str = os.getenv("LLM_PROVIDER", "groq")  # groq | anthropic
    llm_model: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    llm_model_fast: str = os.getenv("LLM_MODEL_FAST", "llama-3.1-8b-instant")
    # 검색 설정 (DuckDuckGo 기본, Tavily 폴백)
    search_provider: str = os.getenv("SEARCH_PROVIDER", "duckduckgo")  # duckduckgo | tavily
    tavily_key: str = os.getenv("TAVILY_API_KEY", "")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


config = Config()
