from __future__ import annotations

import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from src.agents.matching import MatchingAgent
from src.core.config import Config, config
from src.core.pipeline import FundingPipeline, PipelineResult
from src.core.types import OpportunityCard, ProgramCategory
from src.db.entity_store import EntityStore
from src.interface.card_renderer import escape_md, render_ranked_list
from src.interface.opportunity_filters import filter_current_cards

logger = structlog.get_logger()
URL_PATTERN = re.compile(r"https?://[^\s<>()]+")


@dataclass
class DiscoveryExecution:
    result: PipelineResult
    elapsed_seconds: float
    status_message: Any


def build_source_query_hint(text: str) -> str:
    """붙여준 링크 주변 문맥을 짧은 query hint로 축약."""
    cleaned = URL_PATTERN.sub(" ", text or "")
    cleaned = " ".join(cleaned.split())
    return cleaned[:120] or "user supplied funding leads"


async def run_discovery_with_status(
    update: Update,
    store: EntityStore,
    *,
    query: str,
    category: ProgramCategory | None = None,
    company_profile_id: str | None = None,
    source_urls: Sequence[str] | None = None,
    hint_queries: Sequence[str] | None = None,
    start_text: str,
    success_text_builder: Callable[[PipelineResult, float], str],
    error_prefix: str,
    cfg: Config | None = None,
) -> DiscoveryExecution | None:
    """Run the discovery pipeline behind a common Telegram status flow."""
    status_message = await update.message.reply_text(
        escape_md(start_text),
        parse_mode="MarkdownV2",
    )

    start = time.monotonic()
    try:
        pipeline = FundingPipeline(store=store, cfg=cfg or config)
        result = await pipeline.run_discovery_pipeline(
            query=query,
            category=category,
            company_profile_id=company_profile_id,
            sources=list(source_urls or []),
            hint_queries=list(hint_queries or []),
        )
    except Exception as exc:
        logger.error(
            "discovery_runtime.run.error",
            query=query,
            category=category.value if category else None,
            error=str(exc),
        )
        await status_message.edit_text(
            escape_md(f"⚠️ {error_prefix}: {str(exc)[:100]}"),
            parse_mode="MarkdownV2",
        )
        return None

    elapsed = time.monotonic() - start
    await status_message.edit_text(
        escape_md(success_text_builder(result, elapsed)),
        parse_mode="MarkdownV2",
    )
    return DiscoveryExecution(
        result=result,
        elapsed_seconds=elapsed,
        status_message=status_message,
    )


async def load_curated_cards_for_opportunity_ids(
    store: EntityStore,
    opportunity_ids: list[str],
    company_profile_id: str | None,
) -> list[OpportunityCard]:
    """주어진 opportunity ids만 current/actionable 카드로 복원."""
    if not opportunity_ids:
        return []

    from src.interface.handlers.list_handler import _opportunities_to_cards

    allowed = set(opportunity_ids)
    rows = await store.list_opportunities_curated(
        company_profile_id=company_profile_id,
        min_confidence=0.75,
        limit=max(len(opportunity_ids), 10),
    )
    filtered_rows = [row for row in rows if row["id"] in allowed]
    return filter_current_cards(_opportunities_to_cards(filtered_rows))


async def send_source_lead_intake(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    source_urls: list[str],
    message_text: str,
) -> None:
    """유저가 붙여준 funding lead URL을 직접 fetch/extract/verify 한다."""
    store: EntityStore = context.bot_data["store"]
    profile = await store.get_profile_by_telegram_user(update.effective_user.id)
    profile_id = profile.id if profile else None
    query_hint = build_source_query_hint(message_text)

    execution = await run_discovery_with_status(
        update,
        store,
        query=query_hint,
        company_profile_id=profile_id,
        source_urls=source_urls,
        start_text=(
            f"🔗 붙여준 링크 {len(source_urls)}개 검토 중...\n"
            "🌐 직접 fetch + extract + verify"
        ),
        success_text_builder=lambda result, elapsed: (
            f"✅ 링크 검토 완료 ({elapsed:.1f}초)\n"
            f"발견: {result.total_discovered} → 저장: {result.total_ingested} → 검증: {result.total_verified}"
        ),
        error_prefix="링크 검토 중 오류 발생",
    )
    if execution is None:
        return

    if execution.result.total_discovered == 0:
        await update.message.reply_text(
            escape_md("붙여준 링크에서 지원 가능한 프로그램을 추출하지 못했습니다."),
            parse_mode="MarkdownV2",
        )
        return

    cards = await load_curated_cards_for_opportunity_ids(
        store,
        execution.result.ingested_opp_ids,
        profile_id,
    )
    if cards:
        text = render_ranked_list(cards[:10], title="🔗 붙여준 링크 검토 결과")
        await update.message.reply_text(
            text,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
        )
        return

    followup = "링크는 검토/저장했지만 현재 기준의 verified actionable 결과는 아직 없습니다."
    if not profile_id:
        followup += "\n/register 후 다시 보면 맞춤 추천 품질이 올라갑니다."
    await update.message.reply_text(
        escape_md(followup),
        parse_mode="MarkdownV2",
    )


