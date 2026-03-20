"""
Funding Intelligence Agent — Research Output Handlers.

/funding_for_project [project] [intent]
/funding_map [project]
/org <name>

기존 autoresearch / funding scaffold를 Telegram user-facing output으로 연결한다.
"""

from __future__ import annotations

from types import SimpleNamespace

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from src.core.config import config
from src.core.profiles import get_default_profile
from src.core.types import DossierCard, OpportunityCard, normalize_org_name
from src.db.entity_store import EntityStore
from src.interface.card_renderer import (
    escape_md,
    render_error,
    render_funding_map,
    render_funding_results,
    render_org_dossier,
)
from src.interface.handlers.funding_handler import (
    INTENT_ALIASES,
    VALID_INTENTS,
    _load_profile,
)
from src.interface.opportunity_filters import filter_current_cards, is_actionable_card
from src.research.actionable_funding_service import (
    build_actionable_funding_view,
    matches_project as shared_matches_project,
    primary_project_name as shared_primary_project_name,
)
from src.research.dossier_builder import (
    build_org_dossier,
    build_project_funding_map,
    compute_dossier_fact_completeness,
    compute_funding_map_coverage,
    enrich_cards_from_registry,
    is_snapshot_current,
    load_ecosystem_graph,
    load_program_registry,
)
from src.research.strategy_composer import compose_actionable_entries
from src.search.research_goal_router import GoalType

logger = structlog.get_logger()

INTENT_LABELS: dict[str, str] = {
    "default": "추천 순위",
    "urgent": "마감 임박",
    "biggest_check": "최대 금액",
    "ready_now": "지금 지원 가능",
    "best_fit": "최고 적합도",
}

def _primary_project_name(profile) -> str:
    return shared_primary_project_name(profile, fallback="내 프로젝트")


def _normalize_text(text: str | None) -> str:
    return " ".join((text or "").strip().lower().split())


def _split_project_and_intent(args: list[str]) -> tuple[str | None, str]:
    if not args:
        return None, "default"

    maybe_intent = INTENT_ALIASES.get(args[-1].lower(), args[-1].lower())
    if maybe_intent in VALID_INTENTS:
        project_name = " ".join(args[:-1]).strip() or None
        return project_name, maybe_intent

    return " ".join(args).strip(), "default"


def _matches_project(result_project_name: str | None, requested_project: str | None) -> bool:
    return shared_matches_project(result_project_name, requested_project)


async def _resolve_profile_for_project(
    store: EntityStore,
    telegram_user_id: int,
    project_name: str | None,
):
    profile = await _load_profile(store, telegram_user_id)
    if not project_name:
        return profile

    default_profile = get_default_profile(project_name)
    if default_profile is not None:
        return default_profile
    return profile


def _filter_cards_to_actionable(cards: list[OpportunityCard], project_name: str) -> list[OpportunityCard]:
    current_cards = filter_current_cards(cards)
    entries = compose_actionable_entries(project_name=project_name, snapshots=current_cards, top_n=10)
    ready_keys = {
        (entry.organization, entry.program, entry.apply_url or "")
        for entry in entries
        if entry.ready
    }
    if not ready_keys:
        return []

    actionable = [
        card
        for card in current_cards
        if (card.organization, card.program, card.apply_url or "") in ready_keys
    ]
    return actionable[:10]


def _org_name_candidates(text: str) -> list[str]:
    normalized = normalize_org_name(text)
    return [text.strip(), normalized]


async def _find_organization(store: EntityStore, query: str):
    for candidate in _org_name_candidates(query):
        if not candidate:
            continue
        org = await store.get_organization_by_name(candidate)
        if org is not None:
            return org

    normalized_query = normalize_org_name(query)
    organizations = await store.list_organizations(limit=200)
    for org in organizations:
        haystacks = [
            normalize_org_name(org.display_name or ""),
            normalize_org_name(org.normalized_name or ""),
        ]
        if any(
            normalized_query == haystack or normalized_query in haystack
            for haystack in haystacks
            if haystack
        ):
            return org
    return None


async def _build_org_cards(store: EntityStore, org_id: str) -> list[OpportunityCard]:
    cards: list[OpportunityCard] = []
    programs = await store.list_programs(org_id=org_id, limit=20)
    org = await store.get_organization(org_id)
    org_name = org.display_name if org and org.display_name else (org.normalized_name if org else "Unknown")

    for program in programs:
        opp = await store.get_latest_opportunity_by_program(program.id)
        if opp is None:
            continue

        card = OpportunityCard(
            organization=org_name,
            program=program.display_name or program.normalized_name,
            category=program.category.value,
            status=opp.status.value,
            apply_url=opp.apply_url or "",
            confidence=opp.fact_confidence,
            deadline=opp.deadline_at.isoformat()[:10] if opp.deadline_at else None,
            days_left=opp.days_left,
            budget=opp.budget_note,
            source_url=program.program_url,
            description=program.description,
        )
        if is_snapshot_current(card):
            if is_actionable_card(card):
                cards.append(card)
    return cards


