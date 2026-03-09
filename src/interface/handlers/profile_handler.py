"""
Funding Intelligence Agent — Profile Handlers.

/start — 봇 소개
/register — 프로필 등록 (multi-step conversation)
/profile — 현재 프로필 조회
"""

from __future__ import annotations

import json

import structlog
from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.core.types import CompanyProfile, CompanyStage, generate_id
from src.db.entity_store import EntityStore
from src.interface.card_renderer import escape_md

logger = structlog.get_logger()

# ConversationHandler states
COMPANY_NAME, STAGE, SECTORS, PROJECT_NAME, PROJECT_TAGS, CONFIRM = range(6)


async def start_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/start — 봇 소개 + 안내."""
    welcome = (
        "🤖 *Funding Intelligence Agent*\n\n"
        "AI 기반 펀딩 기회 탐색·검증·매칭 봇입니다\\.\n\n"
        "*사용 가능한 명령어:*\n"
        "  /register — 프로젝트 프로필 등록\n"
        "  /profile — 내 프로필 조회\n"
        "  /grants — Grant 프로그램 목록\n"
        "  /cohorts — VC Cohort 목록\n"
        "  /funds — Accelerator 목록\n"
        "  /all — 전체 기회 목록\n"
        "  /ranking \\[intent\\] — 개인화 순위\n\n"
        "먼저 /register 로 프로필을 등록하세요\\!"
    )
    await update.message.reply_text(welcome, parse_mode="MarkdownV2")


async def profile_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/profile — 현재 프로필 조회."""
    store: EntityStore = context.bot_data["store"]
    user_id = update.effective_user.id

    profile = await store.get_profile_by_telegram_user(user_id)

    if profile is None:
        await update.message.reply_text(
            escape_md("등록된 프로필이 없습니다. /register 로 등록하세요."),
            parse_mode="MarkdownV2",
        )
        return

    lines = [
        f"👤 *{escape_md(profile.company_name)}*",
        f"   단계: {escape_md(profile.stage.value if profile.stage else 'N/A')}",
        f"   분야: {escape_md(', '.join(profile.sector_tags) if profile.sector_tags else 'N/A')}",
    ]

    if profile.projects:
        lines.append("   📦 프로젝트:")
        for proj in profile.projects:
            name = proj.get("name", "Unnamed")
            tags = ", ".join(proj.get("tags", []))
            lines.append(f"     • {escape_md(name)} \\({escape_md(tags)}\\)")

    if profile.description:
        lines.append(f"   📝 {escape_md(profile.description)}")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="MarkdownV2",
    )


# ============================================================
# Registration Conversation
# ============================================================


async def register_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """/register — 등록 시작."""
    store: EntityStore = context.bot_data["store"]
    user_id = update.effective_user.id

    # 이미 프로필이 있는지 확인
    existing = await store.get_profile_by_telegram_user(user_id)
    if existing:
        await update.message.reply_text(
            escape_md(
                f"이미 '{existing.company_name}' 프로필이 등록되어 있습니다. "
                f"다시 등록하면 기존 프로필이 업데이트됩니다.\n\n"
                f"회사/프로젝트 이름을 입력하세요:"
            ),
            parse_mode="MarkdownV2",
        )
    else:
        await update.message.reply_text(
            escape_md("프로필 등록을 시작합니다.\n\n회사/프로젝트 이름을 입력하세요:"),
            parse_mode="MarkdownV2",
        )

    context.user_data["reg"] = {}
    return COMPANY_NAME


async def reg_company_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """회사명 입력 → 단계 질문."""
    context.user_data["reg"]["company_name"] = update.message.text.strip()

    stages = ", ".join([s.value for s in CompanyStage])
    await update.message.reply_text(
        escape_md(f"현재 단계를 입력하세요 ({stages}):"),
        parse_mode="MarkdownV2",
    )
    return STAGE


