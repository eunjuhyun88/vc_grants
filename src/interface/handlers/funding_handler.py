"""
Funding Intelligence Agent — Funding Handler.

/funding [intent] — 프로필 기반 즉시 펀딩 추천 (참조 데이터, ~1초).
/discover [intent] — 웹 포함 심층 탐색 (Discovery Loop, 2~5분).

유저 흐름:
  1. /register → 프로젝트 정보 등록
  2. /funding  → 즉시 맞춤 추천 (636건 참조 데이터 매칭)
  3. /discover → 더 많은 기회 웹 탐색 (선택)
"""

from __future__ import annotations

import asyncio
import time

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from src.core.config import config
from src.core.profile_identity import repair_profile_identity
from src.core.profiles import get_default_profile
from src.core.types import CompanyProfile, MatchingOutput, OpportunityCard
from src.db.entity_store import EntityStore
from src.interface.card_renderer import escape_md, render_funding_results
from src.research.actionable_funding_service import (
    build_actionable_funding_view,
    primary_project_name,
    ranked_to_cards as build_ranked_cards,
)

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
    """/funding [intent] — 즉시 맞춤 추천 (참조 데이터).

    사용법:
      /funding            → 내 프로필 기준 추천
      /funding urgent     → 마감 임박 우선
      /funding best_fit   → 적합도 우선
    """
    await _handle_funding(update, context, mode="fast")