async def send_funding_for_project(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    requested_project: str | None = None,
    intent: str = "default",
) -> None:
    """프로젝트 전용 actionable funding view 전송."""
    store: EntityStore = context.bot_data["store"]
    profile = await _resolve_profile_for_project(
        store,
        update.effective_user.id,
        requested_project,
    )
    project_name = requested_project or _primary_project_name(profile)

    try:
        view = await build_actionable_funding_view(
            store=store,
            config=config,
            profile=profile,
            requested_project=project_name,
            intent=intent,
            top_n=15,
            mode="fast",
        )
        result = view.result
        actionable_cards = view.actionable_cards

        if not actionable_cards:
            await update.message.reply_text(
                escape_md(f"{project_name} 기준 actionable funding 결과가 없습니다."),
                parse_mode="MarkdownV2",
            )
            return

        if view.fallback_used:
            await update.message.reply_text(
                escape_md(
                    f"{project_name} 전용 project label이 부족해서 전체 상위 결과를 대신 표시합니다."
                ),
                parse_mode="MarkdownV2",
            )

        text = render_funding_results(
            cards=actionable_cards,
            project_name=project_name,
            intent=INTENT_LABELS.get(intent, intent),
            web_count=result.web_count,
            social_count=result.social_count,
            ref_count=result.reference_count,
            new_count=result.new_discovered,
            elapsed=result.elapsed_seconds,
        )
        await update.message.reply_text(
            text,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
        )
    except Exception as exc:
        logger.error("research_handler.funding_for_project.error", error=str(exc))
        await update.message.reply_text(render_error(), parse_mode="MarkdownV2")


async def funding_for_project_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/funding_for_project [project] [intent] — 프로젝트 전용 actionable funding view."""
    requested_project, intent = _split_project_and_intent(context.args or [])
    await send_funding_for_project(
        update,
        context,
        requested_project=requested_project,
        intent=intent,
    )


async def send_funding_map(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    requested_project: str | None = None,
) -> None:
    """project별 funding landscape 요약 전송."""
    store: EntityStore = context.bot_data["store"]
    profile = await _resolve_profile_for_project(
        store,
        update.effective_user.id,
        requested_project,
    )
    project_name = requested_project or _primary_project_name(profile)

    try:
        view = await build_actionable_funding_view(
            store=store,
            config=config,
            profile=profile,
            requested_project=project_name,
            goal_type=GoalType.FUNDING_MAP,
            intent="best_fit",
            top_n=15,
            mode="fast",
        )
        filtered_cards = [card for card in view.current_cards if is_actionable_card(card)]
        graph = load_ecosystem_graph()
        funding_map = build_project_funding_map(
            project_name=project_name,
            target_ecosystems=profile.target_ecosystems,
            graph=graph,
            ranked_snapshots=filtered_cards,
        )
        coverage = compute_funding_map_coverage(
            funding_map=funding_map,
            target_ecosystems=profile.target_ecosystems,
        )

        text = render_funding_map(
            project_name=project_name,
            funding_map=funding_map,
            cards=filtered_cards[:5],
            coverage=coverage,
        )
        await update.message.reply_text(
            text,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
        )
    except Exception as exc:
        logger.error("research_handler.funding_map.error", error=str(exc))
        await update.message.reply_text(render_error(), parse_mode="MarkdownV2")


async def funding_map_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/funding_map [project] — project별 funding landscape 요약."""
    requested_project = " ".join(context.args or []).strip() or None
    await send_funding_map(
        update,
        context,
        requested_project=requested_project,
    )


async def send_org_dossier(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    query: str,
) -> None:
    """organization dossier + tracked opportunities 전송."""
    store: EntityStore = context.bot_data["store"]
    if not query:
        await update.message.reply_text(
            escape_md("사용법: /org <organization name>"),
            parse_mode="MarkdownV2",
        )
        return

    try:
        org = await _find_organization(store, query)
        graph = load_ecosystem_graph()
        program_registry = load_program_registry()
        cards: list[OpportunityCard] = []
        org_name = query
        org_type = "unknown"
        website = None

        if org is not None:
            org_name = org.display_name or org.normalized_name or query
            org_type = org.org_type.value if org.org_type else "unknown"
            website = org.website_url
            cards = await _build_org_cards(store, org.id)
            cards = enrich_cards_from_registry(cards, program_registry)

        ranked_snapshots = [
            SimpleNamespace(
                organization=card.organization,
                program=card.program,
                apply_url=card.apply_url,
            )
            for card in cards
        ]
        dossier = build_org_dossier(
            org_name,
            graph,
            ranked_snapshots=ranked_snapshots,
            program_registry=program_registry,
        )
        completeness = compute_dossier_fact_completeness(dossier)

        if org is None and completeness == 0.0:
            await update.message.reply_text(
                escape_md(f"'{query}' 조직 정보를 찾지 못했습니다."),
                parse_mode="MarkdownV2",
            )
            return

        dossier_card = DossierCard(
            org_name=org_name,
            org_type=org_type,
            website=website or (dossier.official_urls[0] if dossier.official_urls else None),
            portfolio_count=len(dossier.portfolio_analogs) or None,
            focus_areas=dossier.ecosystems,
            decision_makers=dossier.mentors,
            confidence=completeness,
        )
        text = render_org_dossier(
            dossier=dossier,
            org_card=dossier_card,
            opportunity_cards=cards,
        )
        await update.message.reply_text(
            text,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True,
        )
    except Exception as exc:
        logger.error("research_handler.org.error", error=str(exc))
        await update.message.reply_text(render_error(), parse_mode="MarkdownV2")


async def org_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """/org <name> — organization dossier + tracked opportunities."""
    query = " ".join(context.args or []).strip()
    await send_org_dossier(update, context, query)
