"""
Funding Intelligence Agent — Search Handler.

/search <쿼리> — 라이브 검색 + 프로필 기반 매칭.
"""

from __future__ import annotations

from collections.abc import Callable

from telegram import Update
from telegram.ext import ContextTypes

from src.core.types import ProgramCategory
from src.db.entity_store import EntityStore
from src.interface.card_renderer import escape_md
from src.interface.discovery_runtime import (
    run_discovery_with_status,
    send_search_results,
)
from src.research.runtime_reflection import resolve_runtime_reflection_seeds
from src.search.engines.reference_engine import ReferenceDataEngine
from src.search.research_goal_router import GoalType

# 카테고리 키워드 매핑
CATEGORY_KEYWORDS: dict[str, ProgramCategory] = {
    "grant": ProgramCategory.GRANT,
    "grants": ProgramCategory.GRANT,
    "그랜트": ProgramCategory.GRANT,
    "accelerator": ProgramCategory.ACCELERATOR,
    "액셀러레이터": ProgramCategory.ACCELERATOR,
    "vc": ProgramCategory.VC_COHORT,
    "cohort": ProgramCategory.VC_COHORT,
    "코호트": ProgramCategory.VC_COHORT,
    "ecosystem": ProgramCategory.ECOSYSTEM_BUILDER,
    "생태계": ProgramCategory.ECOSYSTEM_BUILDER,
}


def _detect_category(text: str) -> ProgramCategory | None:
    """쿼리에서 카테고리 키워드 감지."""
    lower = text.lower()
    for keyword, category in CATEGORY_KEYWORDS.items():
        if keyword in lower:
            return category
    return None


def _goal_type_for_search(category: ProgramCategory | None) -> GoalType:
    if category == ProgramCategory.GRANT:
        return GoalType.GRANT_COVERAGE
    if category in {
        ProgramCategory.ACCELERATOR,
        ProgramCategory.VC_COHORT,
        ProgramCategory.BUILDER_PROGRAM,
        ProgramCategory.ECOSYSTEM_BUILDER,
        ProgramCategory.RESIDENCY,
        ProgramCategory.HACKATHON_PIPELINE,
    }:
        return GoalType.COHORT_RECALL
    return GoalType.ACTIONABLE_STRATEGY


def _build_search_success_text(
    *,
    include_matching: bool,
) -> Callable[[object, float], str]:
    def _builder(result, elapsed: float) -> str:
        progress = (
            f"✅ 검색 완료 ({elapsed:.1f}초)\n"
            f"발견: {result.total_discovered} → "
            f"저장: {result.total_ingested} → "
            f"검증: {result.total_verified}"
        )
        if include_matching:
            progress += f" → 매칭: {result.total_matched}"
        return progress

    return _builder


async def search_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/search <쿼리> — 라이브 검색 실행."""
    store: EntityStore = context.bot_data["store"]
    args = context.args or []
    if not args:
        await update.message.reply_text(
            escape_md(
                "사용법: /search <검색어>\n"
                "예시:\n"
                "  /search AI grants\n"
                "  /search DeFi accelerator program\n"
                "  /search Ethereum ecosystem funding"
            ),
            parse_mode="MarkdownV2",
        )
        return

    query = " ".join(args)
    category = _detect_category(query)
    profile = await store.get_profile_by_telegram_user(update.effective_user.id)
    profile_id = profile.id if profile else None
    hint_queries: list[str] = []
    source_urls: list[str] = []

    if profile is not None:
        seeds = resolve_runtime_reflection_seeds(
            profile=profile,
            goal_type=_goal_type_for_search(category),
        )
        hint_queries = list(seeds.search_hints)
        priority_terms = list(seeds.bootstrap_terms) + list(seeds.search_hints)
        if priority_terms:
            source_urls = ReferenceDataEngine().bootstrap_sources(
                profile,
                top_n=8,
                priority_terms=priority_terms,
            )

    execution = await run_discovery_with_status(
        update,
        store,
        query=query,
        category=category,
        company_profile_id=profile_id,
        source_urls=source_urls,
        hint_queries=hint_queries,
        start_text=f"🔍 \"{query}\" 검색 중... (최대 60초 소요)",
        success_text_builder=_build_search_success_text(
            include_matching=bool(profile_id),
        ),
        error_prefix="검색 중 오류 발생",
    )
    if execution is None:
        return

    if execution.result.total_discovered == 0:
        await execution.status_message.edit_text(
            escape_md(
                f"검색 완료 ({execution.elapsed_seconds:.1f}초). "
                f"'{query}'에 대한 결과를 찾지 못했습니다.\n"
                "다른 키워드로 시도해보세요."
            ),
            parse_mode="MarkdownV2",
        )
        return

    if execution.result.total_ingested <= 0:
        return

    await send_search_results(
        update,
        store=store,
        query=query,
        category=category,
        profile_id=profile_id,
    )
