# DEV_SETUP — 개발 환경 설정

## Python 환경

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## requirements.txt

```
# Core
python-telegram-bot==21.3
anthropic==0.39.0
aiosqlite==0.20.0

# Web fetching
httpx==0.27.0
beautifulsoup4==4.12.3
lxml==5.2.0

# Search
tavily-python==0.4.0

# Data validation
pydantic==2.9.0

# Utils
python-dotenv==1.0.1
structlog==24.4.0
tenacity==9.0.0

# Dev
pytest==8.3.0
pytest-asyncio==0.24.0
```

## .env

```env
# Required
TELEGRAM_BOT_TOKEN=
ANTHROPIC_API_KEY=
TAVILY_API_KEY=

# Optional
LUNARCRUSH_API_KEY=
DB_PATH=data/funding.db
LOG_LEVEL=INFO
LLM_MODEL=claude-sonnet-4-20250514
LLM_MODEL_FAST=claude-haiku-4-20250414
```

## 프로젝트 디렉토리 구조 (최종)

```
VC_Grants/
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── types.py          # 공유 타입 (dataclass, enum)
│   │   ├── config.py         # 설정 로드 (.env → Config 객체)
│   │   ├── errors.py         # 커스텀 에러 클래스
│   │   └── pipeline.py       # 파이프라인 오케스트레이터
│   ├── db/
│   │   ├── __init__.py
│   │   ├── schema.sql        # DDL
│   │   ├── entity_store.py   # DB CRUD 레이어
│   │   └── queries.py        # SQL 쿼리 상수 (curated view 등)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py     # BaseAgent 추상 클래스
│   │   ├── discovery.py      # Discovery Agent
│   │   ├── verification.py   # Verification Agent
│   │   ├── matching.py       # Matching Agent
│   │   ├── research.py       # Research Agent (Phase 7)
│   │   ├── entity_resolution.py  # Entity Resolution (Phase 6)
│   │   ├── monitoring.py     # Monitoring Agent (Phase 8)
│   │   └── briefing.py       # Briefing Agent (Phase 9)
│   └── interface/                # Output interface (Telegram은 delivery일 뿐)
│       ├── __init__.py
│       ├── telegram_app.py   # Application 초기화 + 명령 라우터
│       ├── card_renderer.py  # 출력 포맷터
│       └── handlers/
│           ├── __init__.py
│           ├── list_handler.py    # /grants, /cohorts, /funds, /all
│           ├── ranking_handler.py # /ranking
│           ├── org_handler.py     # /org, /fit, /research (Phase 7)
│           ├── changes_handler.py # /changes (Phase 8)
│           ├── brief_handler.py   # /brief (Phase 9)
│           └── profile_handler.py # /register, /profile, /myprofile
├── data/
│   ├── funding.db            # SQLite DB (gitignore)
│   └── seed/
│       └── hoot_profile.json # Seed user 프로필
├── tests/
│   ├── __init__.py
│   ├── test_entity_store.py
│   ├── test_discovery.py
│   ├── test_verification.py
│   ├── test_matching.py
│   ├── test_card_renderer.py
│   └── test_pipeline.py
├── requirements.txt
├── .env                      # gitignore
├── .env.example
└── pyproject.toml
```

## 의존성 방향 (import 규칙)

```
core/types.py      ← 모든 모듈이 import 가능
core/config.py     ← 모든 모듈이 import 가능
core/errors.py     ← 모든 모듈이 import 가능
db/entity_store.py ← agents/*, interface/*, core/pipeline.py
db/queries.py      ← db/entity_store.py, interface/handlers/*
agents/*           ← core/pipeline.py, interface/handlers/* (일부)
interface/card_renderer  ← interface/handlers/*
interface/handlers/*     ← interface/telegram_app.py
```

**금지:**
- `interface/handlers/` → `agents/` 직접 호출 (deterministic 명령: /grants, /cohorts, /funds, /all, /ranking, /changes, /brief)
- `agents/` → `agents/` 직접 호출 (pipeline을 통해서만)
- `db/` → `agents/` 또는 `interface/` import

**예외 허용:**
- `interface/handlers/` → `agents/` 호출: reasoned 명령 한정 (/org, /fit, /research, /verify)
- 이 경우에도 agent 결과는 DB facts(PROVIDED_FACTS) 기반만 사용

## 실행 방법

```bash
# DB 초기화
python -m src.db.entity_store --init

# Agent system 시작 (Telegram interface)
python -m src.interface.telegram_app

# 수동 파이프라인 실행
python -m src.core.pipeline --query "AI infrastructure grants"

# 테스트
pytest tests/ -v
```

## 에러 처리 패턴

모든 에러는 복구 방법 포함:

```python
# 금지
raise ValueError("invalid input")

# 필수
from src.core.errors import AgentError

raise AgentError(
    code="DISCOVERY_FETCH_FAIL",
    message="소스 URL에서 데이터를 가져올 수 없음",
    fix="URL 접근 가능 여부 확인 후 재시도. source_url={url}",
    context={"url": url, "status_code": resp.status_code}
)
```

## 로깅 패턴

```python
import structlog
log = structlog.get_logger()

# agent 시작/종료
log.info("agent.start", agent="discovery", query=query)
log.info("agent.complete", agent="discovery", count=len(results), elapsed=elapsed)

# DB 작업
log.info("db.insert", table="opportunities", id=opp_id)

# 에러
log.error("agent.fail", agent="discovery", error=str(e), url=url)
```
