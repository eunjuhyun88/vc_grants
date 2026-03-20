"""
SmartFetcher 단위 테스트.

httpx mock — 실제 네트워크 호출 없음.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from src.core.config import Config
from src.search.fetcher import (
    MAX_CONTENT_FRONT,
    MAX_CONTENT_TAIL,
    SmartFetcher,
    extract_apply_surface_candidates,
    extract_apply_surface_candidates_from_text,
    format_apply_surface_block,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def config_with_jina():
    return Config(jina_key="test-jina")


@pytest.fixture
def config_no_jina():
    return Config(jina_key="")


# ============================================================
# SmartFetcher tests
# ============================================================

class TestSmartFetcher:
    def test_jina_available(self, config_with_jina):
        fetcher = SmartFetcher(config_with_jina)
        assert fetcher.jina_available is True

    def test_jina_not_available(self, config_no_jina):
        fetcher = SmartFetcher(config_no_jina)
        assert fetcher.jina_available is False


# ============================================================
# Smart truncate tests
# ============================================================

class TestSmartTruncate:
    def test_short_content_not_truncated(self):
        text = "Short content"
        result = SmartFetcher._smart_truncate(text)
        assert result == text

    def test_exact_limit_not_truncated(self):
        total = MAX_CONTENT_FRONT + MAX_CONTENT_TAIL
        text = "a" * total
        result = SmartFetcher._smart_truncate(text)
        assert result == text
        assert "[... content truncated ...]" not in result

    def test_long_content_truncated(self):
        total = MAX_CONTENT_FRONT + MAX_CONTENT_TAIL
        text = "a" * (total + 1000)
        result = SmartFetcher._smart_truncate(text)
        assert "[... content truncated ...]" in result
        # 앞부분 보존 확인
        assert result[:100] == "a" * 100
        # 뒷부분 보존 확인
        assert result[-100:] == "a" * 100

    def test_truncated_preserves_ends(self):
        front = "FRONT" * 5000  # 25K 앞부분
        tail = "TAIL" * 2000   # 8K 뒷부분
        text = front + tail
        result = SmartFetcher._smart_truncate(text)
        assert result.startswith("FRONT")
        assert result.endswith("TAIL" * 1000)  # 뒷부분 보존


class TestApplySurfaceCandidates:
    def test_extract_candidates_prefers_known_form_hosts(self):
        html = """
        <html><body>
          <a href="https://taverncommunity.typeform.com/to/RW1j6BMu">Apply here</a>
          <a href="/about">About</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")

        candidates = extract_apply_surface_candidates(
            soup,
            base_url="https://www.tavern.xyz/accelerator",
        )

        assert candidates
        assert candidates[0]["url"] == "https://taverncommunity.typeform.com/to/RW1j6BMu"
        assert candidates[0]["host"] == "taverncommunity.typeform.com"

    def test_extract_candidates_resolves_relative_apply_links(self):
        html = """
        <html><body>
          <a href="/apply">Apply now</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")

        candidates = extract_apply_surface_candidates(
            soup,
            base_url="https://alliance.xyz/programs/accelerator",
        )

        assert candidates[0]["url"] == "https://alliance.xyz/apply"
        assert candidates[0]["text"] == "Apply now"

    def test_format_apply_surface_block_includes_structured_lines(self):
        block = format_apply_surface_block(
            [
                {
                    "url": "https://taverncommunity.typeform.com/to/RW1j6BMu",
                    "text": "Apply here",
                    "host": "taverncommunity.typeform.com",
                    "score": 6.0,
                    "reasons": "known_form_host,cta_text",
                }
            ]
        )

        assert "APPLY CANDIDATES:" in block
        assert "taverncommunity.typeform.com" in block
        assert "https://taverncommunity.typeform.com/to/RW1j6BMu" in block

    def test_extract_candidates_from_text_supports_markdown_links(self):
        text = """
        Apply using this form:
        [Apply here](https://taverncommunity.typeform.com/to/RW1j6BMu)
        """

        candidates = extract_apply_surface_candidates_from_text(
            text,
            base_url="https://www.tavern.xyz/accelerator",
        )

        assert candidates
        assert candidates[0]["url"] == "https://taverncommunity.typeform.com/to/RW1j6BMu"
