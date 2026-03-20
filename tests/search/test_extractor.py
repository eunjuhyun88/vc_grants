"""
OpportunityExtractor 단위 테스트.

JSON 파싱 로직 테스트 — LLM 호출은 mock.
"""

from __future__ import annotations

import pytest

from src.core.config import Config
from src.search.extractor import OpportunityExtractor
from src.search.types import ExtractedOpportunity


@pytest.fixture
def extractor():
    config = Config(groq_key="", anthropic_key="")
    return OpportunityExtractor(config)


class TestExtractJsonArray:
    def test_clean_json(self, extractor):
        raw = '[{"organization": "Ethereum", "program": "ESP Grants"}]'
        result = extractor._extract_json_array(raw)
        assert len(result) == 1
        assert result[0]["organization"] == "Ethereum"

    def test_markdown_codeblock(self, extractor):
        raw = '''```json
[{"organization": "Solana", "program": "Grants"}]
```'''
        result = extractor._extract_json_array(raw)
        assert len(result) == 1
        assert result[0]["organization"] == "Solana"

    def test_surrounding_text(self, extractor):
        raw = '''Here are the results:
[{"organization": "Near", "program": "Grants"}]
That's all I found.'''
        result = extractor._extract_json_array(raw)
        assert len(result) == 1

    def test_empty_array(self, extractor):
        raw = "[]"
        result = extractor._extract_json_array(raw)
        assert result == []

    def test_invalid_json(self, extractor):
        raw = "this is not json"
        result = extractor._extract_json_array(raw)
        assert result == []

    def test_nested_codeblock(self, extractor):
        raw = '''```
json
[{"organization": "Polygon", "program": "Village"}]
```'''
        result = extractor._extract_json_array(raw)
        assert len(result) == 1


class TestParseOpportunitiesJson:
    def test_valid_entry(self, extractor):
        raw = '''[{
            "organization": "Ethereum Foundation",
            "program": "ESP Grants",
            "category": "grant",
            "status": "open",
            "deadline": "2026-06-30",
            "budget": "$50K-$500K",
            "apply_url": "https://esp.ethereum.foundation/apply",
            "description": "General grants program",
            "focus_areas": ["DeFi", "Infrastructure"]
        }]'''
        result = extractor._parse_opportunities_json(raw, "https://source.com")
        assert len(result) == 1
        opp = result[0]
        assert opp.organization == "Ethereum Foundation"
        assert opp.apply_url == "https://esp.ethereum.foundation/apply"
        assert opp.source_url == "https://source.com"

    def test_filters_example_urls(self, extractor):
        raw = '''[{
            "organization": "Test",
            "program": "Test Grant",
            "apply_url": "https://example.com/apply"
        }]'''
        result = extractor._parse_opportunities_json(raw, "https://source.com")
        assert len(result) == 1
        assert result[0].apply_url is None  # example.com 필터됨

    def test_filters_missing_org_program(self, extractor):
        raw = '''[
            {"organization": "", "program": "Test"},
            {"organization": "Org", "program": ""},
            {"organization": "Valid", "program": "Valid Grant"}
        ]'''
        result = extractor._parse_opportunities_json(raw, "https://source.com")
        assert len(result) == 1
        assert result[0].organization == "Valid"

    def test_keeps_custom_typeform_apply_urls(self, extractor):
        raw = '''[{
            "organization": "Tavern",
            "program": "Tavern Accelerator",
            "apply_url": "https://taverncommunity.typeform.com/to/RW1j6BMu"
        }]'''
        result = extractor._parse_opportunities_json(raw, "https://tavern.xyz")
        assert len(result) == 1
        assert result[0].apply_url == "https://taverncommunity.typeform.com/to/RW1j6BMu"


class TestSimpleDedup:
    def test_removes_duplicates(self, extractor):
        opps = [
            ExtractedOpportunity(organization="Org A", program="Grant X"),
            ExtractedOpportunity(organization="org a", program="grant x"),
            ExtractedOpportunity(organization="Org B", program="Grant Y"),
        ]
        result = extractor._simple_dedup(opps)
        assert len(result) == 2


class TestExtractApplyUrl:
    def test_prefers_apply_candidates_block(self, extractor):
        content = """
        APPLY CANDIDATES:
        [score=6.0 host=taverncommunity.typeform.com reasons=known_form_host,cta_text] Apply here -> https://taverncommunity.typeform.com/to/RW1j6BMu
        [score=2.5 host=tavern.xyz reasons=apply_like_url] Learn more -> https://tavern.xyz/apply
        """

        result = extractor._extract_apply_url(content, "https://tavern.xyz/accelerator")

        assert result == "https://taverncommunity.typeform.com/to/RW1j6BMu"

    def test_falls_back_to_known_form_host_in_raw_links(self, extractor):
        content = "Official application form: https://taverncommunity.typeform.com/to/RW1j6BMu"

        result = extractor._extract_apply_url(content, "https://tavern.xyz/accelerator")

        assert result == "https://taverncommunity.typeform.com/to/RW1j6BMu"

    def test_preserves_different(self, extractor):
        opps = [
            ExtractedOpportunity(organization="Org A", program="Grant X"),
            ExtractedOpportunity(organization="Org A", program="Grant Y"),
        ]
        result = extractor._simple_dedup(opps)
        assert len(result) == 2
