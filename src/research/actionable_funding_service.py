from __future__ import annotations

from dataclasses import dataclass, field

from src.core.config import Config
from src.core.profile_identity import primary_project_name
from src.core.types import CompanyProfile, MatchingOutput, OpportunityCard, OutputStatus
from src.db.entity_store import EntityStore
from src.interface.opportunity_filters import filter_current_cards
from src.research.dossier_builder import enrich_cards_from_registry, load_program_registry
from src.research.runtime_reflection import resolve_runtime_reflection_seeds
from src.research.strategy_composer import StrategyEntry, compose_actionable_entries
from src.search.research_goal_router import GoalType
from src.search.research_reflection import ReflectionSeeds
from src.search.funding_orchestrator import FundingSearchOrchestrator, FundingSearchResult


@dataclass
class ActionableFundingView:
    project_name: str
    result: FundingSearchResult
    reflection_seeds: ReflectionSeeds = field(default_factory=ReflectionSeeds)
    ranked_results: list[MatchingOutput] = field(default_factory=list)
    cards: list[OpportunityCard] = field(default_factory=list)
    current_cards: list[OpportunityCard] = field(default_factory=list)
    actionable_cards: list[OpportunityCard] = field(default_factory=list)
    strategy_entries: list[StrategyEntry] = field(default_factory=list)
    fallback_used: bool = False


def matches_project(result_project_name: str | None, requested_project: str | None) -> bool:
    if not requested_project:
        return True
    if not result_project_name:
        return False
    return " ".join(result_project_name.strip().lower().split()) == " ".join(
        requested_project.strip().lower().split()
    )


def _endpoint_priority(url: str | None) -> tuple[int, str]:
    normalized = (url or "").lower()
    if any(host in normalized for host in ("typeform.com", "docs.google.com/forms", "airtable.com", "hsforms.com")):
        return (0, normalized)
    if any(token in normalized for token in ("apply", "application", "register", "form")):
        return (1, normalized)
    return (2, normalized)


async def ranked_to_cards(
    store: EntityStore,
    ranked: list[MatchingOutput],
) -> list[OpportunityCard]:
    cards: list[OpportunityCard] = []

    for mo in ranked:
        opp = await store.get_opportunity(mo.opportunity_id)
        if opp is None:
            continue

        program = await store.get_program(opp.program_id)
        org_name = "Unknown"
        prog_name = "Unknown"
        endpoints = await store.get_active_endpoints(opp.id)
        verified_apply_url = (
            sorted((endpoint.url for endpoint in endpoints if endpoint.url), key=_endpoint_priority)[0]
            if endpoints
            else (opp.apply_url or "")
        )

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
                apply_url=verified_apply_url,
                confidence=opp.fact_confidence,
                deadline=opp.deadline_at.isoformat()[:10] if opp.deadline_at else None,
                days_left=opp.days_left,
                budget=opp.budget_note,
                source_url=program.program_url if program else None,
                description=program.description if program else None,
                fit_score=mo.fit_score,
                priority_score=mo.priority_score,
                why_fit=mo.why_fit,
                next_action=mo.next_action,
            )
        )
        setattr(cards[-1], "_output_status", opp.output_status.value)
        setattr(cards[-1], "_has_active_endpoint", bool(endpoints))

    return cards


def _ready_card_keys(
    project_name: str,
    cards: list[OpportunityCard],
) -> tuple[set[tuple[str, str, str]], list[StrategyEntry]]:
    entries = compose_actionable_entries(project_name=project_name, snapshots=cards, top_n=10)
    ready_keys = {
        (entry.organization, entry.program, entry.apply_url or "")
        for entry in entries
        if entry.ready
    }
    return ready_keys, entries


async def build_actionable_funding_view(
    *,
    store: EntityStore,
    config: Config,
    profile: CompanyProfile,
    requested_project: str | None = None,
    goal_type: GoalType | str = GoalType.ACTIONABLE_STRATEGY,
    intent: str = "default",
    top_n: int = 15,
    mode: str = "fast",
) -> ActionableFundingView:
    project_name = requested_project or primary_project_name(profile, fallback="내 프로젝트")
    reflection_seeds = resolve_runtime_reflection_seeds(
        profile=profile,
        goal_type=goal_type,
        requested_project=project_name,
    )
    orchestrator = FundingSearchOrchestrator(store=store, config=config)
    result = await orchestrator.search_for_project(
        profile=profile,
        intent=intent,
        top_n=top_n,
        mode=mode,
        search_hints=reflection_seeds.search_hints or None,
        bootstrap_terms=reflection_seeds.bootstrap_terms or None,
    )

    ranked = [
        item for item in result.ranked_results if matches_project(item.project_name, project_name)
    ]
    fallback_used = False
    if not ranked:
        ranked = result.ranked_results
        fallback_used = True

    cards = await ranked_to_cards(store, ranked)
    cards = enrich_cards_from_registry(cards, load_program_registry())
    current_cards = [
        card
        for card in filter_current_cards(cards)
        if getattr(card, "_output_status", OutputStatus.PENDING.value) == OutputStatus.VERIFIED.value
        and getattr(card, "_has_active_endpoint", False)
    ]
    ready_keys, entries = _ready_card_keys(project_name, current_cards)
    actionable_cards = [
        card
        for card in current_cards
        if (card.organization, card.program, card.apply_url or "") in ready_keys
    ][:10]

    return ActionableFundingView(
        project_name=project_name,
        result=result,
        reflection_seeds=reflection_seeds,
        ranked_results=ranked,
        cards=cards,
        current_cards=current_cards,
        actionable_cards=actionable_cards,
        strategy_entries=entries,
        fallback_used=fallback_used,
    )
