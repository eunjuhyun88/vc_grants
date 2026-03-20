"""
Funding Intelligence Agent — DB CRUD 레이어.

의존성: core/types.py, core/config.py, db/queries.py
이 모듈을 import하는 곳: agents/*, interface/*, core/pipeline.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

from src.core.config import config
from src.core.errors import StoreError
from src.core.types import (
    ApplicationEndpoint,
    CompanyProfile,
    CompanyStage,
    EndpointType,
    FitRecommendation,
    Observation,
    Opportunity,
    OpportunityStatus,
    Organization,
    OrgType,
    OutputStatus,
    Program,
    ProgramCategory,
    SocialMonitoringEvent,
    deserialize_json_field,
    generate_id,
    serialize_json_field,
)
from src.core.types import BUCKET_TO_CATEGORIES
from src.db.queries import (
    CURATED_VIEW_CATEGORY_FILTER,
    CURATED_VIEW_DISPLAY_BUCKET_FILTER_TEMPLATE,
    CURATED_VIEW_ORDER,
    CURATED_VIEW_SQL,
)


class EntityStore:
    """SQLite DB 접근 레이어. async context manager 지원."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or config.db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """DB 연결. 없으면 파일 생성."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self.db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA foreign_keys = ON")
        await self._db.execute("PRAGMA journal_mode = WAL")

    async def close(self) -> None:
        """DB 연결 종료."""
        if self._db:
            await self._db.close()
            self._db = None

    async def init_schema(self) -> None:
        """schema.sql 실행하여 테이블 생성."""
        schema_path = Path(__file__).parent / "schema.sql"
        if not schema_path.exists():
            raise StoreError(
                message="schema.sql 파일을 찾을 수 없음",
                fix=f"파일 존재 여부 확인: {schema_path}",
                context={"path": str(schema_path)},
            )
        schema = schema_path.read_text(encoding="utf-8")
        await self._db.executescript(schema)

    async def __aenter__(self) -> EntityStore:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise StoreError(
                message="DB 연결이 없음",
                fix="EntityStore.connect() 호출 또는 async with EntityStore() 사용",
            )
        return self._db

    # ============================================================
    # Organization CRUD
    # ============================================================

    async def create_organization(self, org: Organization) -> str:
        """조직 생성. 반환: org.id"""
        await self.db.execute(
            """INSERT INTO organizations
               (id, normalized_name, display_name, domain, org_type, sector_tags, website_url)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                org.id,
                org.normalized_name,
                org.display_name,
                org.domain,
                org.org_type.value if org.org_type else None,
                serialize_json_field(org.sector_tags),
                org.website_url,
            ),
        )
        await self.db.commit()
        return org.id

    async def get_organization(self, org_id: str) -> Organization | None:
        """ID로 조직 조회."""
        cursor = await self.db.execute(
            "SELECT * FROM organizations WHERE id = ?", (org_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_organization(row)

    async def get_organization_by_domain(self, domain: str) -> Organization | None:
        """도메인으로 조직 조회 (dedup 기준 1순위)."""
        cursor = await self.db.execute(
            "SELECT * FROM organizations WHERE domain = ?", (domain,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_organization(row)

    async def get_organization_by_name(self, normalized_name: str) -> Organization | None:
        """정규화된 이름으로 조직 조회."""
        cursor = await self.db.execute(
            "SELECT * FROM organizations WHERE normalized_name = ?",
            (normalized_name,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_organization(row)

    async def list_organizations(
        self,
        org_type: OrgType | None = None,
        limit: int = 50,
    ) -> list[Organization]:
        """조직 목록 조회. org_type 필터 선택."""
        if org_type:
            cursor = await self.db.execute(
                "SELECT * FROM organizations WHERE org_type = ? ORDER BY display_name LIMIT ?",
                (org_type.value, limit),
            )
        else:
            cursor = await self.db.execute(
                "SELECT * FROM organizations ORDER BY display_name LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [self._row_to_organization(r) for r in rows]

    async def update_organization(self, org_id: str, **fields: Any) -> None:
        """조직 필드 업데이트. updated_at 자동 갱신."""
        if not fields:
            return
        if "sector_tags" in fields and isinstance(fields["sector_tags"], list):
            fields["sector_tags"] = serialize_json_field(fields["sector_tags"])
        if "org_type" in fields and isinstance(fields["org_type"], OrgType):
            fields["org_type"] = fields["org_type"].value
        fields["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [org_id]
        await self.db.execute(
            f"UPDATE organizations SET {set_clause} WHERE id = ?", values
        )
        await self.db.commit()

    def _row_to_organization(self, row: aiosqlite.Row) -> Organization:
        return Organization(
            id=row["id"],
            normalized_name=row["normalized_name"],
            display_name=row["display_name"],
            domain=row["domain"],
            org_type=OrgType(row["org_type"]) if row["org_type"] else None,
            sector_tags=deserialize_json_field(row["sector_tags"]) or [],
            website_url=row["website_url"],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )

    # ============================================================
    # Program CRUD
    # ============================================================

    async def create_program(self, program: Program) -> str:
        """프로그램 생성. UNIQUE(org_id, normalized_name) 위반 시 에러."""
        try:
            await self.db.execute(
                """INSERT INTO programs
                   (id, org_id, normalized_name, display_name, category, program_url, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    program.id,
                    program.org_id,
                    program.normalized_name,
                    program.display_name,
                    program.category.value,
                    program.program_url,
                    program.description,
                ),
            )
            await self.db.commit()
        except Exception as e:
            if "UNIQUE constraint" in str(e):
                raise StoreError(
                    message=f"프로그램 중복: org_id={program.org_id}, name={program.normalized_name}",
                    fix="get_program_by_org_and_name()으로 기존 프로그램 조회 후 사용",
                    context={"org_id": program.org_id, "name": program.normalized_name},
                )
            raise
        return program.id

    async def get_program(self, program_id: str) -> Program | None:
        """ID로 프로그램 조회."""
        cursor = await self.db.execute(
            "SELECT * FROM programs WHERE id = ?", (program_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_program(row)

    async def get_program_by_org_and_name(
        self, org_id: str, normalized_name: str
    ) -> Program | None:
        """조직 + 정규화 이름으로 프로그램 조회 (dedup 기준)."""
        cursor = await self.db.execute(
            "SELECT * FROM programs WHERE org_id = ? AND normalized_name = ?",
            (org_id, normalized_name),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_program(row)

    async def list_programs(
        self,
        org_id: str | None = None,
        category: ProgramCategory | None = None,
        limit: int = 50,
    ) -> list[Program]:
        """프로그램 목록. org_id 또는 category 필터."""
        conditions: list[str] = []
        params: list[Any] = []
        if org_id:
            conditions.append("org_id = ?")
            params.append(org_id)
        if category:
            conditions.append("category = ?")
            params.append(category.value)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        cursor = await self.db.execute(
            f"SELECT * FROM programs {where} ORDER BY display_name LIMIT ?", params
        )
        rows = await cursor.fetchall()
        return [self._row_to_program(r) for r in rows]

    async def update_program(self, program_id: str, **fields: Any) -> None:
        """프로그램 필드 업데이트."""
        if not fields:
            return
        if "category" in fields and isinstance(fields["category"], ProgramCategory):
            fields["category"] = fields["category"].value
        fields["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [program_id]
        await self.db.execute(
            f"UPDATE programs SET {set_clause} WHERE id = ?",
            values,
        )
        await self.db.commit()

    def _row_to_program(self, row: aiosqlite.Row) -> Program:
        return Program(
            id=row["id"],
            org_id=row["org_id"],
            normalized_name=row["normalized_name"],
            display_name=row["display_name"],
            category=ProgramCategory(row["category"]),
            program_url=row["program_url"],
            description=row["description"],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )

    # ============================================================
    # Opportunity CRUD
    # ============================================================

    async def create_opportunity(self, opp: Opportunity) -> str:
        """기회 생성. program_id 필수."""
        await self.db.execute(
            """INSERT INTO opportunities
               (id, program_id, cycle_key, status, deadline_at, days_left,
                budget_amount, budget_currency, budget_note, apply_url,
                output_status, fact_confidence, source_tier, evidence_json, source_chain)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                opp.id,
                opp.program_id,
                opp.cycle_key,
                opp.status.value,
                opp.deadline_at.isoformat() if opp.deadline_at else None,
                opp.days_left,
                opp.budget_amount,
                opp.budget_currency,
                opp.budget_note,
                opp.apply_url,
                opp.output_status.value,
                opp.fact_confidence,
                opp.source_tier,
                serialize_json_field(opp.evidence_json),
                serialize_json_field(opp.source_chain),
            ),
        )
        await self.db.commit()
        return opp.id

    async def get_opportunity(self, opp_id: str) -> Opportunity | None:
        """ID로 기회 조회."""
        cursor = await self.db.execute(
            "SELECT * FROM opportunities WHERE id = ?", (opp_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_opportunity(row)

    async def get_latest_opportunity_by_program_and_apply_url(
        self,
        program_id: str,
        apply_url: str | None,
    ) -> Opportunity | None:
        """program + apply_url 조합으로 가장 최근 기회 조회.

        Seed import와 반복 discovery에서 같은 intake/landing page가 다시 들어올 때
        opportunity를 중복 생성하지 않도록 한다.
        """
        if not apply_url:
            return None
        cursor = await self.db.execute(
            """SELECT * FROM opportunities
               WHERE program_id = ? AND apply_url = ?
               ORDER BY updated_at DESC, created_at DESC
               LIMIT 1""",
            (program_id, apply_url),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_opportunity(row)

    async def get_latest_opportunity_by_program(
        self,
        program_id: str,
    ) -> Opportunity | None:
        """program 단위 최신 기회 조회.

        apply_url이 없고 cycle_key도 없는 seed/update 경로에서 동일 program의
        대표 opportunity를 업데이트하기 위한 fallback.
        """
        cursor = await self.db.execute(
            """SELECT * FROM opportunities
               WHERE program_id = ?
               ORDER BY updated_at DESC, created_at DESC
               LIMIT 1""",
            (program_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_opportunity(row)

    async def update_opportunity(self, opp_id: str, **fields: Any) -> None:
        """기회 필드 업데이트. deadline 변경 시 기존 record UPDATE, 새 row 생성 금지."""
        if not fields:
            return
        if "status" in fields and isinstance(fields["status"], OpportunityStatus):
            fields["status"] = fields["status"].value
        if "output_status" in fields and isinstance(fields["output_status"], OutputStatus):
            fields["output_status"] = fields["output_status"].value
        if "evidence_json" in fields and isinstance(fields["evidence_json"], list):
            fields["evidence_json"] = serialize_json_field(fields["evidence_json"])
        if "source_chain" in fields and isinstance(fields["source_chain"], list):
            fields["source_chain"] = serialize_json_field(fields["source_chain"])
        if "deadline_at" in fields and isinstance(fields["deadline_at"], datetime):
            fields["deadline_at"] = fields["deadline_at"].isoformat()
        fields["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [opp_id]
        await self.db.execute(
            f"UPDATE opportunities SET {set_clause} WHERE id = ?", values
        )
        await self.db.commit()

    async def list_opportunities_curated(
        self,
        company_profile_id: str | None = None,
        category: ProgramCategory | None = None,
        display_bucket: str | None = None,
        min_confidence: float = 0.75,
        limit: int = 10,
    ) -> list[dict]:
        """
        Curated View 조회 — Eligibility Filter 적용.
        조건: verified + confidence >= min + tier <= 4 + apply_url + not closed.
        JOIN: organizations, programs, fit_recommendations (LEFT).
        정렬: priority_score DESC, fallback: fact_confidence DESC, days_left ASC.

        display_bucket: "grants"|"cohorts"|"funds" → 해당 bucket에 매핑된 category들로 필터.
        category: 단일 ProgramCategory로 필터 (display_bucket과 동시 사용 시 display_bucket 우선).
        """
        sql = CURATED_VIEW_SQL
        params: dict[str, Any] = {
            "company_profile_id": company_profile_id or "",
            "min_confidence": min_confidence,
            "limit": limit,
        }

        if display_bucket and display_bucket in BUCKET_TO_CATEGORIES:
            # display_bucket 기반 IN 절 (named params 사용 불가 → positional 혼용 불가)
            # 따라서 직접 문자열로 IN 절 생성 (안전: 값이 상수 맵에서만 옴)
            categories = BUCKET_TO_CATEGORIES[display_bucket]
            placeholders = ", ".join(f"'{c}'" for c in categories)
            sql += CURATED_VIEW_DISPLAY_BUCKET_FILTER_TEMPLATE.format(
                placeholders=placeholders
            )
        elif category:
            sql += CURATED_VIEW_CATEGORY_FILTER
            params["category"] = category.value

        sql += CURATED_VIEW_ORDER
        cursor = await self.db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def list_opportunities(
        self,
        status: OpportunityStatus | None = None,
        limit: int = 100,
    ) -> list[Opportunity]:
        """전체 기회 조회 (MonitoringAgent용). updated_at 오래된 순."""
        conditions: list[str] = []
        params: list[Any] = []
        if status:
            conditions.append("status = ?")
            params.append(status.value)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        cursor = await self.db.execute(
            f"SELECT * FROM opportunities {where} ORDER BY updated_at ASC LIMIT ?",
            params,
        )
        rows = await cursor.fetchall()
        return [self._row_to_opportunity(r) for r in rows]

    async def count_opportunities(
        self,
        category: ProgramCategory | None = None,
        status: OpportunityStatus | None = None,
    ) -> int:
        """기회 수 카운트."""
        conditions: list[str] = []
        params: list[Any] = []
        base = "SELECT COUNT(*) FROM opportunities o"
        if category:
            base += " JOIN programs p ON o.program_id = p.id"
            conditions.append("p.category = ?")
            params.append(category.value)
        if status:
            conditions.append("o.status = ?")
            params.append(status.value)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        cursor = await self.db.execute(base + where, params)
        row = await cursor.fetchone()
        return row[0] if row else 0

    def _row_to_opportunity(self, row: aiosqlite.Row) -> Opportunity:
        return Opportunity(
            id=row["id"],
            program_id=row["program_id"],
            cycle_key=row["cycle_key"],
            status=OpportunityStatus(row["status"]),
            deadline_at=_parse_dt(row["deadline_at"]),
            days_left=row["days_left"],
            budget_amount=row["budget_amount"],
            budget_currency=row["budget_currency"] or "USD",
            budget_note=row["budget_note"],
            apply_url=row["apply_url"],
            output_status=OutputStatus(row["output_status"]),
            fact_confidence=row["fact_confidence"] or 0.0,
            source_tier=row["source_tier"],
            evidence_json=deserialize_json_field(row["evidence_json"]) or [],
            source_chain=deserialize_json_field(row["source_chain"]) or [],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )

    # ============================================================
    # Observation CRUD
    # ============================================================

    async def create_observation(self, obs: Observation) -> str:
        """검증 증거 저장."""
        await self.db.execute(
            """INSERT INTO observations
               (id, opportunity_id, org_id, source_url, source_tier, observed_data, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                obs.id,
                obs.opportunity_id,
                obs.org_id,
                obs.source_url,
                obs.source_tier,
                serialize_json_field(obs.observed_data),
                obs.confidence,
            ),
        )
        await self.db.commit()
        return obs.id

    async def list_observations(
        self,
        opportunity_id: str | None = None,
        org_id: str | None = None,
    ) -> list[Observation]:
        """특정 기회 또는 조직의 observation 목록."""
        conditions: list[str] = []
        params: list[Any] = []
        if opportunity_id:
            conditions.append("opportunity_id = ?")
            params.append(opportunity_id)
        if org_id:
            conditions.append("org_id = ?")
            params.append(org_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        cursor = await self.db.execute(
            f"SELECT * FROM observations {where} ORDER BY observed_at DESC", params
        )
        rows = await cursor.fetchall()
        return [self._row_to_observation(r) for r in rows]

    def _row_to_observation(self, row: aiosqlite.Row) -> Observation:
        return Observation(
            id=row["id"],
            opportunity_id=row["opportunity_id"],
            org_id=row["org_id"],
            source_url=row["source_url"],
            source_tier=row["source_tier"],
            observed_data=deserialize_json_field(row["observed_data"]) or {},
            confidence=row["confidence"] or 0.0,
            observed_at=_parse_dt(row["observed_at"]),
        )

    # ============================================================
    # Social Monitoring Event CRUD
    # ============================================================

    async def upsert_social_monitoring_event(
        self,
        event: SocialMonitoringEvent,
    ) -> str:
        """소셜 탐색 provenance 저장/갱신. source_url 기준 dedup."""
        await self.db.execute(
            """INSERT INTO social_monitoring_events
               (id, source_url, matched_account, matched_account_type, monitoring_round,
                organization, program, category, signal_type, apply_url,
                source_tier, confidence, promoted_opportunity_id,
                verification_status, notified, discovered_at, notified_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(source_url)
               DO UPDATE SET
                matched_account = excluded.matched_account,
                matched_account_type = excluded.matched_account_type,
                monitoring_round = excluded.monitoring_round,
                organization = excluded.organization,
                program = excluded.program,
                category = excluded.category,
                signal_type = excluded.signal_type,
                apply_url = COALESCE(excluded.apply_url, social_monitoring_events.apply_url),
                source_tier = excluded.source_tier,
                confidence = excluded.confidence,
                promoted_opportunity_id = COALESCE(excluded.promoted_opportunity_id, social_monitoring_events.promoted_opportunity_id),
                verification_status = excluded.verification_status,
                notified = CASE
                    WHEN social_monitoring_events.notified = TRUE THEN TRUE
                    ELSE excluded.notified
                END,
                notified_at = COALESCE(social_monitoring_events.notified_at, excluded.notified_at)""",
            (
                event.id,
                event.source_url,
                event.matched_account,
                event.matched_account_type,
                event.monitoring_round,
                event.organization,
                event.program,
                event.category,
                event.signal_type,
                event.apply_url,
                event.source_tier,
                event.confidence,
                event.promoted_opportunity_id,
                event.verification_status,
                event.notified,
                event.discovered_at.isoformat() if event.discovered_at else None,
                event.notified_at.isoformat() if event.notified_at else None,
            ),
        )
        await self.db.commit()
        return event.id

    async def sync_social_monitoring_status_for_opportunity(
        self,
        opportunity_id: str,
    ) -> None:
        """기회 검증 상태를 social provenance 레코드에 반영."""
        opp = await self.get_opportunity(opportunity_id)
        if opp is None:
            return

        verification_status = "pending"
        if (
            opp.output_status == OutputStatus.VERIFIED
            and opp.status in {
                OpportunityStatus.OPEN,
                OpportunityStatus.ROLLING,
                OpportunityStatus.UPCOMING,
            }
            and opp.apply_url
            and opp.fact_confidence >= 0.75
            and (opp.source_tier or 99) <= 2
        ):
            verification_status = "verified"
        elif opp.output_status == OutputStatus.REJECTED or opp.status == OpportunityStatus.CLOSED:
            verification_status = "rejected"

        await self.db.execute(
            """UPDATE social_monitoring_events
               SET promoted_opportunity_id = ?, verification_status = ?
               WHERE promoted_opportunity_id = ?""",
            (opportunity_id, verification_status, opportunity_id),
        )
        await self.db.commit()

    async def list_social_monitoring_events(
        self,
        verification_status: str | None = None,
        limit: int = 100,
    ) -> list[SocialMonitoringEvent]:
        conditions: list[str] = []
        params: list[Any] = []
        if verification_status:
            conditions.append("verification_status = ?")
            params.append(verification_status)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        cursor = await self.db.execute(
            f"""SELECT * FROM social_monitoring_events
                {where}
                ORDER BY discovered_at DESC
                LIMIT ?""",
            params,
        )
        rows = await cursor.fetchall()
        return [self._row_to_social_monitoring_event(row) for row in rows]

    async def list_social_alert_candidates(
        self,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """verified actionable social discoveries 중 아직 알리지 않은 후보."""
        cursor = await self.db.execute(
            """
            SELECT
                sme.id AS event_id,
                sme.source_url,
                sme.matched_account,
                sme.matched_account_type,
                sme.monitoring_round,
                sme.organization AS social_organization,
                sme.program AS social_program,
                sme.signal_type,
                sme.discovered_at,
                o.id AS opportunity_id,
                o.status,
                o.apply_url,
                o.fact_confidence,
                o.source_tier,
                o.deadline_at,
                o.days_left,
                p.display_name AS program_name,
                p.program_url,
                p.category,
                org.display_name AS organization_name
            FROM social_monitoring_events sme
            JOIN opportunities o ON o.id = sme.promoted_opportunity_id
            JOIN programs p ON p.id = o.program_id
            JOIN organizations org ON org.id = p.org_id
            WHERE sme.notified = FALSE
              AND sme.verification_status = 'verified'
              AND o.output_status = 'verified'
              AND o.status IN ('open', 'rolling', 'upcoming')
              AND o.apply_url IS NOT NULL
              AND o.fact_confidence >= 0.75
              AND (o.source_tier IS NULL OR o.source_tier <= 2)
              AND (o.days_left IS NULL OR o.days_left >= 0)
              AND (o.deadline_at IS NULL OR DATE(o.deadline_at) >= DATE('now', 'localtime'))
            ORDER BY
              CASE WHEN o.days_left IS NULL THEN 9999 ELSE o.days_left END ASC,
              o.fact_confidence DESC,
              sme.discovered_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def list_telegram_recipient_ids(self) -> list[int]:
        """알림 전송 대상 Telegram 사용자 ID 목록."""
        cursor = await self.db.execute(
            """
            SELECT DISTINCT telegram_user_id
            FROM company_profiles
            WHERE telegram_user_id IS NOT NULL
            ORDER BY telegram_user_id ASC
            """
        )
        rows = await cursor.fetchall()
        return [int(row["telegram_user_id"]) for row in rows if row["telegram_user_id"] is not None]

    async def mark_social_alerts_notified(
        self,
        event_ids: list[str],
    ) -> None:
        if not event_ids:
            return
        placeholders = ", ".join("?" for _ in event_ids)
        await self.db.execute(
            f"""UPDATE social_monitoring_events
                SET notified = TRUE, notified_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})""",
            event_ids,
        )
        await self.db.commit()

    def _row_to_social_monitoring_event(self, row: aiosqlite.Row) -> SocialMonitoringEvent:
        return SocialMonitoringEvent(
            id=row["id"],
            source_url=row["source_url"],
            matched_account=row["matched_account"] or "",
            matched_account_type=row["matched_account_type"] or "",
            monitoring_round=row["monitoring_round"] or "",
            organization=row["organization"] or "",
            program=row["program"] or "",
            category=row["category"] or "",
            signal_type=row["signal_type"] or "",
            apply_url=row["apply_url"],
            source_tier=row["source_tier"] or 5,
            confidence=row["confidence"] or 0.0,
            promoted_opportunity_id=row["promoted_opportunity_id"],
            verification_status=row["verification_status"] or "pending",
            notified=bool(row["notified"]),
            discovered_at=_parse_dt(row["discovered_at"]),
            notified_at=_parse_dt(row["notified_at"]),
        )

    # ============================================================
    # Application Endpoint CRUD
    # ============================================================

    async def create_endpoint(self, ep: ApplicationEndpoint) -> str:
        """지원 엔드포인트 저장."""
        await self.db.execute(
            """INSERT INTO application_endpoints
               (id, opportunity_id, endpoint_type, url, is_active, verified_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                ep.id,
                ep.opportunity_id,
                ep.endpoint_type.value if ep.endpoint_type else None,
                ep.url,
                ep.is_active,
                ep.verified_at.isoformat() if ep.verified_at else None,
            ),
        )
        await self.db.commit()
        return ep.id

    async def get_active_endpoints(
        self, opportunity_id: str
    ) -> list[ApplicationEndpoint]:
        """활성 엔드포인트 목록."""
        cursor = await self.db.execute(
            """SELECT * FROM application_endpoints
               WHERE opportunity_id = ? AND is_active = TRUE
               ORDER BY verified_at DESC, created_at DESC, id DESC""",
            (opportunity_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_endpoint(r) for r in rows]

    async def sync_active_endpoints(
        self,
        opportunity_id: str,
        active_urls: list[str],
    ) -> None:
        """기회별 active endpoint set을 현재 검증 결과와 동기화한다."""
        normalized_urls = [url for url in dict.fromkeys(active_urls) if url]

        if normalized_urls:
            placeholders = ", ".join("?" for _ in normalized_urls)
            await self.db.execute(
                f"""UPDATE application_endpoints
                    SET is_active = FALSE
                    WHERE opportunity_id = ?
                      AND is_active = TRUE
                      AND url NOT IN ({placeholders})""",
                (opportunity_id, *normalized_urls),
            )
        else:
            await self.db.execute(
                """UPDATE application_endpoints
                   SET is_active = FALSE
                   WHERE opportunity_id = ? AND is_active = TRUE""",
                (opportunity_id,),
            )
        await self.db.commit()

    def _row_to_endpoint(self, row: aiosqlite.Row) -> ApplicationEndpoint:
        return ApplicationEndpoint(
            id=row["id"],
            opportunity_id=row["opportunity_id"],
            endpoint_type=EndpointType(row["endpoint_type"]) if row["endpoint_type"] else None,
            url=row["url"],
            is_active=bool(row["is_active"]),
            verified_at=_parse_dt(row["verified_at"]),
            created_at=_parse_dt(row["created_at"]),
        )

    # ============================================================
    # Company Profile CRUD
    # ============================================================

    async def create_company_profile(self, profile: CompanyProfile) -> str:
        """사용자 프로필 생성."""
        await self.db.execute(
            """INSERT INTO company_profiles
               (id, company_name, stage, sector_tags, subsector_tags, projects,
                description, geography, funding_goal, product_summary,
                target_ecosystems, telegram_user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile.id,
                profile.company_name,
                profile.stage.value if profile.stage else None,
                serialize_json_field(profile.sector_tags),
                serialize_json_field(profile.subsector_tags),
                serialize_json_field(profile.projects),
                profile.description,
                profile.geography,
                profile.funding_goal,
                profile.product_summary,
                serialize_json_field(profile.target_ecosystems),
                profile.telegram_user_id,
            ),
        )
        await self.db.commit()
        return profile.id

    async def get_company_profile(self, profile_id: str) -> CompanyProfile | None:
        """ID로 프로필 조회."""
        cursor = await self.db.execute(
            "SELECT * FROM company_profiles WHERE id = ?", (profile_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_profile(row)

    async def get_profile_by_telegram_user(
        self, telegram_user_id: int
    ) -> CompanyProfile | None:
        """Telegram 사용자 ID로 프로필 조회."""
        cursor = await self.db.execute(
            "SELECT * FROM company_profiles WHERE telegram_user_id = ?",
            (telegram_user_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_profile(row)

    async def update_company_profile(self, profile_id: str, **fields: Any) -> None:
        """프로필 업데이트."""
        if not fields:
            return
        if "sector_tags" in fields and isinstance(fields["sector_tags"], list):
            fields["sector_tags"] = serialize_json_field(fields["sector_tags"])
        if "subsector_tags" in fields and isinstance(fields["subsector_tags"], list):
            fields["subsector_tags"] = serialize_json_field(fields["subsector_tags"])
        if "projects" in fields and isinstance(fields["projects"], list):
            fields["projects"] = serialize_json_field(fields["projects"])
        if "target_ecosystems" in fields and isinstance(fields["target_ecosystems"], list):
            fields["target_ecosystems"] = serialize_json_field(fields["target_ecosystems"])
        if "stage" in fields and isinstance(fields["stage"], CompanyStage):
            fields["stage"] = fields["stage"].value
        fields["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [profile_id]
        await self.db.execute(
            f"UPDATE company_profiles SET {set_clause} WHERE id = ?", values
        )
        await self.db.commit()

    async def delete_company_profile(self, profile_id: str) -> bool:
        """프로필 삭제. 관련 fit_recommendations도 함께 정리."""
        await self.db.execute(
            "DELETE FROM fit_recommendations WHERE company_profile_id = ?",
            (profile_id,),
        )
        cursor = await self.db.execute(
            "DELETE FROM company_profiles WHERE id = ?",
            (profile_id,),
        )
        await self.db.commit()
        return (cursor.rowcount or 0) > 0

    async def delete_profile_by_telegram_user(self, telegram_user_id: int) -> bool:
        """Telegram 사용자 ID로 프로필 삭제."""
        profile = await self.get_profile_by_telegram_user(telegram_user_id)
        if profile is None:
            return False
        return await self.delete_company_profile(profile.id)

    def _row_to_profile(self, row: aiosqlite.Row) -> CompanyProfile:
        keys = row.keys()
        return CompanyProfile(
            id=row["id"],
            company_name=row["company_name"],
            stage=CompanyStage(row["stage"]) if row["stage"] else None,
            sector_tags=deserialize_json_field(row["sector_tags"]) or [],
            subsector_tags=deserialize_json_field(row["subsector_tags"]) or [] if "subsector_tags" in keys else [],
            projects=deserialize_json_field(row["projects"]) or [],
            description=row["description"],
            geography=row["geography"] if "geography" in keys else None,
            funding_goal=row["funding_goal"] if "funding_goal" in keys else None,
            product_summary=row["product_summary"] if "product_summary" in keys else None,
            target_ecosystems=deserialize_json_field(row["target_ecosystems"]) or [] if "target_ecosystems" in keys else [],
            telegram_user_id=row["telegram_user_id"],
            updated_at=_parse_dt(row["updated_at"]),
        )

    # ============================================================
    # Fit Recommendations (Phase 2, 테이블은 Phase 1에서 생성)
    # ============================================================

    async def upsert_fit_recommendation(self, rec: FitRecommendation) -> str:
        """fit 추천 생성 또는 갱신. (opportunity_id, company_profile_id) 기준."""
        await self.db.execute(
            """INSERT INTO fit_recommendations
               (id, opportunity_id, company_profile_id, project_name,
                fit_score, priority_score, why_fit, next_action,
                urgency_score, actionability_score, expected_value, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(opportunity_id, company_profile_id)
               DO UPDATE SET
                fit_score = excluded.fit_score,
                priority_score = excluded.priority_score,
                why_fit = excluded.why_fit,
                next_action = excluded.next_action,
                urgency_score = excluded.urgency_score,
                actionability_score = excluded.actionability_score,
                expected_value = excluded.expected_value,
                confidence = excluded.confidence,
                computed_at = CURRENT_TIMESTAMP""",
            (
                rec.id,
                rec.opportunity_id,
                rec.company_profile_id,
                rec.project_name,
                rec.fit_score,
                rec.priority_score,
                rec.why_fit,
                rec.next_action,
                rec.urgency_score,
                rec.actionability_score,
                rec.expected_value,
                rec.confidence,
            ),
        )
        await self.db.commit()
        return rec.id

    async def get_fit_recommendations(
        self,
        company_profile_id: str,
        top_n: int = 10,
    ) -> list[FitRecommendation]:
        """프로필 기준 상위 N개 fit 추천. priority_score DESC."""
        cursor = await self.db.execute(
            """SELECT * FROM fit_recommendations
               WHERE company_profile_id = ?
               ORDER BY priority_score DESC
               LIMIT ?""",
            (company_profile_id, top_n),
        )
        rows = await cursor.fetchall()
        return [self._row_to_fit(r) for r in rows]

    async def get_fit_recommendation(
        self,
        opportunity_id: str,
        company_profile_id: str,
    ) -> FitRecommendation | None:
        """특정 기회+프로필 조합의 fit 추천 조회."""
        cursor = await self.db.execute(
            """SELECT * FROM fit_recommendations
               WHERE opportunity_id = ? AND company_profile_id = ?""",
            (opportunity_id, company_profile_id),
        )
        row = await cursor.fetchone()
        return self._row_to_fit(row) if row else None

    def _row_to_fit(self, row: aiosqlite.Row) -> FitRecommendation:
        return FitRecommendation(
            id=row["id"],
            opportunity_id=row["opportunity_id"],
            company_profile_id=row["company_profile_id"],
            project_name=row["project_name"],
            fit_score=row["fit_score"],
            priority_score=row["priority_score"],
            why_fit=row["why_fit"],
            next_action=row["next_action"],
            urgency_score=row["urgency_score"],
            actionability_score=row["actionability_score"] if "actionability_score" in row.keys() else None,
            expected_value=row["expected_value"],
            confidence=row["confidence"],
            computed_at=_parse_dt(row["computed_at"]),
        )

    # ============================================================
    # Seed Data
    # ============================================================

    async def load_seed_profile(self, seed_path: Path) -> str:
        """JSON 파일에서 CompanyProfile seed 데이터 로드."""
        if not seed_path.exists():
            raise StoreError(
                message=f"Seed 파일을 찾을 수 없음: {seed_path}",
                fix="data/seed/hoot_profile.json 파일 존재 확인",
                context={"path": str(seed_path)},
            )
        data = json.loads(seed_path.read_text(encoding="utf-8"))
        profile = CompanyProfile(
            id=data["id"],
            company_name=data["company_name"],
            stage=CompanyStage(data["stage"]) if data.get("stage") else None,
            sector_tags=data.get("sector_tags", []),
            projects=data.get("projects", []),
            description=data.get("description"),
            telegram_user_id=data.get("telegram_user_id"),
        )
        # 이미 존재하면 skip
        existing = await self.get_company_profile(profile.id)
        if existing:
            return existing.id
        return await self.create_company_profile(profile)


# ============================================================
# Helpers
# ============================================================

def _parse_dt(value: str | None) -> datetime | None:
    """DB timestamp string → datetime. None이면 None 반환."""
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


# ============================================================
# CLI: python -m src.db.entity_store --init
# ============================================================

if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="EntityStore CLI")
    parser.add_argument("--init", action="store_true", help="DB 초기화 (schema 실행)")
    parser.add_argument("--seed", action="store_true", help="Seed 데이터 로드")
    args = parser.parse_args()

    async def _main() -> None:
        async with EntityStore() as store:
            if args.init:
                await store.init_schema()
                print(f"DB initialized: {store.db_path}")
            if args.seed:
                seed_path = Path("data/seed/hoot_profile.json")
                profile_id = await store.load_seed_profile(seed_path)
                print(f"Seed profile loaded: {profile_id}")

    asyncio.run(_main())
