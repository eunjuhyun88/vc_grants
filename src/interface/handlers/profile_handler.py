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

from src.core.profile_identity import repair_profile_identity
from src.core.profiles import get_default_profile
from src.core.types import CompanyProfile, CompanyStage, generate_id
from src.db.entity_store import EntityStore
from src.interface.card_renderer import escape_md

logger = structlog.get_logger()

# ConversationHandler states
(
    COMPANY_NAME, STAGE, SECTORS, ECOSYSTEMS,
    PROJECT_NAME, PROJECT_TAGS, DESCRIPTION, CONFIRM,
) = range(8)


async def start_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/start — 봇 소개 + 안내."""
    store: EntityStore = context.bot_data["store"]
    user_id = update.effective_user.id
    profile = repair_profile_identity(await store.get_profile_by_telegram_user(user_id))

    if profile is not None:
        project_name = (
            (profile.projects[0].get("name") if profile.projects else None)
            or profile.company_name
        )
        welcome = (
            "🤖 *Funding Intelligence Agent*\n\n"
            f"현재 프로필: *{escape_md(project_name)}*\n"
            f"회사명: {escape_md(profile.company_name)}\n"
            f"단계: {escape_md(profile.stage.value if profile.stage else 'N/A')}\n\n"
            "*바로 실행:*\n"
            "  /funding — 현재 actionable funding\n"
            "  /funding\\_for\\_project HOOT — HOOT 액션 리스트\n"
            "  /funding\\_map HOOT — HOOT funding map\n"
            "  /org Monad — Monad dossier\n\n"
            "*프로필 관리:*\n"
            "  /profile — 현재 프로필 조회\n"
            "  /register — 수동 수정\n"
            "  /setup\\_hoot — HOOT 기본 프로필로 재설정\n"
            "  /reset\\_profile confirm — 프로필 초기화"
        )
    else:
        welcome = (
            "🤖 *Funding Intelligence Agent*\n\n"
            "프로젝트에 맞는 투자사·Grant·Accelerator를\n"
            "자동으로 찾아 추천해드립니다\\.\n\n"
            "*빠른 시작:*\n"
            "  /setup\\_hoot — HOOT 기본 프로필로 즉시 시작\n"
            "  /register — 직접 프로필 등록\n\n"
            "*추천 명령:*\n"
            "  /funding — 맞춤 펀딩 추천 \\(즉시\\)\n"
            "  /funding\\_for\\_project HOOT — 특정 프로젝트 기준 액션 리스트\n"
            "  /funding\\_map HOOT — 프로젝트별 funding landscape\n"
            "  /discover — 웹 심층 탐색\n"
        )
    await update.message.reply_text(welcome, parse_mode="MarkdownV2")


async def profile_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/profile — 현재 프로필 조회."""
    store: EntityStore = context.bot_data["store"]
    user_id = update.effective_user.id

    profile = repair_profile_identity(await store.get_profile_by_telegram_user(user_id))

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

    if profile.target_ecosystems:
        lines.append(
            f"   생태계: {escape_md(', '.join(profile.target_ecosystems))}"
        )

    if profile.projects:
        lines.append("   📦 프로젝트:")
        for proj in profile.projects:
            name = proj.get("name", "Unnamed")
            tags = ", ".join(proj.get("tags", []))
            lines.append(
                f"     • {escape_md(name)} \\({escape_md(tags)}\\)"
            )

    if profile.product_summary:
        lines.append(f"   📝 {escape_md(profile.product_summary)}")

    lines.append("")
    lines.append(escape_md("💡 /funding 으로 맞춤 추천 받기"))

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="MarkdownV2",
    )


async def seed_default_profile_for_user(
    store: EntityStore,
    user_id: int,
    profile_key: str = "HOOT",
) -> CompanyProfile | None:
    base = get_default_profile(profile_key)
    if base is None:
        return None

    existing = await store.get_profile_by_telegram_user(user_id)
    if existing:
        await store.update_company_profile(
            existing.id,
            company_name=base.company_name,
            stage=base.stage,
            sector_tags=base.sector_tags,
            subsector_tags=base.subsector_tags,
            target_ecosystems=base.target_ecosystems,
            geography=base.geography,
            funding_goal=base.funding_goal,
            product_summary=base.product_summary,
            projects=base.projects,
        )
        return repair_profile_identity(await store.get_profile_by_telegram_user(user_id))

    profile = CompanyProfile(
        id=generate_id("cp_"),
        company_name=base.company_name,
        stage=base.stage,
        sector_tags=base.sector_tags,
        subsector_tags=base.subsector_tags,
        projects=base.projects,
        description=base.description,
        geography=base.geography,
        funding_goal=base.funding_goal,
        product_summary=base.product_summary,
        target_ecosystems=base.target_ecosystems,
        telegram_user_id=user_id,
    )
    await store.create_company_profile(profile)
    return profile


