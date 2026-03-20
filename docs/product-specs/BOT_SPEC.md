# BOT_SPEC — src/interface/ (Telegram Output Interface)

> Telegram은 AI Agent System의 **output interface**일 뿐.
> 핵심 로직은 agents/에 있고, interface/는 사용자 명령 → agent 호출 → 결과 렌더링만 담당.

## src/interface/telegram_app.py — Application 초기화

```python
from telegram.ext import Application, CommandHandler
from src.core.config import config
from src.db.entity_store import EntityStore

class FundingAgentApp:
    def __init__(self):
        self.store = EntityStore()
        self.app = Application.builder().token(config.telegram_token).build()

    def setup_handlers(self):
        """명령 핸들러 등록."""
        # Deterministic (LLM 금지)
        self.app.add_handler(CommandHandler("grants", list_handler.grants))
        self.app.add_handler(CommandHandler("cohorts", list_handler.cohorts))
        self.app.add_handler(CommandHandler("funds", list_handler.funds))
        self.app.add_handler(CommandHandler("all", list_handler.all_funding))
        self.app.add_handler(CommandHandler("ranking", ranking_handler.ranking))
        self.app.add_handler(CommandHandler("changes", changes_handler.changes))   # Phase 8
        self.app.add_handler(CommandHandler("brief", brief_handler.brief))         # Phase 9

        # Reasoned (LLM 허용, PROVIDED_FACTS 기반만)
        self.app.add_handler(CommandHandler("org", org_handler.org_detail))         # Phase 7
        self.app.add_handler(CommandHandler("fit", org_handler.fit_detail))         # Phase 7
        self.app.add_handler(CommandHandler("research", org_handler.research))      # Phase 7
        self.app.add_handler(CommandHandler("verify", org_handler.verify))

        # 프로필 관리
        self.app.add_handler(CommandHandler("register", profile_handler.register))
        self.app.add_handler(CommandHandler("profile", profile_handler.view_profile))
        self.app.add_handler(CommandHandler("start", profile_handler.start))

    async def post_init(self, application):
        """Agent system 시작 시 DB 연결."""
        await self.store.connect()
        await self.store.init_schema()

    def run(self):
        self.setup_handlers()
        self.app.post_init = self.post_init
        self.app.run_polling()

if __name__ == "__main__":
    agent = FundingAgentApp()
    agent.run()
```

---

## src/interface/handlers/profile_handler.py — 프로필 관리

```python
from telegram import Update
from telegram.ext import ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start — 봇 소개 + 프로필 등록 안내.

    응답:
    "Funding Intelligence Agent입니다.
     /register로 프로젝트를 등록하면 맞춤 펀딩 기회를 찾아드립니다."
    """

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /register — 프로필 등록 시작.

    Flow:
    1. "프로젝트 이름을 입력해주세요" → 대기
    2. "프로젝트 단계를 선택해주세요 (idea/mvp/seed/series_a)" → 대기
    3. "섹터 태그를 쉼표로 입력해주세요 (예: ai_infra, blockchain, defi)" → 대기
    4. "프로젝트 한 줄 설명을 입력해주세요" → 대기
    5. CompanyProfile 생성 → DB 저장
    6. "등록 완료! /grants, /cohorts, /funds로 맞춤 기회를 확인하세요."

    telegram_user_id = update.effective_user.id 로 사용자 연결.

    구현: ConversationHandler 사용.
    """

async def view_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /profile — 내 프로필 조회.

    1. telegram_user_id로 프로필 조회
    2. 없으면: "등록된 프로필이 없습니다. /register로 등록하세요."
    3. 있으면: 프로필 정보 출력
    """
```

---

## src/interface/handlers/list_handler.py — 목록 명령 (LLM 금지)

```python
async def grants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /grants — Grant 기회 목록.

    Flow:
    1. telegram_user_id로 company_profile 조회
    2. 없으면: "프로필을 먼저 등록하세요. /register"
    3. store.list_opportunities_curated(
           company_profile_id=profile.id,
           category="grant",
           min_confidence=0.75,
           limit=10
       )
    4. 결과 0건: "현재 DB에 해당 카테고리 데이터 없음. /research로 수동 추가 가능."
    5. 결과 있음: card_renderer.render_ranked_list(cards)
    6. 전송

    LLM 호출: 절대 금지.
    응답 시간: < 2초.
    """

async def cohorts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /cohorts — Accelerator + VC Cohort 목록.
    grants와 동일 로직, category=["accelerator", "vc_cohort"].
    """

async def funds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /funds — Ecosystem Builder Program 기회 목록.
    grants와 동일 로직, category="ecosystem_builder", min_confidence=0.70.
    """

async def all_funding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /all — 전체 4개 카테고리 상위 기회.
    grant + accelerator + vc_cohort + ecosystem_builder 각 상위 기회.
    min_confidence=0.80. 최대 15개.
    """
```

### 공통 헬퍼

