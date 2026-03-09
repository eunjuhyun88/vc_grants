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
    anthropic_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    tavily_key: str = os.getenv("TAVILY_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
    llm_model_fast: str = os.getenv("LLM_MODEL_FAST", "claude-haiku-4-20250414")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


config = Config()