async def delete_profile_for_user(store: EntityStore, user_id: int) -> bool:
    return await store.delete_profile_by_telegram_user(user_id)


async def setup_hoot_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/setup_hoot — HOOT 기본 프로필 즉시 적용."""
    store: EntityStore = context.bot_data["store"]
    profile = await seed_default_profile_for_user(store, update.effective_user.id, "HOOT")
    if profile is None:
        await update.message.reply_text(
            escape_md("HOOT 기본 프로필을 불러오지 못했습니다."),
            parse_mode="MarkdownV2",
        )
        return

    await update.message.reply_text(
        escape_md(
            "✅ HOOT 기본 프로필이 적용되었습니다.\n\n"
            "이제 바로 아래 명령을 써보세요:\n"
            "  /funding\n"
            "  /funding_for_project HOOT\n"
            "  /funding_map HOOT"
        ),
        parse_mode="MarkdownV2",
    )


async def reset_profile_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/reset_profile confirm — 저장된 프로필 삭제."""
    store: EntityStore = context.bot_data["store"]
    args = context.args or []
    if not args or args[0].lower() != "confirm":
        await update.message.reply_text(
            escape_md(
                "프로필을 초기화하려면 아래처럼 입력하세요:\n"
                "  /reset_profile confirm"
            ),
            parse_mode="MarkdownV2",
        )
        return

    deleted = await delete_profile_for_user(store, update.effective_user.id)
    if not deleted:
        await update.message.reply_text(
            escape_md("삭제할 프로필이 없습니다. /setup_hoot 또는 /register 로 시작하세요."),
            parse_mode="MarkdownV2",
        )
        return

    await update.message.reply_text(
        escape_md(
            "🧹 프로필을 초기화했습니다.\n\n"
            "다시 시작하려면:\n"
            "  /setup_hoot\n"
            "또는\n"
            "  /register"
        ),
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

    existing = await store.get_profile_by_telegram_user(user_id)
    if existing:
        await update.message.reply_text(
            escape_md(
                f"이미 '{existing.company_name}' 프로필이 있습니다.\n"
                f"다시 등록하면 업데이트됩니다.\n\n"
                f"1/7 회사/프로젝트 이름을 입력하세요:"
            ),
            parse_mode="MarkdownV2",
        )
    else:
        await update.message.reply_text(
            escape_md(
                "프로필 등록을 시작합니다.\n"
                "정보를 기반으로 맞춤 펀딩을 추천해드립니다.\n\n"
                "1/7 회사 또는 프로젝트 이름을 입력하세요:"
            ),
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
        escape_md(f"2/7 현재 단계를 입력하세요:\n({stages})"),
        parse_mode="MarkdownV2",
    )
    return STAGE


async def reg_stage(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """단계 입력 → 분야 질문."""
    stage_input = update.message.text.strip().lower()

    valid_stages = {s.value for s in CompanyStage}
    if stage_input not in valid_stages:
        await update.message.reply_text(
            escape_md(
                f"유효하지 않은 단계입니다.\n다시 입력하세요: {', '.join(valid_stages)}"
            ),
            parse_mode="MarkdownV2",
        )
        return STAGE

    context.user_data["reg"]["stage"] = stage_input

    await update.message.reply_text(
        escape_md(
            "3/7 관련 분야를 쉼표로 구분하여 입력하세요:\n\n"
            "예시: ai, crypto, defi, gaming, nft, depin\n"
            "더 구체적으로: ai_infra, decentralized_ai, distributed_compute"
        ),
        parse_mode="MarkdownV2",
    )
    return SECTORS


async def reg_sectors(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """분야 입력 → 생태계 질문."""
    tags = [
        t.strip().lower().replace(" ", "_")
        for t in update.message.text.split(",")
        if t.strip()
    ]
    context.user_data["reg"]["sector_tags"] = tags

    await update.message.reply_text(
        escape_md(
            "4/7 타겟 블록체인 생태계를 쉼표로 입력하세요:\n\n"
            "예시: ethereum, solana, arbitrum, base, near\n"
            "기타: monad, bittensor, polygon, avalanche, sui\n\n"
            "없으면 '없음' 입력"
        ),
        parse_mode="MarkdownV2",
    )
    return ECOSYSTEMS


async def reg_ecosystems(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """생태계 입력 → 프로젝트명 질문."""
    text = update.message.text.strip()
    if text in ("없음", "none", "x", "X"):
        ecosystems = []
    else:
        ecosystems = [
            e.strip().lower()
            for e in text.split(",")
            if e.strip()
        ]
    context.user_data["reg"]["target_ecosystems"] = ecosystems

    await update.message.reply_text(
        escape_md("5/7 대표 프로젝트 이름을 입력하세요:"),
        parse_mode="MarkdownV2",
    )
    return PROJECT_NAME


async def reg_project_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """프로젝트명 → 프로젝트 태그 질문."""
    context.user_data["reg"]["project_name"] = update.message.text.strip()

    await update.message.reply_text(
        escape_md(
            "6/7 프로젝트 관련 태그를 쉼표로 입력하세요:\n\n"
            "예시: ai_infra, blockchain, distributed_compute\n"
            "예시: defi, trading, analytics"
        ),
        parse_mode="MarkdownV2",
    )
    return PROJECT_TAGS


async def reg_project_tags(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """프로젝트 태그 → 설명 질문."""
    tags = [
        t.strip().lower().replace(" ", "_")
        for t in update.message.text.split(",")
        if t.strip()
    ]
    context.user_data["reg"]["project_tags"] = tags

    await update.message.reply_text(
        escape_md(
            "7/7 프로젝트를 한 줄로 설명해주세요:\n\n"
            "예시: AI 기반 분산 컴퓨팅 네트워크로 개인 모델 학습 지원\n"
            "예시: DeFi 프로토콜 기반 자동화 트레이딩 인프라"
        ),
        parse_mode="MarkdownV2",
    )
    return DESCRIPTION


async def reg_description(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """설명 입력 → 확인."""
    context.user_data["reg"]["description"] = update.message.text.strip()

    reg = context.user_data["reg"]
    eco_str = ", ".join(reg.get("target_ecosystems", [])) or "없음"
    summary = (
        f"확인해 주세요:\n\n"
        f"  회사명: {reg['company_name']}\n"
        f"  단계: {reg['stage']}\n"
        f"  분야: {', '.join(reg['sector_tags'])}\n"
        f"  생태계: {eco_str}\n"
        f"  프로젝트: {reg['project_name']}\n"
        f"  태그: {', '.join(reg['project_tags'])}\n"
        f"  설명: {reg['description']}\n\n"
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
    if text not in ("확인", "yes", "y", "ㅇ", "ok"):
        await update.message.reply_text(
            escape_md("등록이 취소되었습니다."),
            parse_mode="MarkdownV2",
        )
        return ConversationHandler.END

    store: EntityStore = context.bot_data["store"]
    user_id = update.effective_user.id
    reg = context.user_data["reg"]

    existing = await store.get_profile_by_telegram_user(user_id)

    projects = [{
        "name": reg["project_name"],
        "priority": 1,
        "tags": reg["project_tags"],
    }]

    if existing:
        await store.update_company_profile(
            existing.id,
            company_name=reg["company_name"],
            stage=CompanyStage(reg["stage"]),
            sector_tags=reg["sector_tags"],
            target_ecosystems=reg.get("target_ecosystems", []),
            product_summary=reg.get("description", ""),
            projects=projects,
        )
        profile_id = existing.id
    else:
        profile = CompanyProfile(
            id=generate_id("cp_"),
            company_name=reg["company_name"],
            stage=CompanyStage(reg["stage"]),
            sector_tags=reg["sector_tags"],
            target_ecosystems=reg.get("target_ecosystems", []),
            product_summary=reg.get("description", ""),
            projects=projects,
            telegram_user_id=user_id,
        )
        await store.create_company_profile(profile)
        profile_id = profile.id

    await update.message.reply_text(
        escape_md(
            f"✅ 프로필이 등록되었습니다!\n\n"
            f"이제 /funding 으로 맞춤 펀딩 추천을 받으세요.\n"
            f"/discover 로 웹 심층 탐색도 가능합니다."
        ),
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
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, reg_company_name
                ),
            ],
            STAGE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, reg_stage
                ),
            ],
            SECTORS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, reg_sectors
                ),
            ],
            ECOSYSTEMS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, reg_ecosystems
                ),
            ],
            PROJECT_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, reg_project_name
                ),
            ],
            PROJECT_TAGS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, reg_project_tags
                ),
            ],
            DESCRIPTION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, reg_description
                ),
            ],
            CONFIRM: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, reg_confirm
                ),
            ],
        },
        fallbacks=[CommandHandler("cancel", reg_cancel)],
    )
