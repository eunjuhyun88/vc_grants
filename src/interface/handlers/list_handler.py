"""
Funding Intelligence Agent — List Command Handlers.

/grants, /cohorts, /funds, /all
LLM 호출 없음 — DB 조회 + card_renderer만 사용.
"""

from __future__ import annotations

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from src.core.types import OpportunityCard, ProgramCategory
from src.db.entity_store import EntityStore
from src.interface.card_renderer import render_empty, render_error, render_ranked_list

logger = structlog.get_logger()


def _opportunities_to_cards(rows: list[dict]) -> list[OpportunityCard]:
    """DB curated view rows → OpportunityCard 리스트."""
    cards: list[OpportunityCard] = []
    for row in rows:
        card = OpportunityCard(
            organization=row.get("org_name", "Unknown"),
            program=row.get("program_name", "Unknown"),
            category=row.get("category", "unknown"),
            status=row.get("status", "unknown"),
            apply_url=row.get("apply_url", ""),
            confidence=row.get("fact_confidence", 0.0),
            deadline=row.get("deadline_at"),
            days_left=row.get("days_left"),
            budget=row.get("budget_note"),
            fit_score=row.get("fit_score"),
            priority_score=row.get("priority_score"),
            why_fit=row.get("why_fit"),
            next_action=row.get("next_action"),
        )
        cards.append(card)
    return cards


async def _handle_list_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    category: ProgramCategory | None = None,
    title: str = "펀딩 기회 목록",
) -> None:
    """공통 리스트 커맨드 처리."""
    store: EntityStore = context.bot_data["store"]

    try:
        # Curated view 조회
        rows = await store.list_opportunities_curated(
            company_profile_id=None,
            min_confidence=0.75,
            category=category,
        )

        cards = _opportunities_to_cards(rows)

        if not cards:
            cat_str = category.value if category else None
            text = render_empty(cat_str)
        else:
            text = render_ranked_list(cards, title=title)

        await update.message.reply_text(
            text,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error("list_handler.error", error=str(e))
        await update.message.reply_text(
            render_error(),
            parse_mode="MarkdownV2",
        )


async def grants_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/grants — Grant 프로그램 목록."""
    await _handle_list_command(
        update, context,
        category=ProgramCategory.GRANT,
        title="💰 Grant 프로그램",
    )


async def cohorts_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/cohorts — VC Cohort 목록."""
    await _handle_list_command(
        update, context,
        category=ProgramCategory.VC_COHORT,
        title="🏦 VC Cohort 프로그램",
    )


async def funds_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/funds — Accelerator 목록."""
    await _handle_list_command(
        update, context,
        category=ProgramCategory.ACCELERATOR,
        title="🚀 Accelerator 프로그램",
    )


async def all_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/all — 전체 기회 목록 (confidence 0.80 이상)."""
    store: EntityStore = context.bot_data["store"]

    try:
        rows = await store.list_opportunities_curated(
            company_profile_id=None,
            min_confidence=0.80,  # /all은 더 높은 기준
        )
        cards = _opportunities_to_cards(rows)

        if not cards:
            text = render_empty()
        else:
            text = render_ranked_list(cards, title="⭐ 전체 펀딩 기회 (Top)")

        await update.message.reply_text(
            text,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error("all_handler.error", error=str(e))
        await update.message.reply_text(
            render_error(),
            parse_mode="MarkdownV2",
        )