async def discover_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/discover [intent] — 웹 포함 심층 탐색 (Discovery Loop).

    사용법:
      /discover           → 웹 + 참조 데이터 심층 탐색
      /discover urgent    → 마감 임박 우선 심층 탐색
    """
    await _handle_funding(update, context, mode="deep")


async def _handle_funding(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    mode: str = "fast",
) -> None:
    """공통 펀딩 검색 로직."""
    store: EntityStore = context.bot_data["store"]

    # ── 인자 파싱 ──
    args = context.args or []
    intent = "default"

    if args:
        raw_intent = args[0].lower()
        intent = INTENT_ALIASES.get(raw_intent, raw_intent)
        if intent not in VALID_INTENTS:
            intent = "default"

    # ── 프로필 로드 ──
    profile = await _load_profile(store, update.effective_user.id)

    if profile is None:
        await update.message.reply_text(
            escape_md(
                "등록된 프로필이 없습니다.\n\n"
                "/register 로 프로젝트 정보를 등록하세요.\n\n"
                "등록 항목:\n"
                "  • 회사/프로젝트명\n"
                "  • 단계 (idea/mvp/growth 등)\n"
                "  • 분야 (ai, crypto, defi 등)\n"
                "  • 타겟 생태계 (ethereum, solana 등)\n"
                "  • 프로젝트 설명\n\n"
                "등록 후 /funding 으로 맞춤 추천을 받으세요!"
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
    company = primary_project_name(profile, fallback="내 프로젝트")

    if mode == "fast":
        status_text = (
            f"🔍 {company} 기준 펀딩 매칭 중...\n"
            f"📊 Intent: {intent_label}\n"
            f"📋 참조 데이터 스캔 중"
        )
    else:
        status_text = (
            f"🔍 {company} 기준 심층 탐색 중...\n"
            f"📊 Intent: {intent_label}\n"
            f"🌐 웹 검색 + 참조 데이터 + Discovery Loop\n"
            f"⏱ 2~5분 소요"
        )

    status_msg = await update.message.reply_text(
        escape_md(status_text),
        parse_mode="MarkdownV2",
    )

    # ── 검색 실행 ──
    start = time.monotonic()

    # Deep 모드: 5분 타임아웃 + 30초마다 진행 메시지
    DEEP_TIMEOUT = 300  # 5분
    PROGRESS_INTERVAL = 30  # 30초마다 업데이트

    async def _progress_updater():
        """Deep 모드에서 30초마다 진행 상황 업데이트."""
        tick = 0
        while True:
            await asyncio.sleep(PROGRESS_INTERVAL)
            tick += 1
            elapsed = time.monotonic() - start
            try:
                await status_msg.edit_text(
                    escape_md(
                        f"🔍 심층 탐색 진행 중... ({elapsed:.0f}초 경과)\n"
                        f"🔄 라운드 진행 중 (최대 {DEEP_TIMEOUT}초)\n"
                        f"⏳ 잠시만 기다려주세요"
                    ),
                    parse_mode="MarkdownV2",
                )
            except Exception:
                pass

    try:
        if mode == "deep":
            # 타임아웃 + 진행 메시지
            progress_task = asyncio.create_task(_progress_updater())
            try:
                view = await asyncio.wait_for(
                    build_actionable_funding_view(
                        store=store,
                        config=config,
                        profile=profile,
                        intent=intent,
                        top_n=15,
                        mode=mode,
                    ),
                    timeout=DEEP_TIMEOUT,
                )
            except asyncio.TimeoutError:
                view = None
                logger.warning("funding_handler.deep_timeout", elapsed=DEEP_TIMEOUT)
                await status_msg.edit_text(
                    escape_md(
                        f"⏱ 심층 탐색 {DEEP_TIMEOUT}초 타임아웃.\n"
                        f"중간까지 찾은 결과를 보여드립니다."
                    ),
                    parse_mode="MarkdownV2",
                )
            finally:
                progress_task.cancel()
        else:
            view = await build_actionable_funding_view(
                store=store,
                config=config,
                profile=profile,
                intent=intent,
                top_n=15,
                mode=mode,
            )

        elapsed = time.monotonic() - start

        # 타임아웃/에러로 result가 None인 경우
        if view is None:
            from src.search.funding_orchestrator import FundingSearchResult
            from src.research.actionable_funding_service import ActionableFundingView
            view = ActionableFundingView(project_name=company, result=FundingSearchResult())
        result = view.result

        # ── 진행 상황 업데이트 ──
        if mode == "fast":
            progress = (
                f"✅ 매칭 완료 ({elapsed:.1f}초)\n"
                f"📋 참조 데이터 {result.reference_count}건 매칭\n"
                f"💾 DB 저장 {result.total_ingested}건"
            )
        else:
            progress = (
                f"✅ 심층 탐색 완료 ({elapsed:.1f}초)\n"
                f"📊 웹 {result.web_count} │ 참조 {result.reference_count}\n"
                f"📋 총 {result.total_raw} → 중복제거 {result.total_deduped} → 저장 {result.total_ingested}"
            )

        if result.new_discovered > 0:
            progress += f"\n🆕 새로 발견: {result.new_discovered}개"

        if result.round_log and len(result.round_log) > 1:
            progress += f"\n🔄 Discovery: {len(result.round_log)} 라운드"

        await status_msg.edit_text(
            escape_md(progress),
            parse_mode="MarkdownV2",
        )

        # ── 결과 없음 ──
        if not view.ranked_results:
            no_result = f"'{company}' 기준 매칭 결과가 없습니다.\n"
            if mode == "fast":
                no_result += "\n💡 /discover 로 웹 심층 탐색을 시도해보세요."
            else:
                no_result += "\n💡 /register 로 프로필을 수정해보세요."

            await update.message.reply_text(
                escape_md(no_result),
                parse_mode="MarkdownV2",
            )
            return

        # ── 결과 카드 렌더링 ──
        cards = view.actionable_cards

        if not cards:
            await update.message.reply_text(
                escape_md("현재 지원 가능한 결과가 없습니다."),
                parse_mode="MarkdownV2",
            )
            return

        text = render_funding_results(
            cards=cards,
            project_name=company,
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

        # ── fast mode: 웹 탐색 안내 ──
        if mode == "fast":
            await update.message.reply_text(
                escape_md(
                    "💡 더 많은 기회를 찾으려면 /discover 로 웹 심층 탐색"
                ),
                parse_mode="MarkdownV2",
            )

    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error("funding_handler.error", error=str(e), elapsed=elapsed)
        await status_msg.edit_text(
            escape_md(f"⚠️ 오류 발생: {str(e)[:100]}"),
            parse_mode="MarkdownV2",
        )


# ============================================================
# 헬퍼
# ============================================================

async def _load_profile(
    store: EntityStore,
    telegram_user_id: int,
) -> CompanyProfile | None:
    """프로필 로드 (DB → 하드코딩 폴백)."""
    # 1. Telegram 유저 기반 DB 프로필
    profile = await store.get_profile_by_telegram_user(telegram_user_id)
    if profile:
        return repair_profile_identity(profile)

    # 2. 하드코딩 프로필 폴백 (테스트용)
    return get_default_profile("HOOT")


async def _ranked_to_cards(
    store: EntityStore,
    ranked: list[MatchingOutput],
) -> list[OpportunityCard]:
    """Backward-compatible wrapper around the shared research service helper."""
    return await build_ranked_cards(store, ranked)