async def reg_stage(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """단계 입력 → 분야 질문."""
    stage_input = update.message.text.strip().lower()

    # 유효한 stage인지 확인
    valid_stages = {s.value for s in CompanyStage}
    if stage_input not in valid_stages:
        await update.message.reply_text(
            escape_md(f"유효하지 않은 단계입니다. 다시 입력하세요: {', '.join(valid_stages)}"),
            parse_mode="MarkdownV2",
        )
        return STAGE

    context.user_data["reg"]["stage"] = stage_input

    await update.message.reply_text(
        escape_md("관련 분야를 쉼표로 구분하여 입력하세요\n"
                   "(예: ai, crypto, defi, gaming):"),
        parse_mode="MarkdownV2",
    )
    return SECTORS


async def reg_sectors(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """분야 입력 → 프로젝트명 질문."""
    tags = [t.strip().lower() for t in update.message.text.split(",") if t.strip()]
    context.user_data["reg"]["sector_tags"] = tags

    await update.message.reply_text(
        escape_md("주요 프로젝트 이름을 입력하세요:"),
        parse_mode="MarkdownV2",
    )
    return PROJECT_NAME


async def reg_project_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """프로젝트명 → 프로젝트 태그 질문."""
    context.user_data["reg"]["project_name"] = update.message.text.strip()

    await update.message.reply_text(
        escape_md("프로젝트 관련 태그를 쉼표로 입력하세요\n"
                   "(예: ai_infra, blockchain, distributed_compute):"),
        parse_mode="MarkdownV2",
    )
    return PROJECT_TAGS


async def reg_project_tags(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """프로젝트 태그 → 확인."""
    tags = [t.strip().lower() for t in update.message.text.split(",") if t.strip()]
    context.user_data["reg"]["project_tags"] = tags

    reg = context.user_data["reg"]
    summary = (
        f"확인해 주세요:\n"
        f"  회사명: {reg['company_name']}\n"
        f"  단계: {reg['stage']}\n"
        f"  분야: {', '.join(reg['sector_tags'])}\n"
        f"  프로젝트: {reg['project_name']}\n"
        f"  프로젝트 태그: {', '.join(reg['project_tags'])}\n\n"
        f"맞으면 '확인', 취소하려면 /cancel"
    )
    await update.message.reply_text(
        escape_md(summary),
        parse_mode="MarkdownV2",
    )
    return CONFIRM


async def reg_confirm(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """확인 → DB 저장."""
    text = update.message.text.strip()
    if text not in ("확인", "yes", "y", "ㅇ"):
        await update.message.reply_text(
            escape_md("등록이 취소되었습니다."),
            parse_mode="MarkdownV2",
        )
        return ConversationHandler.END

    store: EntityStore = context.bot_data["store"]
    user_id = update.effective_user.id
    reg = context.user_data["reg"]

    # 기존 프로필 확인
    existing = await store.get_profile_by_telegram_user(user_id)

    if existing:
        # 업데이트
        await store.update_company_profile(
            existing.id,
            company_name=reg["company_name"],
            stage=CompanyStage(reg["stage"]),
            sector_tags=reg["sector_tags"],
            projects=[{
                "name": reg["project_name"],
                "priority": 1,
                "tags": reg["project_tags"],
            }],
        )
        profile_id = existing.id
    else:
        # 신규 생성
        profile = CompanyProfile(
            id=generate_id("cp_"),
            company_name=reg["company_name"],
            stage=CompanyStage(reg["stage"]),
            sector_tags=reg["sector_tags"],
            projects=[{
                "name": reg["project_name"],
                "priority": 1,
                "tags": reg["project_tags"],
            }],
            telegram_user_id=user_id,
        )
        await store.create_company_profile(profile)
        profile_id = profile.id

    await update.message.reply_text(
        escape_md(f"✅ 프로필이 등록되었습니다! (ID: {profile_id})\n"
                   f"/grants, /ranking 등으로 펀딩 기회를 확인하세요."),
        parse_mode="MarkdownV2",
    )

    context.user_data.pop("reg", None)
    return ConversationHandler.END


async def reg_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """등록 취소."""
    context.user_data.pop("reg", None)
    await update.message.reply_text(
        escape_md("등록이 취소되었습니다."),
        parse_mode="MarkdownV2",
    )
    return ConversationHandler.END


def get_registration_handler() -> ConversationHandler:
    """ConversationHandler 생성."""
    return ConversationHandler(
        entry_points=[CommandHandler("register", register_start)],
        states={
            COMPANY_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reg_company_name),
            ],
            STAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reg_stage),
            ],
            SECTORS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reg_sectors),
            ],
            PROJECT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reg_project_name),
            ],
            PROJECT_TAGS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reg_project_tags),
            ],
            CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reg_confirm),
            ],
        },
        fallbacks=[CommandHandler("cancel", reg_cancel)],
    )
