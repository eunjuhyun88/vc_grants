"""
Funding Intelligence Agent — Card Renderer.

Telegram MarkdownV2 포맷 출력.
OpportunityCard → 텍스트 변환만 담당. LLM 호출 없음.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from src.core.types import DailyBriefData, DossierCard, OpportunityCard
from src.research.dossier_builder import FundingMap, OrganizationDossier, ProgramDossier

# ============================================================
# MarkdownV2 이스케이프
# ============================================================

# Telegram MarkdownV2에서 이스케이프해야 하는 특수문자
_ESCAPE_CHARS = r"_*[]()~`>#+-=|{}.!"


def escape_md(text: str) -> str:
    """Telegram MarkdownV2 특수문자 이스케이프."""
    return re.sub(r"([" + re.escape(_ESCAPE_CHARS) + r"])", r"\\\1", text)


def _is_stale_date_text(value: str | None) -> bool:
    text = (value or "").strip()
    if not text:
        return False

    for fmt in ("%Y-%m-%d", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date() < date.today()
        except ValueError:
            continue
    return False


# ============================================================
# Status 이모지 매핑
# ============================================================

STATUS_EMOJI: dict[str, str] = {
    "open": "🟢",
    "rolling": "🔵",
    "upcoming": "⏳",
    "closed": "🔴",
    "unknown": "⚪",
}

CATEGORY_LABEL: dict[str, str] = {
    "grant": "💰 Grant",
    "accelerator": "🚀 Accelerator",
    "vc_cohort": "🏦 VC Cohort",
    "builder_program": "🌱 Builder Program",
    "residency": "🏠 Residency",
    "fund": "💼 Fund",
    "hackathon_pipeline": "🏆 Hackathon Pipeline",
    "ecosystem_builder": "🌱 Ecosystem Builder",  # deprecated 호환
    # display bucket labels
    "grants": "💰 Grants",
    "cohorts": "🚀 Cohorts",
    "funds": "🏦 Funds",
}


# ============================================================
# 렌더링 함수
# ============================================================


def render_opportunity_card(card: OpportunityCard, index: int | None = None) -> str:
    """단일 OpportunityCard → Telegram MarkdownV2 텍스트."""
    lines: list[str] = []

    # 헤더
    status_emoji = STATUS_EMOJI.get(card.status, "⚪")
    cat_label = CATEGORY_LABEL.get(card.category, card.category)
    prefix = f"*{index}\\.*" if index is not None else "•"

    org_name = escape_md(card.organization)
    prog_name = escape_md(card.program)

    lines.append(f"{prefix} *{org_name}* — {prog_name}")
    lines.append(f"   {escape_md(cat_label)} │ {status_emoji} {escape_md(card.status.upper())}")

    # 예산
    if card.budget:
        lines.append(f"   💵 {escape_md(card.budget)}")

    # 마감일
    if card.deadline and not _is_stale_date_text(card.deadline) and (
        card.days_left is None or card.days_left >= 0
    ):
        deadline_text = escape_md(card.deadline)
        if card.days_left is not None:
            if card.days_left <= 3:
                lines.append(f"   ⏰ *{deadline_text}* \\(D\\-{card.days_left} 🔥\\)")
            elif card.days_left <= 7:
                lines.append(f"   ⏰ {deadline_text} \\(D\\-{card.days_left}\\)")
            else:
                lines.append(f"   📅 {deadline_text} \\(D\\-{card.days_left}\\)")
        else:
            lines.append(f"   📅 {deadline_text}")

    # Fit 데이터 (있을 때만)
    if card.fit_score is not None:
        fit_bar = _score_bar(card.fit_score)
        lines.append(f"   🎯 적합도: {fit_bar} {escape_md(f'{card.fit_score:.0%}')}")

    if card.priority_score is not None:
        pri_bar = _score_bar(card.priority_score)
        lines.append(f"   ⭐ 우선순위: {pri_bar} {escape_md(f'{card.priority_score:.0%}')}")

    if card.why_fit:
        lines.append(f"   💡 {escape_md(card.why_fit)}")

    if card.next_action:
        lines.append(f"   👉 {escape_md(card.next_action)}")

    # 프로그램 설명
    if card.description:
        lines.append(f"   📄 {escape_md(card.description[:80])}")

    # 신뢰도
    conf_text = f"신뢰도: {card.confidence:.0%}"
    lines.append(f"   🔍 {escape_md(conf_text)}")

    # 링크: 프로그램 정보 + 지원
    if card.source_url and card.apply_url and card.source_url != card.apply_url:
        lines.append(f"   🌐 [프로그램 정보]({card.source_url}) │ 🔗 [지원하기]({card.apply_url})")
    elif card.source_url:
        lines.append(f"   🌐 [프로그램 정보]({card.source_url})")
    elif card.apply_url:
        lines.append(f"   🔗 [지원하기]({card.apply_url})")

    return "\n".join(lines)


def render_ranked_list(
    cards: list[OpportunityCard],
    title: str = "펀딩 기회 목록",
    max_items: int = 10,
) -> str:
    """OpportunityCard 리스트 → 번호 매긴 Telegram 메시지."""
    if not cards:
        return render_empty()

    lines: list[str] = []
    lines.append(f"*{escape_md(title)}*")
    lines.append(f"_{escape_md(f'총 {len(cards)}건')}_")
    lines.append("")

    for i, card in enumerate(cards[:max_items], 1):
        lines.append(render_opportunity_card(card, index=i))
        lines.append("")  # 카드 간 간격

    if len(cards) > max_items:
        remaining = len(cards) - max_items
        lines.append(escape_md(f"... 외 {remaining}건"))

    return "\n".join(lines)


def render_dossier_card(dossier: DossierCard) -> str:
    """DossierCard → Telegram MarkdownV2 텍스트."""
    lines: list[str] = []

    lines.append(f"🏢 *{escape_md(dossier.org_name)}*")
    lines.append(f"   유형: {escape_md(dossier.org_type)}")

    if dossier.website:
        lines.append(f"   🌐 [웹사이트]({dossier.website})")

    if dossier.portfolio_count is not None:
        lines.append(f"   📊 포트폴리오: {escape_md(str(dossier.portfolio_count))}개")

    if dossier.avg_check_size:
        lines.append(f"   💵 평균 투자: {escape_md(dossier.avg_check_size)}")

    if dossier.focus_areas:
        areas = ", ".join(dossier.focus_areas[:5])
        lines.append(f"   🎯 집중 분야: {escape_md(areas)}")

    if dossier.decision_makers:
        makers = ", ".join(dossier.decision_makers[:3])
        lines.append(f"   👤 의사결정자: {escape_md(makers)}")

    conf_text = f"신뢰도: {dossier.confidence:.0%}"
    lines.append(f"   🔍 {escape_md(conf_text)}")

    return "\n".join(lines)


def render_daily_brief(brief: DailyBriefData) -> str:
    """DailyBriefData → Telegram 일일 브리핑 메시지."""
    lines: list[str] = []

    lines.append("📋 *일일 펀딩 브리핑*")
    lines.append("")

    # 긴급 마감
    if brief.deadline_soon:
        lines.append("🔥 *마감 임박*")
        for card in brief.deadline_soon[:3]:
            lines.append(render_opportunity_card(card))
            lines.append("")

    # 신규 발견
    if brief.new_today:
        lines.append("🆕 *오늘 새로 발견*")
        for card in brief.new_today[:3]:
            lines.append(render_opportunity_card(card))
            lines.append("")

    # Top 기회
    if brief.top_opportunities:
        lines.append("⭐ *Top 기회*")
        for card in brief.top_opportunities[:3]:
            lines.append(render_opportunity_card(card))
            lines.append("")

    # 변경사항
    if brief.changes:
        lines.append("📝 *변경사항*")
        for change in brief.changes[:5]:
            desc = change.get("description", "변경 발생")
            lines.append(f"  • {escape_md(desc)}")

    if not any([brief.deadline_soon, brief.new_today,
                brief.top_opportunities, brief.changes]):
        lines.append(escape_md("새로운 업데이트가 없습니다."))

    return "\n".join(lines)


def render_funding_results(
    cards: list[OpportunityCard],
    project_name: str = "HOOT",
    intent: str = "추천 순위",
    web_count: int = 0,
    social_count: int = 0,
    ref_count: int = 0,
    new_count: int = 0,
    elapsed: float = 0.0,
    max_items: int = 10,
) -> str:
    """통합 펀딩 검색 결과 → Telegram MarkdownV2 메시지.

    /funding 커맨드 전용 출력 포맷.
    """
    if not cards:
        return render_empty()

    lines: list[str] = []

    # 헤더
    lines.append(f"🏆 *TOP FUNDING FOR {escape_md(project_name)}*")
    lines.append(f"📊 Intent: {escape_md(intent)}")
    lines.append("")

    # 카드 렌더링
    for i, card in enumerate(cards[:max_items], 1):
        lines.append(render_opportunity_card(card, index=i))
        lines.append("")

    if len(cards) > max_items:
        remaining = len(cards) - max_items
        lines.append(escape_md(f"... 외 {remaining}건"))
        lines.append("")

    # 푸터: 출처 통계
    footer_parts: list[str] = []
    if web_count:
        footer_parts.append(f"웹 {web_count}")
    if social_count:
        footer_parts.append(f"소셜 {social_count}")
    if ref_count:
        footer_parts.append(f"참조 {ref_count}")

    if footer_parts:
        lines.append(f"📊 출처: {escape_md(' │ '.join(footer_parts))}")

    if new_count > 0:
        lines.append(f"🆕 새로 발견: {escape_md(str(new_count))}개")

    if elapsed > 0:
        lines.append(f"⏱ 검색 시간: {escape_md(f'{elapsed:.1f}초')}")

    return "\n".join(lines)


def render_funding_map(
    project_name: str,
    funding_map: FundingMap,
    cards: list[OpportunityCard] | None = None,
    coverage: float | None = None,
    max_items: int = 5,
) -> str:
    """Funding map 요약 → Telegram MarkdownV2 텍스트."""
    lines: list[str] = []

    lines.append(f"🗺 *FUNDING MAP FOR {escape_md(project_name)}*")
    if coverage is not None:
        lines.append(f"📐 커버리지: {escape_md(f'{coverage:.0%}')}")
    lines.append("")

    if funding_map.tier1_ecosystems:
        lines.append("🔴 *Tier 1 Ecosystems*")
        for name in funding_map.tier1_ecosystems:
            lines.append(f"• {escape_md(name)}")
        lines.append("")

    if funding_map.tier2_ecosystems:
        lines.append("🟠 *Tier 2 Ecosystems*")
        for name in funding_map.tier2_ecosystems:
            lines.append(f"• {escape_md(name)}")
        lines.append("")

    if funding_map.matched_ecosystems:
        lines.append("✅ *Matched Now*")
        for name in funding_map.matched_ecosystems[:8]:
            lines.append(f"• {escape_md(name)}")
        lines.append("")

    if funding_map.covered_target_ecosystems:
        covered = ", ".join(funding_map.covered_target_ecosystems)
        lines.append(f"🎯 타겟 커버: {escape_md(covered)}")
        lines.append("")

    if cards:
        lines.append("⭐ *현재 연결된 기회*")
        for index, card in enumerate(cards[:max_items], 1):
            status_emoji = STATUS_EMOJI.get(card.status, "⚪")
            line = (
                f"{index}\\. *{escape_md(card.organization)}* — {escape_md(card.program)} "
                f"{status_emoji}"
            )
            if card.deadline and not _is_stale_date_text(card.deadline) and (
                card.days_left is None or card.days_left >= 0
            ):
                line += f" │ {escape_md(card.deadline)}"
            lines.append(line)
            if card.description:
                lines.append(f"   📄 {escape_md(card.description[:120])}")
            if card.source_url and card.apply_url and card.source_url != card.apply_url:
                lines.append(
                    f"   🌐 [공식]({card.source_url}) │ 🔗 [지원]({card.apply_url})"
                )
            elif card.source_url:
                lines.append(f"   🌐 [공식]({card.source_url})")
            elif card.apply_url:
                lines.append(f"   🔗 [지원]({card.apply_url})")
        lines.append("")

    return "\n".join(lines).strip()


def _render_program_dossier_detail(program: ProgramDossier, index: int) -> list[str]:
    lines: list[str] = []
    header = f"{index}\\. *{escape_md(program.program)}*"
    if program.program_type:
        header += f" │ {escape_md(program.program_type)}"
    lines.append(header)
    if program.description:
        lines.append(f"   📄 {escape_md(program.description[:140])}")
    if program.deadline_text and not _is_stale_date_text(program.deadline_text):
        lines.append(f"   📅 {escape_md(program.deadline_text)}")
    detail_parts: list[str] = []
    if program.funding_range:
        detail_parts.append(f"Funding: {program.funding_range}")
    if program.status_note and program.status_note != program.deadline_text:
        detail_parts.append(program.status_note)
    if detail_parts:
        lines.append(f"   🧾 {escape_md(' │ '.join(detail_parts))}")
    if program.official_url and program.apply_url and program.official_url != program.apply_url:
        lines.append(
            f"   🌐 [공식]({program.official_url}) │ 🔗 [지원]({program.apply_url})"
        )
    elif program.official_url:
        lines.append(f"   🌐 [공식]({program.official_url})")
    elif program.apply_url:
        lines.append(f"   🔗 [지원]({program.apply_url})")
    return lines


def render_org_dossier(
    dossier: OrganizationDossier,
    org_card: DossierCard | None = None,
    opportunity_cards: list[OpportunityCard] | None = None,
    max_items: int = 5,
) -> str:
    """Organization dossier + 현재 기회 요약."""
    lines: list[str] = []
    org_name = org_card.org_name if org_card else dossier.organization

    lines.append(f"🏢 *{escape_md(org_name)}*")
    if org_card:
        lines.append(f"유형: {escape_md(org_card.org_type)}")
        if org_card.website:
            lines.append(f"🌐 [웹사이트]({org_card.website})")
        lines.append(f"🔍 신뢰도: {escape_md(f'{org_card.confidence:.0%}')}")

    if dossier.ecosystems:
        lines.append(f"생태계: {escape_md(', '.join(dossier.ecosystems[:6]))}")
    if dossier.programs:
        lines.append(f"프로그램: {escape_md(', '.join(dossier.programs[:6]))}")
    if dossier.partners:
        lines.append(f"파트너: {escape_md(', '.join(dossier.partners[:6]))}")
    if dossier.mentors:
        lines.append(f"멘토/연결: {escape_md(', '.join(dossier.mentors[:6]))}")
    if dossier.portfolio_analogs:
        lines.append(
            f"유사 포트폴리오: {escape_md(', '.join(dossier.portfolio_analogs[:6]))}"
        )
    if dossier.matched_programs:
        lines.append(
            f"현재 매칭된 프로그램: {escape_md(', '.join(dossier.matched_programs[:6]))}"
        )
    elif opportunity_cards:
        lines.append("현재 매칭된 프로그램: DB 기반 기회 확인")
    if dossier.official_urls:
        lines.append(f"공식 링크: {escape_md(', '.join(dossier.official_urls[:4]))}")

    if dossier.program_details:
        lines.append("")
        lines.append("📚 *대표 프로그램 / 코호트*")
        for index, program_detail in enumerate(dossier.program_details[:max_items], 1):
            lines.extend(_render_program_dossier_detail(program_detail, index))

    if opportunity_cards:
        lines.append("")
        lines.append("⭐ *현재 추적 중인 기회*")
        for index, card in enumerate(opportunity_cards[:max_items], 1):
            status_emoji = STATUS_EMOJI.get(card.status, "⚪")
            line = (
                f"{index}\\. {status_emoji} *{escape_md(card.program)}*"
            )
            if card.deadline and not _is_stale_date_text(card.deadline) and (
                card.days_left is None or card.days_left >= 0
            ):
                line += f" │ {escape_md(card.deadline)}"
            lines.append(line)
            if card.description:
                lines.append(f"   📄 {escape_md(card.description[:120])}")
            if card.source_url and card.apply_url and card.source_url != card.apply_url:
                lines.append(
                    f"   🌐 [공식]({card.source_url}) │ 🔗 [지원]({card.apply_url})"
                )
            elif card.source_url:
                lines.append(f"   🌐 [공식]({card.source_url})")
            elif card.apply_url:
                lines.append(f"   🔗 [지원]({card.apply_url})")

    return "\n".join(lines).strip()


def render_social_alert_candidate(candidate: dict[str, object]) -> str:
    """verified social discovery alert → Telegram MarkdownV2 텍스트."""
    organization = escape_md(str(candidate.get("organization_name") or candidate.get("social_organization") or "Unknown"))
    program = escape_md(str(candidate.get("program_name") or candidate.get("social_program") or "Unknown Program"))
    category = CATEGORY_LABEL.get(str(candidate.get("category") or ""), str(candidate.get("category") or ""))
    status = str(candidate.get("status") or "unknown")
    status_emoji = STATUS_EMOJI.get(status, "⚪")
    monitoring_round = str(candidate.get("monitoring_round") or "").strip()
    matched_account = str(candidate.get("matched_account") or "").strip().lstrip("@")
    signal_type = str(candidate.get("signal_type") or "").strip()
    apply_url = str(candidate.get("apply_url") or "").strip()
    program_url = str(candidate.get("program_url") or "").strip()
    social_url = str(candidate.get("source_url") or "").strip()
    deadline_at = str(candidate.get("deadline_at") or "").strip()
    days_left = candidate.get("days_left")
    confidence = float(candidate.get("fact_confidence") or 0.0)

    lines: list[str] = []
    lines.append("🚨 *NEW VERIFIED SOCIAL FUNDING SIGNAL*")
    lines.append(f"*{organization}* — {program}")
    lines.append(f"{escape_md(category)} │ {status_emoji} {escape_md(status.upper())}")

    deadline_text = None
    if deadline_at:
        deadline_text = deadline_at[:10]
    if deadline_text and not _is_stale_date_text(deadline_text):
        if isinstance(days_left, int) and days_left >= 0:
            lines.append(f"📅 {escape_md(deadline_text)} \\(D\\-{days_left}\\)")
        else:
            lines.append(f"📅 {escape_md(deadline_text)}")

    why_parts: list[str] = []
    if matched_account:
        why_parts.append(f"@{matched_account}")
    if signal_type:
        why_parts.append(signal_type.replace("_", " "))
    if monitoring_round:
        why_parts.append(monitoring_round)
    if why_parts:
        lines.append(f"👀 발견 경로: {escape_md(' │ '.join(why_parts))}")

    lines.append(f"🔍 신뢰도: {escape_md(f'{confidence:.0%}')}")

    link_parts: list[str] = []
    if program_url and apply_url and program_url != apply_url:
        link_parts.append(f"🌐 [공식]({program_url})")
        link_parts.append(f"🔗 [지원]({apply_url})")
    elif apply_url:
        link_parts.append(f"🔗 [지원]({apply_url})")
    elif program_url:
        link_parts.append(f"🌐 [공식]({program_url})")
    if social_url:
        link_parts.append(f"🐦 [소셜 근거]({social_url})")
    if link_parts:
        lines.append(" │ ".join(link_parts))

    return "\n".join(lines)


def render_empty(category: str | None = None) -> str:
    """빈 결과 메시지."""
    if category:
        cat_label = CATEGORY_LABEL.get(category, category)
        return escape_md(f"현재 DB에 {cat_label} 데이터가 없습니다. "
                         f"파이프라인 실행 후 다시 시도하세요.")
    return escape_md("현재 DB에 데이터가 없습니다. 파이프라인 실행 후 다시 시도하세요.")


def render_error(message: str = "DB 오류. 관리자에게 문의하세요.") -> str:
    """에러 메시지."""
    return f"⚠️ {escape_md(message)}"


# ============================================================
# 내부 유틸
# ============================================================


def _score_bar(score: float, width: int = 5) -> str:
    """점수를 시각적 바로 표현. 예: ███░░ (0.6)"""
    filled = round(score * width)
    empty = width - filled
    return "█" * filled + "░" * empty