```python
async def _get_user_profile(update: Update, store: EntityStore) -> CompanyProfile | None:
    """telegram_user_id로 프로필 조회. 없으면 None."""
    user_id = update.effective_user.id
    return await store.get_profile_by_telegram_user(user_id)

def _opportunities_to_cards(rows: list[dict]) -> list[OpportunityCard]:
    """DB curated view 결과를 OpportunityCard 리스트로 변환."""
    return [
        OpportunityCard(
            organization=row["org_name"],
            program=row["program_name"],
            category=row["category"],
            status=row["status"],
            apply_url=row["apply_url"],
            confidence=row["fact_confidence"],
            deadline=row.get("deadline_at"),
            days_left=row.get("days_left"),
            budget=row.get("budget_note"),
            fit_score=row.get("fit_score"),
            priority_score=row.get("priority_score"),
            why_fit=row.get("why_fit"),
            next_action=row.get("next_action"),
        )
        for row in rows
    ]
```

---

## src/interface/handlers/ranking_handler.py

```python
async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /ranking [intent] — 사용자 프로필 기준 상위 기회.

    intent 옵션: default, urgent, biggest_check, ready_now, best_fit
    기본: default

    1. 프로필 조회
    2. matching_agent.batch_rank(profile_id, intent=intent, top_n=10)
    3. card_renderer.render_ranked_list(cards)
    """
```

---

## src/interface/card_renderer.py — 출력 포맷터

```python
from src.core.types import OpportunityCard, DossierCard, DailyBriefData

def render_opportunity_card(card: OpportunityCard) -> str:
    """
    단일 기회 카드 → Telegram MarkdownV2 문자열.

    출력 형태:
    🏦 {organization} — {program}
    📁 {category} | ✅ verified
    ⏰ 마감: {deadline} (D-{days_left})
    💰 {budget}
    🔗 apply: {apply_url}
    🎯 fit: {fit_score} | priority: {priority_score}
    💡 "{why_fit}"
    """

def render_ranked_list(cards: list[OpportunityCard]) -> str:
    """
    기회 목록 → Telegram 문자열.
    각 카드 사이 빈 줄 구분.
    최대 10개 (초과 시 잘라냄).
    카드 순번 표시: 1. 2. 3. ...
    """

def render_dossier_card(card: DossierCard) -> str:
    """
    조직 dossier → Telegram 문자열.

    출력 형태:
    🏢 {org_name} ({org_type})
    🌐 {website}
    📊 포트폴리오: {portfolio_count}개
    💵 평균 체크: {avg_check_size}
    🎯 관심 분야: {focus_areas}
    👤 의사결정자: {decision_makers}
    """

def render_daily_brief(data: DailyBriefData) -> str:
    """
    일일 브리핑 → Telegram 문자열.

    섹션:
    📋 오늘의 브리핑
    ── Top 기회 ──
    (top_opportunities 카드 목록)
    ── 신규 ──
    (new_today 카드 목록)
    ── 마감 임박 (D-7) ──
    (deadline_soon 카드 목록)
    ── 변동 사항 ──
    (changes 텍스트 목록)
    """

def render_empty(category: str) -> str:
    """
    DB 0건 시 고정 응답.
    "현재 DB에 {category} 데이터 없음. /research로 수동 추가 가능."
    """

def render_error(error_type: str) -> str:
    """
    에러 시 고정 응답.
    error_type별 메시지 매핑 (DB_FAIL, TIMEOUT 등).
    """
```

### Telegram MarkdownV2 이스케이프

```python
import re

def escape_md(text: str) -> str:
    """Telegram MarkdownV2 특수문자 이스케이프."""
    special = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(special)}])', r'\\\1', text)
```

---

## 에러 응답 규칙

| 상황 | 함수 | 응답 |
|------|------|------|
| 프로필 미등록 | 각 handler | "프로필을 먼저 등록하세요. /register" |
| DB 0건 | render_empty() | "현재 DB에 {category} 데이터 없음." |
| eligibility 미달 전부 | render_empty() | "조건을 충족하는 verified 기회가 없음." |
| DB 연결 실패 | render_error("DB_FAIL") | "DB 오류. 관리자에게 문의." |
| LLM 타임아웃 | render_error("TIMEOUT") | "분석 타임아웃. 잠시 후 재시도." |

**절대 금지:** 에러 상황에서 LLM으로 대체 응답 생성

---

## 테스트: tests/test_card_renderer.py

```python
def test_render_opportunity_card_all_fields():
    """전체 필드가 있는 카드 렌더링."""

def test_render_opportunity_card_minimal():
    """fit 데이터 없는 카드 (필수 필드만)."""

def test_render_ranked_list_max_10():
    """11개 입력 시 10개만 렌더링."""

def test_render_empty_grants():
    """grants 카테고리 빈 응답."""

def test_escape_md_special_chars():
    """MarkdownV2 특수문자 이스케이프."""

def test_render_daily_brief_all_sections():
    """4개 섹션 모두 포함."""

def test_render_daily_brief_empty_sections():
    """빈 섹션은 표시하지 않음."""
```
