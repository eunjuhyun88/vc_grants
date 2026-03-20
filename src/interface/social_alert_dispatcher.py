"""
Funding Intelligence Agent — Social Alert Dispatcher.

verified social monitoring candidates를 Telegram DM으로 전송하고
성공한 event는 notified 처리한다.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from telegram import Bot

from src.db.entity_store import EntityStore
from src.interface.card_renderer import render_social_alert_candidate

logger = structlog.get_logger()


async def dispatch_pending_social_alerts(
    bot: Bot,
    store: EntityStore,
    limit: int = 5,
) -> dict[str, Any]:
    """pending social alerts를 등록된 Telegram 사용자에게 전송."""
    recipients = await store.list_telegram_recipient_ids()
    if not recipients:
        return {
            "checked": 0,
            "sent": 0,
            "notified": 0,
            "recipients": 0,
            "errors": [],
        }

    candidates = await store.list_social_alert_candidates(limit=limit)
    if not candidates:
        return {
            "checked": 0,
            "sent": 0,
            "notified": 0,
            "recipients": len(recipients),
            "errors": [],
        }

    sent_count = 0
    notified_ids: list[str] = []
    errors: list[dict[str, Any]] = []

    for candidate in candidates:
        text = render_social_alert_candidate(candidate)
        event_id = str(candidate["event_id"])
        delivered = False

        for chat_id in recipients:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="MarkdownV2",
                    disable_web_page_preview=True,
                )
                delivered = True
                sent_count += 1
            except Exception as exc:  # pragma: no cover - network/runtime failures
                logger.warning(
                    "social_alert_dispatch.send_failed",
                    chat_id=chat_id,
                    event_id=event_id,
                    error=str(exc),
                )
                errors.append(
                    {
                        "chat_id": chat_id,
                        "event_id": event_id,
                        "error": str(exc),
                    }
                )

        if delivered:
            notified_ids.append(event_id)

    await store.mark_social_alerts_notified(notified_ids)

    logger.info(
        "social_alert_dispatch.complete",
        checked=len(candidates),
        recipients=len(recipients),
        sent=sent_count,
        notified=len(notified_ids),
        errors=len(errors),
    )
    return {
        "checked": len(candidates),
        "sent": sent_count,
        "notified": len(notified_ids),
        "recipients": len(recipients),
        "errors": errors,
    }


async def run_social_alert_dispatch_loop(
    bot: Bot,
    store: EntityStore,
    poll_seconds: int = 300,
    batch_size: int = 5,
) -> None:
    """background loop로 pending social alerts를 주기적으로 전송."""
    logger.info(
        "social_alert_dispatch.loop_start",
        poll_seconds=poll_seconds,
        batch_size=batch_size,
    )
    try:
        while True:
            try:
                await dispatch_pending_social_alerts(
                    bot=bot,
                    store=store,
                    limit=batch_size,
                )
            except Exception as exc:  # pragma: no cover - runtime loop guard
                logger.warning(
                    "social_alert_dispatch.loop_iteration_failed",
                    error=str(exc),
                )
            await asyncio.sleep(max(30, poll_seconds))
    except asyncio.CancelledError:  # pragma: no cover - shutdown path
        logger.info("social_alert_dispatch.loop_stop")
        raise
