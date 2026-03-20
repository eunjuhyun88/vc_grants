"""
Funding Intelligence Agent — Ranking Handler.

/ranking [intent] — 개인화된 기회 순위.
Intent: default, urgent, highest_money, best_ecosystem_match
"""

from __future__ import annotations

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from src.agents.matching import MatchingAgent
from src.core.config import config
from src.core.types import RankingIntent
from src.db.entity_store import EntityStore
from src.interface.card_renderer import (
    escape_md,
    render_error,
    render_ranked_list,
)
from src.interface.opportunity_filters import filter_current_cards

logger = structlog.get_logger()

INTENT_TITLES: dict[str, str] = {
    "default": "⭐ 추천 순위",
    "urgent": "🔥 긴급 마감순",
    "biggest_check": "💰 최대 펀딩순",
    "ready_now": "🎯 즉시 지원 가능",
    "best_fit": "🎯 최고 적합도순",
}


async def ranking_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/ranking [intent] — 개인화된 순위."""
    store: EntityStore = context.bot_data["store"]

    # intent 파싱
    args = context.args or []
    intent_str = args[0].lower() if args else "default"

    # 유효한 intent인지 확인
    valid_intents = {"default", "urgent", "biggest_check", "ready_now", "best_fit"}
    if intent_str not in valid_intents:
        usage = escape_md(
            "사용법: /ranking [default|urgent|biggest_check|ready_now|best_fit]"
        )
        await update.message.reply_text(usage, parse_mode="MarkdownV2")
        return

    # 사용자 프로필 조회
    user_id = update.effective_user.id
    profile = await store.get_profile_by_telegram_user(user_id)

    if profile is None:
        await update.message.reply_text(
            escape_md("프로필을 먼저 등록하세요: /register"),
            parse_mode="MarkdownV2",
        )
        return

    try:
        # curated view에서 기회 목록 가져오기
        rows = await store.list_opportunities_curated(
            company_profile_id=profile.id,
            min_confidence=0.75,
        )

        if not rows:
            await update.message.reply_text(
                escape_md("현재 매칭 가능한 기회가 없습니다."),
                parse_mode="MarkdownV2",
            )
            return

        # Matching Agent로 batch ranking
        agent = MatchingAgent(store=store, config=config)
        opp_ids = [r["id"] for r in rows]

        ranked = await agent.batch_rank(
            opportunity_ids=opp_ids,
            profile_id=profile.id,
            intent=intent_str,
            top_n=10,
        )

        if not ranked:
            await update.message.reply_text(
                escape_md("매칭 결과가 없습니다."),
                parse_mode="MarkdownV2",
            )
            return

        # MatchingOutput → OpportunityCard 변환
        from src.core.types import OpportunityCard

        cards: list[OpportunityCard] = []
        for mo in ranked:
            opp = await store.get_opportunity(mo.opportunity_id)
            if opp is None:
                continue

            program = await store.get_program(opp.program_id)
            org_name = "Unknown"
            prog_name = "Unknown"
            if program:
                prog_name = program.display_name or program.normalized_name
                org = await store.get_organization(program.org_id)
                if org:
                    org_name = org.display_name or org.normalized_name

            card = OpportunityCard(
                organization=org_name,
                program=prog_name,
                category=program.category.value if program else "unknown",
                status=opp.status.value,
                apply_url=opp.apply_url or "",
                confidence=opp.fact_confidence,
                deadline=opp.deadline_at.isoformat()[:10] if opp.deadline_at else None,
                days_left=opp.days_left,
                budget=opp.budget_note,
                fit_score=mo.fit_score,
                priority_score=mo.priority_score,
                why_fit=mo.why_fit,
                next_action=mo.next_action,
            )
            cards.append(card)

        cards = filter_current_cards(cards)
        if not cards:
            await update.message.reply_text(
                escape_md("현재 지원 가능한 기회가 없습니다."),
                parse_mode="MarkdownV2",
            )
            return

        title = INTENT_TITLES.get(intent_str, "⭐ 추천 순위")
        text = render_ranked_list(cards, title=title)

        await update.message.reply_text(
            text,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
        )

    except Exception as e:
        logger.error("ranking_handler.error", error=str(e))
        await update.message.reply_text(
            render_error(),
            parse_mode="MarkdownV2",
        )
