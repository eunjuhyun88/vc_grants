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
    deserialize_json_field,
    generate_id,
    serialize_json_field,
)
from src.db.queries import (
    CURATED_VIEW_CATEGORY_FILTER,
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
        min_confidence: float = 0.75,
        limit: int = 10,
    ) -> list[dict]:
        """
        Curated View 조회 — Eligibility Filter 적용.
        조건: verified + confidence >= min + tier <= 2 + apply_url + not closed.
        JOIN: organizations, programs, fit_recommendations (LEFT).
        정렬: priority_score DESC, fallback: fact_confidence DESC, days_left ASC.
        """
        sql = CURATED_VIEW_SQL
        params: dict[str, Any] = {
            "company_profile_id": company_profile_id or "",
            "min_confidence": min_confidence,
            "limit": limit,
        }
        if category:
            sql += CURATED_VIEW_CATEGORY_FILTER
            params["category"] = category.value
        sql += CURATED_VIEW_ORDER
        cursor = await self.db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

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
            "SELECT * FROM application_endpoints WHERE opportunity_id = ? AND is_active = TRUE",
            (opportunity_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_endpoint(r) for r in rows]

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
               (id, company_name, stage, sector_tags, projects, description, telegram_user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                profile.id,
                profile.company_name,
                profile.stage.value if profile.stage else None,
                serialize_json_field(profile.sector_tags),
                serialize_json_field(profile.projects),
                profile.description,
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
        if "projects" in fields and isinstance(fields["projects"], list):
            fields["projects"] = serialize_json_field(fields["projects"])
        if "stage" in fields and isinstance(fields["stage"], CompanyStage):
            fields["stage"] = fields["stage"].value
        fields["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [profile_id]
        await self.db.execute(
            f"UPDATE company_profiles SET {set_clause} WHERE id = ?", values
        )
        await self.db.commit()

    def _row_to_profile(self, row: aiosqlite.Row) -> CompanyProfile:
        return CompanyProfile(
            id=row["id"],
            company_name=row["company_name"],
            stage=CompanyStage(row["stage"]) if row["stage"] else None,
            sector_tags=deserialize_json_field(row["sector_tags"]) or [],
            projects=deserialize_json_field(row["projects"]) or [],
            description=row["description"],
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
                urgency_score, expected_value, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(opportunity_id, company_profile_id)
               DO UPDATE SET
                fit_score = excluded.fit_score,
                priority_score = excluded.priority_score,
                why_fit = excluded.why_fit,
                next_action = excluded.next_action,
                urgency_score = excluded.urgency_score,
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
