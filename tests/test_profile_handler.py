from __future__ import annotations

import pytest

from src.core.types import CompanyProfile
from src.db.entity_store import EntityStore
from src.interface.handlers.profile_handler import (
    delete_profile_for_user,
    seed_default_profile_for_user,
)


@pytest.mark.asyncio
async def test_seed_default_profile_for_user_creates_hoot_profile(tmp_path):
    async with EntityStore(tmp_path / "test.db") as store:
        await store.init_schema()

        profile = await seed_default_profile_for_user(store, 101, "HOOT")

        assert profile is not None
        assert profile.company_name == "Holo Studio Co., Ltd."
        assert profile.projects[0]["name"] == "HOOT"

        loaded = await store.get_profile_by_telegram_user(101)
        assert loaded is not None
        assert loaded.company_name == "Holo Studio Co., Ltd."


@pytest.mark.asyncio
async def test_seed_default_profile_for_user_updates_existing_profile(tmp_path):
    async with EntityStore(tmp_path / "test.db") as store:
        await store.init_schema()
        await store.create_company_profile(
            CompanyProfile(
                id="cp_existing",
                company_name="Infra",
                telegram_user_id=202,
                projects=[{"name": "null", "priority": 1, "tags": ["web3"]}],
            )
        )

        profile = await seed_default_profile_for_user(store, 202, "HOOT")

        assert profile is not None
        assert profile.company_name == "Holo Studio Co., Ltd."
        assert profile.projects[0]["name"] == "HOOT"


@pytest.mark.asyncio
async def test_delete_profile_for_user_removes_saved_profile(tmp_path):
    async with EntityStore(tmp_path / "test.db") as store:
        await store.init_schema()
        await store.create_company_profile(
            CompanyProfile(
                id="cp_delete",
                company_name="Delete Me",
                telegram_user_id=303,
            )
        )

        deleted = await delete_profile_for_user(store, 303)
        assert deleted is True
        assert await store.get_profile_by_telegram_user(303) is None
