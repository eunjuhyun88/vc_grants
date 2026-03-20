"""
SocialSearchEngine 단위 테스트.

트위터/X는 discovery candidate source로만 사용되며,
실제 검증 승격은 별도 verification 레이어가 담당한다.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.core.config import Config
from src.core.types import CompanyProfile, CompanyStage
from src.search.engines.social_engine import (
    SocialMonitoringRound,
    SocialWatchAccount,
    SocialPost,
    SocialSearchEngine,
    _build_monitoring_rounds,
    _build_watch_queries,
    _build_x_search_queries,
    _classify_signal_type,
    _expand_official_urls,
    _filter_handles_for_account,
    _extract_social_handles_from_html,
    _is_actionable_social_candidate,
    _load_reference_watch_accounts,
    _load_vc_csv_watch_accounts,
    _merge_watch_accounts,
    _parse_tweet_ref,
    _select_watch_accounts,
    _save_social_watch_accounts,
    _select_apply_url,
)
from src.search.types import SearchResult


@pytest.fixture
def profile() -> CompanyProfile:
    return CompanyProfile(
        id="profile-1",
        company_name="HOOT",
        stage=CompanyStage.MVP,
        sector_tags=["ai_infra", "decentralized_ai", "crypto_infra"],
        target_ecosystems=["ethereum", "solana", "monad"],
    )


@pytest.fixture
def config() -> Config:
    return Config(
        tavily_key="test-tavily",
        serper_key="",
        brave_key="",
        lunarcrush_key="",
    )


class TestTweetRefParsing:
    @pytest.mark.parametrize(
        ("url", "screen_name", "tweet_id"),
        [
            (
                "https://x.com/monad_xyz/status/1234567890123456789",
                "monad_xyz",
                "1234567890123456789",
            ),
            (
                "https://twitter.com/a16zcrypto/status/9876543210987654321?s=20",
                "a16zcrypto",
                "9876543210987654321",
            ),
            (
                "https://www.x.com/alliance_xyz/status/111222333444555666/photo/1",
                "alliance_xyz",
                "111222333444555666",
            ),
        ],
    )
    def test_parse_tweet_ref_status_urls(self, url, screen_name, tweet_id):
        ref = _parse_tweet_ref(url)
        assert ref is not None
        assert ref.screen_name == screen_name
        assert ref.tweet_id == tweet_id

    def test_parse_tweet_ref_rejects_non_status_url(self):
        assert _parse_tweet_ref("https://x.com/monad_xyz") is None


class TestQueryBuilding:
    def test_build_x_search_queries_expands_hosts(self):
        queries = _build_x_search_queries(
            ["ethereum grants", "alliance accelerator"]
        )

        assert 'site:x.com "ethereum grants"' in queries
        assert 'site:twitter.com "ethereum grants"' in queries
        assert 'site:x.com "alliance accelerator"' in queries
        assert 'site:twitter.com "alliance accelerator"' in queries

    def test_build_watch_queries_targets_priority_accounts(
        self,
        profile: CompanyProfile,
        config: Config,
    ):
        queries = _build_watch_queries(
            profile,
            watch_accounts=[
                *SocialSearchEngine(config)._watch_accounts,
            ],
            account_limit=6,
            terms_per_account=2,
        )

        joined = " || ".join(queries).lower()
        assert (
            "monad_xyz" in joined
            or "monad" in joined
            or "ethereum" in joined
            or "solana" in joined
            or "a16zcrypto" in joined
        )
        assert (
            "nearprotocol" in joined
            or "near" in joined
            or "1kx" in joined
            or "cypher capital" in joined
        )
        assert "applications open" in joined or "grant" in joined
        assert "portfolio" not in joined


class TestSignalClassification:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Applications open for Nitro Accelerator now", "applications_open"),
            ("Chainlink community grants are live", "grant_program"),
            ("We are launching a new ecosystem fund", "ecosystem_fund"),
            ("We invested in an AI infra startup", "investment_announcement"),
        ],
    )
    def test_classify_signal_type(self, text: str, expected: str):
        assert _classify_signal_type(text) == expected

    def test_select_apply_url_prefers_form_surface(self):
        url = _select_apply_url([
            "https://alliance.xyz",
            "https://taverncommunity.typeform.com/to/RW1j6BMu",
        ])
        assert url == "https://taverncommunity.typeform.com/to/RW1j6BMu"


class TestOfficialHandleDiscovery:
    def test_extract_social_handles_from_html(self):
        html = """
        <html><body>
          <a href="https://x.com/monad">Monad X</a>
          <a href="https://twitter.com/alliancedao">Alliance X</a>
          <a href="https://x.com/monad/status/123456789">ignore status</a>
          <a href="https://example.com">ignore site</a>
        </body></html>
        """
        handles = _extract_social_handles_from_html(html)
        assert handles == ["monad", "alliancedao"]

    def test_merge_watch_accounts_dedups_same_org_handle(self):
        merged = _merge_watch_accounts(
            [
                SocialWatchAccount(
                    organization="Monad",
                    handle="monad",
                    search_names=["Monad"],
                    official_urls=["https://monad.xyz"],
                )
            ],
            [
                SocialWatchAccount(
                    organization="Monad",
                    handle="monad",
                    search_names=["Monad Foundation"],
                    watch_terms=["nitro accelerator"],
                    official_urls=["https://www.monad.foundation"],
                )
            ],
        )
        assert len(merged) == 1
        assert merged[0].search_names == ["Monad", "Monad Foundation"]
        assert "nitro accelerator" in merged[0].watch_terms
        assert "https://monad.xyz" in merged[0].official_urls
        assert "https://www.monad.foundation" in merged[0].official_urls

    def test_merge_watch_accounts_promotes_discovered_handle_over_blank_seed(self):
        merged = _merge_watch_accounts(
            [
                SocialWatchAccount(
                    organization="2048 Ventures",
                    handle="",
                    search_names=["2048 Ventures"],
                    account_type="vc",
                    official_urls=["https://www.2048.vc/"],
                )
            ],
            [
                SocialWatchAccount(
                    organization="2048 Ventures",
                    handle="2048vc",
                    search_names=["2048 Ventures"],
                    account_type="vc",
                    watch_terms=["applications open"],
                    official_urls=["https://www.2048.vc/"],
                )
            ],
        )
        assert len(merged) == 1
        assert merged[0].handle == "2048vc"
        assert "applications open" in merged[0].watch_terms

    def test_expand_official_urls_adds_root_domain(self):
        urls = _expand_official_urls(["https://alliance.xyz/apply"])
        assert urls == ["https://alliance.xyz/apply", "https://alliance.xyz/"]

    def test_filter_handles_for_account_prefers_org_like_handles(self):
        account = SocialWatchAccount(
            organization="Alliance",
            handle="alliancedao",
            search_names=["Alliance DAO"],
        )
        handles = _filter_handles_for_account(
            ["pumpdotfun", "alliance", "foundersfund"],
            account,
        )
        assert handles == ["alliance"]

    def test_load_reference_watch_accounts_from_seed_rows(self, tmp_path):
        seed_path = tmp_path / "seed_raw.json"
        seed_path.write_text(
            json.dumps(
                [
                    {
                        "organization": "2048 Ventures",
                        "program": "Pre-Seed Fast Track",
                        "category": "fund",
                        "program_type": "vc_fund",
                        "industry_category": "Web2",
                        "website": "https://www.2048.vc/blog/pre-seed-fast-track",
                        "apply_url": "https://airtable.com/app/form",
                    },
                    {
                        "organization": "Ethereum Foundation",
                        "program": "Ecosystem Support Program",
                        "category": "grant",
                        "program_type": "grant",
                        "industry_category": "US",
                        "website": "https://esp.ethereum.foundation/",
                    },
                ]
            ),
            encoding="utf-8",
        )

        accounts = _load_reference_watch_accounts(seed_path, limit=10)

        assert {account.organization for account in accounts} == {
            "2048 Ventures",
            "Ethereum Foundation",
        }
        assert all(account.handle == "" for account in accounts)
        fast_track = next(
            account for account in accounts if account.organization == "2048 Ventures"
        )
        assert fast_track.account_type == "vc"
        assert fast_track.region == "Web2"
        assert fast_track.official_urls == ["https://www.2048.vc/blog/pre-seed-fast-track"]

    def test_save_social_watch_accounts_round_trips(self, tmp_path):
        out_path = tmp_path / "discovered_social_accounts.json"
        _save_social_watch_accounts(
            out_path,
            [
                SocialWatchAccount(
                    organization="Monad",
                    handle="monad",
                    search_names=["Monad"],
                    account_type="l1",
                    official_urls=["https://monad.xyz/"],
                )
            ],
        )

        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert payload["accounts"][0]["organization"] == "Monad"
        assert payload["accounts"][0]["handle"] == "monad"

    def test_load_vc_csv_watch_accounts_preserves_region(self, tmp_path):
        csv_path = tmp_path / "vc_list_final.csv"
        csv_path.write_text(
            "\n".join(
                [
                    "organization,program,program_type,source,status_note,date_note,funding_range,max_amount,website,apply_url,industry_category,sector_tags,description,review_required,review_notes",
                    "1kx,1kx Investment,vc_fund,excel_vc,active=Yes,,,,https://1kx.network/,,EU,,,no,",
                    "Amber Group,Amber Group Investment,vc_fund,excel_vc,active=Yes,,,,https://www.ambrus.studio/,,Asia,,,no,",
                ]
            ),
            encoding="utf-8",
        )

        accounts = _load_vc_csv_watch_accounts(csv_path, limit=10)

        assert {account.organization for account in accounts} == {"1kx", "Amber Group"}
        one_kx = next(account for account in accounts if account.organization == "1kx")
        amber = next(account for account in accounts if account.organization == "Amber Group")
        assert one_kx.region == "EU"
        assert amber.region == "Asia"


class TestActionableSignalRouting:
    def test_investment_announcement_is_not_actionable(self):
        post = SocialPost(
            text="We invested in an AI infra startup",
            signal_type="investment_announcement",
            extracted_urls=["https://example.com/post"],
        )

        assert (
            _is_actionable_social_candidate(
                post,
                apply_url="",
                source_url="https://example.com/post",
            )
            is False
        )

    def test_generic_funding_requires_real_apply_surface(self):
        post = SocialPost(
            text="New ecosystem fund announced",
            signal_type="generic_funding",
            extracted_urls=[],
        )

        assert (
            _is_actionable_social_candidate(
                post,
                apply_url="",
                source_url="",
            )
            is False
        )


class TestRegionalWatchSelection:
    def test_select_watch_accounts_keeps_vc_region_diversity(self):
        ranked = [
            SocialWatchAccount("US Fund A", "usfunda", account_type="vc", priority="tier1", region="US"),
            SocialWatchAccount("US Fund B", "usfundb", account_type="vc", priority="tier1", region="US"),
            SocialWatchAccount("Asia Fund", "asiafund", account_type="vc", priority="tier2", region="Asia"),
            SocialWatchAccount("EU Fund", "eufund", account_type="vc", priority="tier2", region="EU"),
            SocialWatchAccount("Alliance", "alliancedao", account_type="accelerator_operator", priority="tier1"),
            SocialWatchAccount("Ethereum", "ethereum", account_type="foundation", priority="tier1"),
        ]

        selected = _select_watch_accounts(ranked, account_limit=4)
        names = {account.organization for account in selected}

        assert "US Fund A" in names
        assert "Asia Fund" in names
        assert "EU Fund" in names

    def test_build_monitoring_rounds_creates_region_specific_vc_rounds(self, profile: CompanyProfile):
        rounds = _build_monitoring_rounds(
            profile,
            [
                SocialWatchAccount("US Fund A", "usfunda", account_type="vc", priority="tier1", region="US"),
                SocialWatchAccount("US Fund B", "usfundb", account_type="vc", priority="tier1", region="US"),
                SocialWatchAccount("Asia Fund", "asiafund", account_type="vc", priority="tier2", region="Asia"),
                SocialWatchAccount("EU Fund", "eufund", account_type="vc", priority="tier2", region="EU"),
                SocialWatchAccount("Alliance", "alliancedao", account_type="accelerator_operator", priority="tier1"),
                SocialWatchAccount("Ethereum", "ethereum", account_type="foundation", priority="tier1"),
            ],
            account_limit=4,
            terms_per_account=2,
        )

        round_ids = {round_item.round_id for round_item in rounds}
        assert "profile-priority" in round_ids
        assert "vc-us" in round_ids
        assert "vc-asia" in round_ids
        assert "vc-eu" in round_ids
        assert "ecosystem-operators" in round_ids


class TestSocialSearchEngine:
    @pytest.mark.asyncio
    async def test_search_x_via_web_executes_monitoring_rounds(
        self,
        config: Config,
    ):
        engine = SocialSearchEngine(config)

        with patch.object(
            engine._web_search,
            "search_all",
            new_callable=AsyncMock,
            side_effect=[
                [
                    SearchResult(
                        url="https://x.com/monad/status/1234567890123456789",
                        title="Monad Nitro applications open",
                        snippet="Apply now for Nitro",
                        score=0.9,
                        engine="tavily",
                    )
                ],
                [
                    SearchResult(
                        url="https://x.com/a16zcrypto/status/2222222222222222222",
                        title="Speedrun applications open",
                        snippet="Apply now for Speedrun",
                        score=0.85,
                        engine="tavily",
                    )
                ],
            ],
        ), patch.object(
            engine,
            "fetch_tweet",
            new_callable=AsyncMock,
            side_effect=[
                SocialPost(
                    text="Nitro Accelerator applications open https://nitroacc.xyz/apply",
                    url="https://x.com/monad/status/1234567890123456789",
                    author="monad",
                    extracted_urls=["https://nitroacc.xyz/apply"],
                    source="fxtwitter",
                ),
                SocialPost(
                    text="Speedrun applications open https://speedrun.xyz/apply",
                    url="https://x.com/a16zcrypto/status/2222222222222222222",
                    author="a16zcrypto",
                    extracted_urls=["https://speedrun.xyz/apply"],
                    source="fxtwitter",
                ),
            ],
        ):
            posts = await engine._search_x_via_web(
                [],
                watch_rounds=[
                    SocialMonitoringRound(round_id="vc-us", queries=['site:x.com/monad/status "applications open"']),
                    SocialMonitoringRound(round_id="vc-eu", queries=['site:x.com/a16zcrypto/status "applications open"']),
                ],
            )

        assert [post.monitoring_round for post in posts] == ["vc-us", "vc-eu"]

    @pytest.mark.asyncio
    async def test_search_x_via_web_fetches_and_falls_back(
        self,
        config: Config,
    ):
        engine = SocialSearchEngine(config)

        results = [
            SearchResult(
                url="https://x.com/monad_xyz/status/1234567890123456789",
                title="Monad launches Nitro Accelerator",
                snippet="Applications open for Nitro Accelerator https://nitroacc.xyz",
                score=0.9,
                engine="tavily",
            ),
            SearchResult(
                url="https://twitter.com/alliance_xyz/status/2222222222222222222",
                title="Alliance accelerator applications open",
                snippet="Apply now for the next crypto cohort",
                score=0.8,
                engine="tavily",
            ),
        ]

        with patch.object(
            engine._web_search,
            "search_all",
            new_callable=AsyncMock,
            return_value=results,
        ), patch.object(
            engine,
            "fetch_tweet",
            new_callable=AsyncMock,
            side_effect=[
                SocialPost(
                    text="Nitro Accelerator applications open https://nitroacc.xyz",
                    url="https://x.com/monad_xyz/status/1234567890123456789",
                    author="monad_xyz",
                    engagement=500,
                    extracted_urls=["https://nitroacc.xyz"],
                    source="fxtwitter",
                ),
                None,
            ],
        ) as fetch_mock:
            posts = await engine._search_x_via_web(["nitro accelerator"])

        assert len(posts) == 2
        assert posts[0].source == "fxtwitter"
        assert posts[1].source == "search_snippet"
        fetch_mock.assert_any_call("monad_xyz", "1234567890123456789")
        fetch_mock.assert_any_call("alliance_xyz", "2222222222222222222")

    @pytest.mark.asyncio
    async def test_search_returns_raw_social_candidates(
        self,
        config: Config,
        profile: CompanyProfile,
    ):
        engine = SocialSearchEngine(config)

        with patch.object(
            engine,
            "_search_lunarcrush",
            new_callable=AsyncMock,
            return_value=[],
        ), patch.object(
            engine,
            "_search_x_via_web",
            new_callable=AsyncMock,
            return_value=[
                SocialPost(
                    text="Alliance Accelerator applications open https://alliance.xyz/apply",
                    url="https://x.com/alliance_xyz/status/3333333333333333333",
                    author="alliance_xyz",
                    engagement=120,
                    extracted_urls=["https://alliance.xyz/apply"],
                    source="fxtwitter",
                )
            ],
        ):
            raw = await engine.search(profile)

        assert len(raw) == 1
        assert raw[0]["organization"] == "Alliance"
        assert raw[0]["program"] == "Alliance Accelerator"
        assert raw[0]["category"] == "accelerator"
        assert raw[0]["apply_url"] == "https://alliance.xyz/apply"
        assert raw[0]["source_type"] == "social"
        assert raw[0]["confidence"] == 0.45
        assert raw[0]["matched_account"] == "Alliance"
        assert raw[0]["social_signal_type"] == "applications_open"