async def send_search_results(
    update: Update,
    *,
    store: EntityStore,
    query: str,
    category: ProgramCategory | None,
    profile_id: str | None,
) -> None:
    if profile_id:
        await _show_matched_results(
            update,
            store=store,
            profile_id=profile_id,
            query=query,
            category=category,
        )
        return

    await _show_list_results(
        update,
        store=store,
        query=query,
        category=category,
    )


async def _show_matched_results(
    update: Update,
    store: EntityStore,
    profile_id: str,
    query: str,
    category: ProgramCategory | None,
) -> None:
    rows = await store.list_opportunities_curated(
        company_profile_id=profile_id,
        min_confidence=0.0,
        category=category,
    )

    if not rows:
        await update.message.reply_text(
            escape_md("저장된 결과가 있지만 표시 기준을 충족하는 항목이 없습니다."),
            parse_mode="MarkdownV2",
        )
        return

    agent = MatchingAgent(store=store, config=config)
    opp_ids = [row["id"] for row in rows]
    ranked = await agent.batch_rank(
        opportunity_ids=opp_ids,
        profile_id=profile_id,
        intent="default",
        top_n=10,
    )

    if not ranked:
        await _show_list_results(update, store, query, category)
        return

    cards: list[OpportunityCard] = []
    for ranked_item in ranked:
        opp = await store.get_opportunity(ranked_item.opportunity_id)
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

        cards.append(
            OpportunityCard(
                organization=org_name,
                program=prog_name,
                category=program.category.value if program else "unknown",
                status=opp.status.value,
                apply_url=opp.apply_url or "",
                confidence=opp.fact_confidence,
                deadline=opp.deadline_at.isoformat()[:10] if opp.deadline_at else None,
                days_left=opp.days_left,
                budget=opp.budget_note,
                fit_score=ranked_item.fit_score,
                priority_score=ranked_item.priority_score,
                why_fit=ranked_item.why_fit,
                next_action=ranked_item.next_action,
            )
        )

    cards = filter_current_cards(cards)
    if not cards:
        await _show_list_results(update, store, query, category)
        return

    await update.message.reply_text(
        render_ranked_list(cards, title=f"🎯 \"{query}\" 맞춤 검색 결과"),
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )


async def _show_list_results(
    update: Update,
    store: EntityStore,
    query: str,
    category: ProgramCategory | None,
) -> None:
    rows = await store.list_opportunities_curated(
        company_profile_id=None,
        min_confidence=0.0,
        category=category,
    )

    if not rows:
        await update.message.reply_text(
            escape_md("결과가 저장되었지만 표시 기준을 충족하는 항목이 없습니다."),
            parse_mode="MarkdownV2",
        )
        return

    from src.interface.handlers.list_handler import _opportunities_to_cards

    cards = filter_current_cards(_opportunities_to_cards(rows))
    if not cards:
        await update.message.reply_text(
            escape_md("현재 지원 가능한 결과가 없습니다."),
            parse_mode="MarkdownV2",
        )
        return

    text = render_ranked_list(cards, title=f"🔍 \"{query}\" 검색 결과")
    text += f"\n\n{escape_md('💡 /register로 프로필을 등록하면 맞춤 순위를 받을 수 있습니다.')}"
    await update.message.reply_text(
        text,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True,
    )
