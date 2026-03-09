"""
Funding Intelligence Agent — Card Renderer.

Telegram MarkdownV2 포맷 출력.
OpportunityCard → 텍스트 변환만 담당. LLM 호출 없음.
"""

from __future__ import annotations

import re

from src.core.types import DailyBriefData, DossierCard, OpportunityCard

# ============================================================
# MarkdownV2 이스케이프
# ============================================================

# Telegram MarkdownV2에서 이스케이프해야 하는 특수문자
_ESCAPE_CHARS = r"_*[]()~`>#+-=|{}.!"


def escape_md(text: str) -> str:
    """Telegram MarkdownV2 특수문자 이스케이프."""
    return re.sub(r"([" + re.escape(_ESCAPE_CHARS) + r"])", r"\\\1", text)


# ============================================================
# Status 이모지 매핑
# ============================================================

STATUS_EMOJI: dict[str, str] = {
    "open": "🟢",
    "rolling": "🔵",
    "deadline": "🟡",
    "upcoming": "⏳",
    "closed": "🔴",
    "unknown": "⚪",
}

CATEGORY_LABEL: dict[str, str] = {
    "grant": "💰 Grant",
    "accelerator": "🚀 Accelerator",
    "vc_cohort": "🏦 VC Cohort",
    "ecosystem_builder": "🌱 Ecosystem Builder",
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
    if card.deadline:
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

    # 신뢰도
    conf_text = f"신뢰도: {card.confidence:.0%}"
    lines.append(f"   🔍 {escape_md(conf_text)}")

    # 지원 링크
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
