"""
Funding Intelligence Agent — Funding Handler.

/funding <project> [intent] — 프로필 기반 통합 펀딩 검색.

흐름:
  1. 프로필 로드 (DB → 하드코딩 폴백)
  2. "검색 중..." 상태 메시지
  3. FundingSearchOrchestrator.search_for_project() 실행
  4. 결과 카드 렌더링 → 전송
"""

from __future__ import annotations

import time

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from src.agents.matching import MatchingAgent
from src.core.config import config
from src.core.profiles import get_default_profile
from src.core.types import CompanyProfile, MatchingOutput, OpportunityCard
from src.db.entity_store import EntityStore
from src.interface.card_renderer import escape_md, render_funding_results
from src.search.funding_orchestrator import FundingSearchOrchestrator

logger = structlog.get_logger()

# 유효한 intent 목록
VALID_INTENTS = {"default", "urgent", "biggest_check", "ready_now", "best_fit"}

# Intent 한글 매핑 (사용자 편의)
INTENT_ALIASES: dict[str, str] = {
    "긴급": "urgent",
    "급한": "urgent",
    "최대": "biggest_check",
    "지금": "ready_now",
    "적합": "best_fit",
    "추천": "default",
}


async def funding_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/funding <project> [intent] — 프로필 기반 통합 펀딩 검색.

    사용법:
      /funding HOOT           → 기본 추천 순위
      /funding HOOT urgent    → 마감 임박 우선
      /funding HOOT best_fit  → 적합도 우선
    """
    store: EntityStore = context.bot_data["store"]

    # ── 인자 파싱 ──
    args = context.args or []

    if not args:
        await update.message.reply_text(
            escape_md(
                "사용법: /funding <프로젝트명> [intent]\n\n"
                "예시:\n"
                "  /funding HOOT          — 추천 순위\n"
                "  /funding HOOT urgent   — 마감 임박 우선\n"
                "  /funding HOOT best_fit — 적합도 우선\n\n"
                "Intent 종류: default, urgent, biggest_check, ready_now, best_fit"
            ),
            parse_mode="MarkdownV2",
        )
        return

    project_name = args[0]
    intent = "default"
    if len(args) > 1:
        raw_intent = args[1].lower()
        intent = INTENT_ALIASES.get(raw_intent, raw_intent)
        if intent not in VALID_INTENTS:
            intent = "default"

    # ── 프로필 로드 ──
    profile = await _load_profile(store, update.effective_user.id, project_name)

    if profile is None:
        await update.message.reply_text(
            escape_md(
                f"'{project_name}' 프로필을 찾을 수 없습니다.\n"
                f"/register로 프로필을 등록하거나, /funding HOOT 으로 기본 프로필을 사용하세요."
            ),
            parse_mode="MarkdownV2",
        )
        return

    # ── 검색 중 상태 메시지 ──
    intent_labels = {
        "default": "추천 순위",
        "urgent": "마감 임박",
        "biggest_check": "최대 금액",
        "ready_now": "지금 지원 가능",
        "best_fit": "최고 적합도",
    }
    intent_label = intent_labels.get(intent, intent)

    status_msg = await update.message.reply_text(
        escape_md(
            f"🔍 {project_name} 기준 펀딩 검색 중...\n"
            f"📊 Intent: {intent_label}\n"
            f"🌐 웹 검색 + 소셜 + 참조 데이터 스캔"
        ),
        parse_mode="MarkdownV2",
    )

    # ── 통합 검색 실행 ──
    start = time.monotonic()

    try:
        orchestrator = FundingSearchOrchestrator(
            store=store,
            config=config,
        )

        result = await orchestrator.search_for_project(
            profile=profile,
            intent=intent,
            top_n=15,
        )

        elapsed = time.monotonic() - start

        # ── 진행 상황 업데이트 ──
        progress = (
            f"✅ 검색 완료 ({elapsed:.1f}초)\n"
            f"📊 웹 {result.web_count} │ 소셜 {result.social_count} │ 참조 {result.reference_count}\n"
            f"📋 통합 {result.total_raw} → 중복제거 {result.total_deduped} → 저장 {result.total_ingested}"
        )
        if result.new_discovered > 0:
            progress += f"\n🆕 새로 발견: {result.new_discovered}개"

        await status_msg.edit_text(
            escape_md(progress),
            parse_mode="MarkdownV2",
        )

        # ── 결과 없음 ──
        if not result.ranked_results:
            await update.message.reply_text(
                escape_md(
                    f"'{project_name}' 기준 매칭되는 펀딩 기회를 찾지 못했습니다.\n"
                    f"다른 프로필이나 Intent로 다시 시도해보세요."
                ),
                parse_mode="MarkdownV2",
            )
            return

        # ── 결과 카드 렌더링 ──
        cards = await _ranked_to_cards(store, result.ranked_results)

        text = render_funding_results(
            cards=cards,
            project_name=project_name,
            intent=intent_label,
            web_count=result.web_count,
            social_count=result.social_count,
            ref_count=result.reference_count,
            new_count=result.new_discovered,
            elapsed=elapsed,
        )

        await update.message.reply_text(
            text,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
        )

    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error("funding_handler.error", error=str(e), elapsed=elapsed)
        await status_msg.edit_text(
            escape_md(f"⚠️ 검색 중 오류 발생: {str(e)[:100]}"),
            parse_mode="MarkdownV2",
        )


# ============================================================
# 헬퍼
# ============================================================

async def _load_profile(
    store: EntityStore,
    telegram_user_id: int,
    project_name: str,
) -> CompanyProfile | None:
    """프로필 로드 (DB → 하드코딩 폴백)."""
    # 1. Telegram 유저 기반 DB 프로필
    profile = await store.get_profile_by_telegram_user(telegram_user_id)
    if profile:
        return profile

    # 2. 하드코딩 프로필 폴백
    return get_default_profile(project_name)


async def _ranked_to_cards(
    store: EntityStore,
    ranked: list[MatchingOutput],
) -> list[OpportunityCard]:
    """MatchingOutput → OpportunityCard 변환."""
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

        cards.append(OpportunityCard(
            organization=org_name,
            program=prog_name,
            category=program.category.value if program else "unknown",
            status=opp.status.value,
            apply_url=opp.apply_url or "",
            confidence=opp.fact_confidence,
            deadline=(
                opp.deadline_at.isoformat()[:10] if opp.deadline_at else None
            ),
            days_left=opp.days_left,
            budget=opp.budget_note,
            fit_score=mo.fit_score,
            priority_score=mo.priority_score,
            why_fit=mo.why_fit,
            next_action=mo.next_action,
        ))

    return cards
