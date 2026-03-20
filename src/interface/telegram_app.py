"""
Funding Intelligence Agent — Telegram Application.

Application 초기화 + 라우터.
실행: python -m src.interface.telegram_app
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import structlog
from telegram.ext import Application, CommandHandler, MessageHandler, filters

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
    reset_profile_command,
    setup_hoot_command,
    start_command,
)
from src.interface.handlers.funding_handler import discover_command, funding_command
from src.interface.handlers.research_handler import (
    funding_for_project_command,
    funding_map_command,
    org_command,
)
from src.interface.handlers.ranking_handler import ranking_command
from src.interface.handlers.search_handler import search_command
from src.interface.handlers.chat_handler import chat_handler
from src.interface.social_alert_dispatcher import run_social_alert_dispatch_loop

logger = structlog.get_logger()

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


class SingleInstanceLock:
    """Prevent concurrent Telegram polling processes in the same worktree."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = open(self.path, "w", encoding="utf-8")
        if fcntl is not None:
            try:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError(
                    f"[TELEGRAM_INSTANCE_CONFLICT] another Telegram polling instance is already active: {self.path}"
                ) from exc
        self._handle.seek(0)
        self._handle.truncate()
        self._handle.write(str(os.getpid()))
        self._handle.flush()

    def release(self) -> None:
        if self._handle is None:
            return
        if fcntl is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


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
    app.add_handler(CommandHandler("setup_hoot", setup_hoot_command))
    app.add_handler(CommandHandler("reset_profile", reset_profile_command))

    # 리스트 커맨드 (LLM 없음)
    app.add_handler(CommandHandler("grants", grants_command))
    app.add_handler(CommandHandler("cohorts", cohorts_command))
    app.add_handler(CommandHandler("funds", funds_command))
    app.add_handler(CommandHandler("all", all_command))

    # 랭킹 (Matching Agent 사용)
    app.add_handler(CommandHandler("ranking", ranking_command))

    # 라이브 검색 (Discovery → Ingest → Verify → Match)
    app.add_handler(CommandHandler("search", search_command))

    # 프로필 기반 즉시 펀딩 추천 (참조 데이터)
    app.add_handler(CommandHandler("funding", funding_command))
    app.add_handler(CommandHandler("funding_for_project", funding_for_project_command))
    app.add_handler(CommandHandler("funding_map", funding_map_command))
    app.add_handler(CommandHandler("org", org_command))

    # 웹 심층 탐색 (Discovery Loop)
    app.add_handler(CommandHandler("discover", discover_command))

    # 자연어 대화 핸들러 (catch-all, 슬래시 커맨드 아닌 모든 텍스트)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))

    logger.info("telegram.handlers_registered")
    return app


async def run_bot() -> None:
    """봇 실행."""
    db_path = config.db_path
    lock = SingleInstanceLock(Path(db_path).parent / ".telegram-bot.lock")
    lock.acquire()
    social_alert_task: asyncio.Task | None = None
    try:
        async with EntityStore(db_path) as store:
            await store.init_schema()
            app = create_app(store)

            logger.info("telegram.starting", db=str(db_path))
            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=False)
            social_alert_task = asyncio.create_task(
                run_social_alert_dispatch_loop(
                    bot=app.bot,
                    store=store,
                    poll_seconds=config.social_alert_poll_seconds,
                    batch_size=config.social_alert_batch_size,
                )
            )

            logger.info("telegram.running")

            # Ctrl+C까지 대기
            try:
                while True:
                    await asyncio.sleep(3600)
            except (KeyboardInterrupt, SystemExit):
                logger.info("telegram.stopping")
            finally:
                if social_alert_task is not None:
                    social_alert_task.cancel()
                    try:
                        await social_alert_task
                    except asyncio.CancelledError:
                        pass
                await app.updater.stop()
                await app.stop()
                await app.shutdown()
    finally:
        lock.release()


if __name__ == "__main__":
    asyncio.run(run_bot())
