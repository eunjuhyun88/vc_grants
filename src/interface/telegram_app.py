"""
Funding Intelligence Agent — Telegram Application.

Application 초기화 + 라우터.
실행: python -m src.interface.telegram_app
"""

from __future__ import annotations

import asyncio
import sys

import structlog
from telegram.ext import Application, CommandHandler

from src.core.config import config
from src.db.entity_store import EntityStore
from src.interface.handlers.list_handler import (
    all_command,
    cohorts_command,
    funds_command,
    grants_command,
)
from src.interface.handlers.profile_handler import (
    get_registration_handler,
    profile_command,
    start_command,
)
from src.interface.handlers.ranking_handler import ranking_command

logger = structlog.get_logger()


def create_app(store: EntityStore) -> Application:
    """Telegram Application 생성 + 핸들러 등록."""
    if not config.telegram_token:
        logger.error("telegram.no_token")
        raise RuntimeError(
            "[TELEGRAM_NO_TOKEN] TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.\n"
            "수정: .env 파일에 TELEGRAM_BOT_TOKEN=your_token 추가\n"
            "예시: TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ"
        )

    app = Application.builder().token(config.telegram_token).build()

    # bot_data에 store 주입
    app.bot_data["store"] = store

    # 프로필 관련 (ConversationHandler 우선 등록)
    app.add_handler(get_registration_handler())
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("profile", profile_command))

    # 리스트 커맨드 (LLM 없음)
    app.add_handler(CommandHandler("grants", grants_command))
    app.add_handler(CommandHandler("cohorts", cohorts_command))
    app.add_handler(CommandHandler("funds", funds_command))
    app.add_handler(CommandHandler("all", all_command))

    # 랭킹 (Matching Agent 사용)
    app.add_handler(CommandHandler("ranking", ranking_command))

    logger.info("telegram.handlers_registered")
    return app


async def run_bot() -> None:
    """봇 실행."""
    db_path = config.db_path
    async with EntityStore(db_path) as store:
        await store.init_schema()
        app = create_app(store)

        logger.info("telegram.starting", db=str(db_path))
        await app.initialize()
        await app.start()
        await app.updater.start_polling()

        logger.info("telegram.running")

        # Ctrl+C까지 대기
        try:
            while True:
                await asyncio.sleep(3600)
        except (KeyboardInterrupt, SystemExit):
            logger.info("telegram.stopping")
        finally:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()


if __name__ == "__main__":
    asyncio.run(run_bot())
