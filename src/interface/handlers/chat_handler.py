"""
Funding Intelligence Agent — Natural Language Chat Handler.

슬래시 커맨드 없이 자연어로 대화.

유저: "나는 AI 분산 컴퓨팅 프로젝트를 하고 있어. ethereum이랑 solana 생태계 타겟."
봇:  → 프로필 자동 생성 → 즉시 펀딩 추천

유저: "펀딩 추천해줘"
봇:  → 기존 프로필로 /funding 실행

유저: "더 찾아줘" / "웹에서 검색해"
봇:  → /discover 실행
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from src.core.config import config
from src.core.profile_identity import (
    extract_name_from_text as shared_extract_name_from_text,
    is_generic_name as shared_is_generic_name,
    known_project_names as shared_known_project_names,
    merge_projects,
    merge_unique_strings,
    primary_project_name as shared_primary_project_name,
    repair_profile_identity,
    resolve_profile_draft,
)
from src.core.types import CompanyProfile, generate_id
from src.db.entity_store import EntityStore
from src.interface.card_renderer import escape_md
from src.interface.discovery_runtime import send_source_lead_intake
from src.interface.handlers.funding_handler import _handle_funding, _load_profile
from src.interface.handlers.research_handler import (
    send_funding_for_project,
    send_funding_map,
    send_org_dossier,
)
from src.research.dossier_builder import load_ecosystem_graph

logger = structlog.get_logger()

# ============================================================
# Intent Detection Prompt
# ============================================================

INTENT_PROMPT = """You are a funding recommendation bot assistant.
Analyze the user's message and determine:
1. intent: what the user wants
2. profile_info: any project/company info mentioned

INTENTS:
- "register": User is describing their project/company (extract profile info)
- "funding": User wants funding recommendations
- "funding_for_project": User wants a project-specific actionable funding list
- "funding_map": User wants a project-level funding map or ecosystem landscape
- "discover": User wants deeper web search for more opportunities
- "org": User wants an organization dossier
- "profile": User wants to see their profile
- "help": User needs help or greeting
- "other": Unrelated message

If intent is "register", extract these fields from the message:
- company_name: company or project name (string, null if not mentioned)
- stage: one of "idea", "mvp", "growth", "scaling" (null if not clear)
- sector_tags: list of relevant sectors (e.g., ["ai", "crypto", "defi"])
- target_ecosystems: blockchain ecosystems (e.g., ["ethereum", "solana"])
- project_description: one-line description of the project
- project_name: specific project name if different from company

If intent is "funding_for_project" or "funding_map", also extract:
- project_name: target project name if mentioned

If intent is "org", also extract:
- organization_name: organization name if mentioned

User message: {message}

Return ONLY valid JSON:
{{"intent": "...", "profile_info": {{...}}}}
"""

# ============================================================
# 키워드 기반 빠른 분류 (LLM 호출 전 필터)
# ============================================================

FUNDING_KEYWORDS = {"펀딩", "추천해", "투자", "grant", "funding", "accelerator", "지원금", "매칭해"}
# "더" 단독은 너무 흔한 단어 → 복합 패턴만 사용
DISCOVER_PHRASES = ["더 찾아", "더찾아", "심층 탐색", "웹에서 검색", "웹 검색", "discover", "깊이 검색", "많이 찾아"]
PROFILE_KEYWORDS = {"프로필", "내정보", "profile", "내 정보"}
HELP_KEYWORDS = {"도움", "help", "뭐해", "안녕", "하이", "hello", "hi", "시작"}
REGISTER_SIGNALS = {"프로젝트", "회사", "우리", "만들고", "개발", "빌딩", "building", "하고있"}
FUNDING_MAP_KEYWORDS = {"funding map", "funding_map", "펀딩맵", "맵", "랜드스케이프", "landscape"}
PROJECT_ROUTE_PHRASES = {
    "기준", "지금 낼", "낼 수", "지원 가능한", "우선순위", "액션 리스트", "actionable",
    "top funding", "best funding", "맞는 funding", "맞는 펀딩",
}
ORG_ROUTE_KEYWORDS = {"어떤 곳", "어떤곳", "뭐하는", "정리해줘", "정리해 줘", "설명해줘", "설명해 줘", "분석해줘", "분석해 줘", "dossier", "도시어"}
URL_PATTERN = re.compile(r"https?://[^\s<>()]+")
LEAD_URL_HOST_TOKENS = (
    "docs.google.com/forms",
    "forms.gle",
    "tally.so",
    "typeform.com",
    "airtable.com",
    "cal.com",
    "calendly.com",
    "lu.ma",
)
LEAD_URL_PATH_TOKENS = (
    "apply",
    "application",
    "builder",
    "grant",
    "accelerator",
    "competition",
    "hackathon",
    "pitch",
    "funding",
)
LEAD_TEXT_KEYWORDS = {
    "apply", "application", "applications close", "applications open",
    "grant", "grants", "accelerator", "builder program", "demo day",
    "equity free", "check size", "funding", "investment", "pitch competition",
    "지원", "지원금", "지원 가능", "그랜트", "액셀러레이터", "투자", "대회",
}


@dataclass
class StructuredChatRoute:
    intent: str
    project_name: str | None = None
    organization_name: str | None = None
    ranking_intent: str = "default"


def _normalize_chat_text(text: str | None) -> str:
    return " ".join((text or "").strip().lower().split())


def _is_generic_name_candidate(value: str | None) -> bool:
    return shared_is_generic_name(value)


def _primary_project_name(profile: CompanyProfile | None) -> str | None:
    return shared_primary_project_name(profile)


def _known_project_names(profile: CompanyProfile | None) -> list[str]:
    return shared_known_project_names(profile)


def _known_org_names() -> list[str]:
    graph = load_ecosystem_graph()
    names: list[str] = []
    for org in graph.get("organizations", []):
        for candidate in [org.get("name", ""), *(org.get("aliases") or [])]:
            candidate = str(candidate).strip()
            if candidate and candidate not in names:
                names.append(candidate)
    return names


def _extract_name_from_text(text: str, candidates: list[str]) -> str | None:
    return shared_extract_name_from_text(text, candidates)


def _extract_urls(text: str | None) -> list[str]:
    urls: list[str] = []
    for match in URL_PATTERN.findall(text or ""):
        cleaned = match.rstrip(".,);]>\"'")
        if cleaned and cleaned not in urls:
            urls.append(cleaned)
    return urls


def _looks_like_funding_lead_message(
    text: str,
    urls: list[str],
) -> bool:
    if not urls:
        return False

    normalized = _normalize_chat_text(text)
    lower_urls = [url.lower() for url in urls]

    if any(host in url for host in LEAD_URL_HOST_TOKENS for url in lower_urls):
        return True

    if any(token in normalized for token in LEAD_TEXT_KEYWORDS):
        return True

    return any(token in url for token in LEAD_URL_PATH_TOKENS for url in lower_urls)


def _infer_ranking_intent(text: str) -> str:
    normalized = _normalize_chat_text(text)
    if any(keyword in normalized for keyword in ("긴급", "급한", "마감")):
        return "urgent"
    if any(keyword in normalized for keyword in ("큰 돈", "금액 큰", "체크 큰", "규모 큰")):
        return "biggest_check"
    if any(keyword in normalized for keyword in ("지금 낼", "바로 낼", "즉시 지원", "ready now")):
        return "ready_now"
    if any(keyword in normalized for keyword in ("가장 맞", "가장 잘 맞", "제일 맞", "best fit")):
        return "best_fit"
    return "default"


def _detect_structured_route(
    text: str,
    profile: CompanyProfile | None,
) -> StructuredChatRoute | None:
    normalized = _normalize_chat_text(text)
    project_name = _extract_name_from_text(text, _known_project_names(profile))
    org_name = _extract_name_from_text(text, _known_org_names())
    primary_project = _primary_project_name(profile)

    if any(keyword in normalized for keyword in FUNDING_MAP_KEYWORDS):
        return StructuredChatRoute(
            intent="funding_map",
            project_name=project_name or primary_project,
        )

    if org_name and any(keyword in normalized for keyword in ORG_ROUTE_KEYWORDS):
        return StructuredChatRoute(
            intent="org",
            organization_name=org_name,
        )

    if project_name and (
        any(keyword in normalized for keyword in PROJECT_ROUTE_PHRASES)
        or any(keyword in normalized for keyword in FUNDING_KEYWORDS)
    ):
        return StructuredChatRoute(
            intent="funding_for_project",
            project_name=project_name,
            ranking_intent=_infer_ranking_intent(text),
        )

    if primary_project and any(keyword in normalized for keyword in ("우리 기준", "우리 프로젝트", "지금 낼 수 있는 것", "action list", "actionable")):
        return StructuredChatRoute(
            intent="funding_for_project",
            project_name=primary_project,
            ranking_intent=_infer_ranking_intent(text),
        )

    return None


async def chat_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """자연어 메시지 처리 — 의도 파악 → 자동 라우팅."""
    text = update.message.text.strip()
    if not text:
        return

    store: EntityStore = context.bot_data["store"]
    text_lower = text.lower()
    current_profile = repair_profile_identity(
        await store.get_profile_by_telegram_user(update.effective_user.id)
    )

    # ── 키워드 빠른 분류 ──
    if any(kw in text_lower for kw in HELP_KEYWORDS) and len(text) < 20:
        await _send_help(update)
        return

    if any(kw in text_lower for kw in PROFILE_KEYWORDS):
        await _show_profile(update, store)
        return

    source_urls = _extract_urls(text)
    if _looks_like_funding_lead_message(text, source_urls):
        await send_source_lead_intake(
            update,
            context,
            source_urls=source_urls,
            message_text=text,
        )
        return

    structured_route = _detect_structured_route(text, current_profile)
    if structured_route is not None:
        if structured_route.intent == "funding_for_project":
            await send_funding_for_project(
                update,
                context,
                requested_project=structured_route.project_name,
                intent=structured_route.ranking_intent,
            )
            return
        if structured_route.intent == "funding_map":
            await send_funding_map(
                update,
                context,
                requested_project=structured_route.project_name,
            )
            return
        if structured_route.intent == "org" and structured_route.organization_name:
            await send_org_dossier(
                update,
                context,
                query=structured_route.organization_name,
            )
            return

    if any(phrase in text_lower for phrase in DISCOVER_PHRASES):
        profile = await _load_profile(store, update.effective_user.id)
        if profile:
            await _handle_funding(update, context, mode="deep")
        else:
            await _ask_for_profile(update)
        return

    if any(kw in text_lower for kw in FUNDING_KEYWORDS) and not any(
        kw in text_lower for kw in REGISTER_SIGNALS
    ):
        profile = await _load_profile(store, update.effective_user.id)
        if profile:
            await _handle_funding(update, context, mode="fast")
        else:
            await _ask_for_profile(update)
        return

    # ── LLM 의도 분류 + 프로필 추출 ──
    intent_data = await _classify_with_llm(text)

    if intent_data is None:
        # LLM 실패 → 키워드 폴백
        if any(kw in text_lower for kw in REGISTER_SIGNALS):
            intent_data = {"intent": "register", "profile_info": {}}
        else:
            await _send_help(update)
            return

    intent = intent_data.get("intent", "other")
    profile_info = intent_data.get("profile_info", {})

    if intent == "register" or (
        intent == "other" and profile_info.get("sector_tags")
    ):
        # 프로젝트 정보가 포함된 메시지 → 프로필 자동 생성 → 바로 추천
        await _auto_register_and_recommend(
            update, context, store, text, profile_info
        )

    elif intent == "funding":
        profile = await _load_profile(store, update.effective_user.id)
        if profile:
            await _handle_funding(update, context, mode="fast")
        else:
            await _ask_for_profile(update)

    elif intent == "funding_for_project":
        await send_funding_for_project(
            update,
            context,
            requested_project=profile_info.get("project_name"),
            intent=_infer_ranking_intent(text),
        )

    elif intent == "funding_map":
        await send_funding_map(
            update,
            context,
            requested_project=profile_info.get("project_name"),
        )

    elif intent == "discover":
        profile = await _load_profile(store, update.effective_user.id)
        if profile:
            await _handle_funding(update, context, mode="deep")
        else:
            await _ask_for_profile(update)

    elif intent == "org":
        org_name = profile_info.get("organization_name") or profile_info.get("company_name")
        if org_name:
            await send_org_dossier(update, context, query=org_name)
        else:
            await _send_help(update)

    elif intent == "profile":
        await _show_profile(update, store)

    elif intent == "help":
        await _send_help(update)

    else:
        await _send_help(update)


# ============================================================
# 자동 프로필 생성 + 즉시 추천
# ============================================================

async def _auto_register_and_recommend(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    store: EntityStore,
    original_text: str,
    profile_info: dict,
) -> None:
    """자연어에서 추출한 정보로 프로필 자동 생성 → 바로 펀딩 추천."""
    user_id = update.effective_user.id
    existing = await store.get_profile_by_telegram_user(user_id)
    draft = resolve_profile_draft(
        original_text=original_text,
        profile_info=profile_info,
        existing_profile=existing,
    )

    if draft is None:
        await update.message.reply_text(
            escape_md(
                "프로젝트 이름이 명확하지 않아 자동 등록을 건너뜁니다.\n"
                "예시처럼 프로젝트명을 함께 말해주세요:\n"
                "  • HOOT는 distributed compute 기반 AI infra 프로젝트야\n"
                "또는 /register 로 직접 등록하세요."
            ),
            parse_mode="MarkdownV2",
        )
        return

    company_name = draft.company_name
    project_name = draft.project_name
    normalized_tags = draft.sector_tags
    ecosystems = draft.target_ecosystems
    description = draft.description

    if existing:
        merged_projects = merge_projects(existing.projects, project_name, normalized_tags)
        await store.update_company_profile(
            existing.id,
            company_name=company_name,
            stage=draft.stage,
            sector_tags=merge_unique_strings(normalized_tags, existing.sector_tags),
            target_ecosystems=merge_unique_strings(ecosystems, existing.target_ecosystems),
            product_summary=description,
            projects=merged_projects,
        )
        action = "업데이트"
    else:
        profile = CompanyProfile(
            id=generate_id("cp_"),
            company_name=company_name,
            stage=draft.stage,
            sector_tags=normalized_tags,
            target_ecosystems=ecosystems,
            product_summary=description,
            projects=[{
                "name": project_name,
                "priority": 1,
                "tags": normalized_tags[:5],
            }],
            telegram_user_id=user_id,
        )
        await store.create_company_profile(profile)
        action = "등록"

    # 프로필 요약 보여주기
    eco_str = ", ".join(ecosystems) if ecosystems else "없음"
    summary = (
        f"✅ 프로필 {action} 완료!\n\n"
        f"  📛 {company_name}\n"
        f"  🏷 분야: {', '.join(normalized_tags)}\n"
        f"  🌐 생태계: {eco_str}\n"
        f"  📝 {description[:60]}\n\n"
        f"맞춤 펀딩을 찾고 있습니다..."
    )
    await update.message.reply_text(
        escape_md(summary),
        parse_mode="MarkdownV2",
    )

    # 바로 펀딩 추천
    await _handle_funding(update, context, mode="fast")


# ============================================================
# LLM 의도 분류
# ============================================================

async def _classify_with_llm(text: str) -> dict | None:
    """Fast LLM으로 의도 분류 + 프로필 정보 추출."""
    if not config.groq_key:
        return None

    try:
        from groq import Groq

        client = Groq(api_key=config.groq_key)
        prompt = INTENT_PROMPT.format(message=text[:500])

        response = client.chat.completions.create(
            model=config.llm_model_fast,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.1,
        )

        raw = response.choices[0].message.content.strip()
        return _extract_json(raw)

    except Exception as e:
        logger.warning("chat.classify_error", error=str(e))
        return None


def _extract_json(text: str) -> dict | None:
    """LLM 응답에서 JSON 추출."""
    try:
        # 코드블록 제거
        if "```" in text:
            blocks = text.split("```")
            for block in blocks[1:]:
                cleaned = block.strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
                if cleaned.startswith("{"):
                    text = cleaned
                    break

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])
    except (json.JSONDecodeError, IndexError):
        pass
    return None


# ============================================================
# 헬퍼
# ============================================================

async def _send_help(update: Update) -> None:
    """도움말 메시지."""
    await update.message.reply_text(
        escape_md(
            "🤖 Funding Intelligence Agent\n\n"
            "프로젝트 정보를 알려주시면 맞춤 펀딩을 추천해드립니다.\n\n"
            "예시:\n"
            '  "나는 AI 분산 컴퓨팅 프로젝트를 하고 있어. '
            'ethereum이랑 solana 타겟."\n\n'
            '  "DeFi 트레이딩 인프라 만들고 있는데 '
            'grant 추천해줘"\n\n'
            "그 외 명령어:\n"
            "  펀딩 추천해줘 → 즉시 추천\n"
            "  HOOT 기준 지금 낼 수 있는 것 정리해줘 → 프로젝트 액션 리스트\n"
            "  HOOT funding map 보여줘 → 프로젝트별 펀딩 맵\n"
            "  Monad 어떤 곳이야 → 조직 dossier\n"
            "  더 찾아줘 → 웹 심층 탐색\n"
            "  내 프로필 → 등록 정보 확인\n"
        ),
        parse_mode="MarkdownV2",
    )


async def _ask_for_profile(update: Update) -> None:
    """프로필 없을 때 안내."""
    await update.message.reply_text(
        escape_md(
            "아직 프로필이 없습니다.\n\n"
            "프로젝트를 설명해주세요! 예시:\n\n"
            '"AI 기반 분산 컴퓨팅 네트워크를 만들고 있어. '
            'ethereum이랑 solana 생태계 타겟이고 MVP 단계야."'
        ),
        parse_mode="MarkdownV2",
    )


async def _show_profile(update: Update, store: EntityStore) -> None:
    """프로필 조회."""
    user_id = update.effective_user.id
    profile = repair_profile_identity(await store.get_profile_by_telegram_user(user_id))

    if profile is None:
        await _ask_for_profile(update)
        return

    eco_str = ", ".join(profile.target_ecosystems) if profile.target_ecosystems else "없음"
    lines = [
        f"👤 {profile.company_name}",
        f"   단계: {profile.stage.value if profile.stage else 'N/A'}",
        f"   분야: {', '.join(profile.sector_tags) if profile.sector_tags else 'N/A'}",
        f"   생태계: {eco_str}",
    ]
    if profile.product_summary:
        lines.append(f"   📝 {profile.product_summary[:60]}")

    lines.append("")
    lines.append("'펀딩 추천해줘'로 맞춤 추천 받기")

    await update.message.reply_text(
        escape_md("\n".join(lines)),
        parse_mode="MarkdownV2",
    )
