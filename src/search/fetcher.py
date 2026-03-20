"""
Smart Fetcher — Jina Reader + httpx 폴백.

Jina Reader: JS 렌더링 지원, 마크다운 반환.
httpx: 정적 페이지용 폴백 (BeautifulSoup).
동시 최대 5개 (asyncio.Semaphore).
스마트 잘라내기: 앞 20K + 뒤 4K (기존 12K 하드컷 대체).
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup

from src.core.config import Config
from src.search.types import FetchedPage

logger = structlog.get_logger()

# Jina Reader 엔드포인트
JINA_READER_URL = "https://r.jina.ai/"

# 동시 fetch 제한
MAX_CONCURRENT_FETCHES = 5

# 콘텐츠 크기 제한
MAX_CONTENT_FRONT = 20_000  # 앞부분 20K
MAX_CONTENT_TAIL = 4_000    # 뒷부분 4K (CTA/footer 보존)
MIN_CONTENT_LENGTH = 100    # 이것보다 짧으면 폐기

KNOWN_APPLICATION_HOST_TOKENS = (
    "typeform.com",
    "airtable.com",
    "docs.google.com",
    "forms.gle",
    "hubspot.com",
    "hsforms.com",
    "jotform.com",
    "tally.so",
    "fillout.com",
    "formstack.com",
    "surveymonkey.com",
)

APPLY_TEXT_KEYWORDS = (
    "apply",
    "application",
    "submit",
    "sign up",
    "signup",
    "join",
    "register",
    "cohort",
    "grant",
    "funding",
    "builder",
    "residency",
    "founder",
)

APPLY_URL_KEYWORDS = (
    "apply",
    "application",
    "submit",
    "register",
    "form",
    "grant",
    "funding",
    "cohort",
    "residency",
    "builder",
)


def _normalize_host(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "").strip()


def _is_known_application_host(host: str) -> bool:
    return any(token in host for token in KNOWN_APPLICATION_HOST_TOKENS)


def _score_apply_candidate(base_url: str, candidate_url: str, link_text: str) -> tuple[float, list[str]]:
    host = _normalize_host(candidate_url)
    base_host = _normalize_host(base_url)
    lowered_text = (link_text or "").lower()
    lowered_url = candidate_url.lower()
    reasons: list[str] = []
    score = 0.0

    if _is_known_application_host(host):
        score += 4.0
        reasons.append("known_form_host")

    if any(keyword in lowered_text for keyword in APPLY_TEXT_KEYWORDS):
        score += 2.0
        reasons.append("cta_text")

    if any(keyword in lowered_url for keyword in APPLY_URL_KEYWORDS):
        score += 1.5
        reasons.append("apply_like_url")

    if "/to/" in lowered_url and "typeform" in host:
        score += 1.0
        reasons.append("typeform_to_path")

    if host and base_host and host != base_host and not host.endswith(f".{base_host}"):
        score += 0.5
        reasons.append("external_domain")

    return score, reasons


def extract_apply_surface_candidates(
    soup: BeautifulSoup,
    *,
    base_url: str,
    limit: int = 20,
) -> list[dict[str, str | float]]:
    """공식 페이지 내부의 외부 apply surface 후보를 뽑는다."""
    seen: set[str] = set()
    candidates: list[dict[str, str | float]] = []

    for a_tag in soup.find_all("a", href=True):
        href = (a_tag.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        resolved = urljoin(base_url, href)
        link_text = " ".join(a_tag.get_text(" ", strip=True).split())
        score, reasons = _score_apply_candidate(base_url, resolved, link_text)
        host = _normalize_host(resolved)
        if score < 2.0 and not _is_known_application_host(host):
            continue
        url_key = resolved.rstrip("/")
        if url_key in seen:
            continue
        seen.add(url_key)
        candidates.append(
            {
                "url": resolved,
                "text": link_text or "(no link text)",
                "host": host,
                "score": round(score, 2),
                "reasons": ",".join(reasons) or "candidate",
            }
        )

    for form_tag in soup.find_all("form", action=True):
        action = (form_tag.get("action") or "").strip()
        if not action:
            continue
        resolved = urljoin(base_url, action)
        score, reasons = _score_apply_candidate(base_url, resolved, "form action")
        host = _normalize_host(resolved)
        if score < 2.0 and not _is_known_application_host(host):
            continue
        url_key = resolved.rstrip("/")
        if url_key in seen:
            continue
        seen.add(url_key)
        candidates.append(
            {
                "url": resolved,
                "text": "form action",
                "host": host,
                "score": round(score + 0.5, 2),
                "reasons": ",".join([*reasons, "form_action"]),
            }
        )

    candidates.sort(
        key=lambda item: (
            float(item["score"]),
            _is_known_application_host(str(item["host"])),
            len(str(item["text"])),
        ),
        reverse=True,
    )
    return candidates[:limit]


def format_apply_surface_block(candidates: list[dict[str, str | float]]) -> str:
    if not candidates:
        return ""
    lines = ["APPLY CANDIDATES:"]
    for item in candidates:
        lines.append(
            f"[score={item['score']} host={item['host']} reasons={item['reasons']}] "
            f"{item['text']} -> {item['url']}"
        )
    return "\n".join(lines)


def extract_apply_surface_candidates_from_text(
    content: str,
    *,
    base_url: str,
    limit: int = 20,
) -> list[dict[str, str | float]]:
    """Jina markdown/plain text에서 apply surface 후보를 뽑는다."""
    seen: set[str] = set()
    candidates: list[dict[str, str | float]] = []

    for text, raw_url in re.findall(r"\[([^\]]+)\]\((https?://[^)]+)\)", content):
        score, reasons = _score_apply_candidate(base_url, raw_url, text)
        host = _normalize_host(raw_url)
        if score < 2.0 and not _is_known_application_host(host):
            continue
        url_key = raw_url.rstrip("/")
        if url_key in seen:
            continue
        seen.add(url_key)
        candidates.append(
            {
                "url": raw_url,
                "text": text.strip() or "(markdown link)",
                "host": host,
                "score": round(score, 2),
                "reasons": ",".join(reasons) or "candidate",
            }
        )

    for raw_url in re.findall(r"https?://[^\s)>\"']+", content):
        cleaned = raw_url.rstrip(".,)")
        host = _normalize_host(cleaned)
        score, reasons = _score_apply_candidate(base_url, cleaned, "")
        if score < 2.0 and not _is_known_application_host(host):
            continue
        url_key = cleaned.rstrip("/")
        if url_key in seen:
            continue
        seen.add(url_key)
        candidates.append(
            {
                "url": cleaned,
                "text": "(plain url)",
                "host": host,
                "score": round(score, 2),
                "reasons": ",".join(reasons) or "candidate",
            }
        )

    candidates.sort(
        key=lambda item: (
            float(item["score"]),
            _is_known_application_host(str(item["host"])),
        ),
        reverse=True,
    )
    return candidates[:limit]


class SmartFetcher:
    """Jina Reader + httpx 폴백 페이지 수집기."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    @property
    def jina_available(self) -> bool:
        return bool(self._config.jina_key)

    async def fetch_many(
        self, urls: list[str], max_pages: int | None = None
    ) -> list[FetchedPage]:
        """여러 URL 병렬 fetch.

        Args:
            urls: fetch할 URL 리스트
            max_pages: 최대 페이지 수 (None이면 config 사용)

        Returns:
            FetchedPage 리스트 (성공한 것만)
        """
        limit = max_pages or self._config.search_max_pages
        target_urls = urls[:limit]

        tasks = [self._fetch_one(url) for url in target_urls]
        results = await asyncio.gather(*tasks)

        # 성공한 것만 필터
        pages = [p for p in results if p.success and p.content]

        logger.info(
            "search.fetcher.done",
            requested=len(target_urls),
            success=len(pages),
            failed=len(target_urls) - len(pages),
        )
        return pages

    async def _fetch_one(self, url: str) -> FetchedPage:
        """단일 URL fetch (세마포어 제한 내)."""
        async with self._semaphore:
            # Jina Reader 우선 시도
            if self.jina_available:
                page = await self._fetch_jina(url)
                if page.success:
                    return page
                logger.debug(
                    "search.fetcher.jina_fallback",
                    url=url,
                    error=page.error,
                )

            # httpx 폴백
            return await self._fetch_httpx(url)

    async def _fetch_jina(self, url: str) -> FetchedPage:
        """Jina Reader API로 fetch (마크다운 반환)."""
        try:
            headers = {
                "Accept": "text/markdown",
                "X-No-Cache": "true",
            }
            if self._config.jina_key:
                headers["Authorization"] = f"Bearer {self._config.jina_key}"

            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
            ) as client:
                resp = await client.get(
                    f"{JINA_READER_URL}{url}",
                    headers=headers,
                )
                resp.raise_for_status()

            content = resp.text.strip()
            apply_candidates = extract_apply_surface_candidates_from_text(
                content,
                base_url=url,
                limit=20,
            )
            apply_block = format_apply_surface_block(apply_candidates)
            if apply_block:
                content += "\n\n" + apply_block
            content = self._smart_truncate(content)

            if len(content) < MIN_CONTENT_LENGTH:
                return FetchedPage(
                    url=url,
                    success=False,
                    error="content_too_short",
                    fetch_method="jina",
                )

            return FetchedPage(
                url=url,
                content=content,
                content_length=len(content),
                fetch_method="jina",
                success=True,
            )

        except Exception as e:
            return FetchedPage(
                url=url,
                success=False,
                error=str(e),
                fetch_method="jina",
            )

    async def _fetch_httpx(self, url: str) -> FetchedPage:
        """httpx + BeautifulSoup 폴백 (정적 페이지용)."""
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                },
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "lxml")
            apply_candidates = extract_apply_surface_candidates(
                soup,
                base_url=str(resp.url),
                limit=20,
            )

            # 불필요한 태그 제거
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)

            apply_block = format_apply_surface_block(apply_candidates)
            if apply_block:
                text += "\n\n" + apply_block

            text = self._smart_truncate(text)

            if len(text) < MIN_CONTENT_LENGTH:
                return FetchedPage(
                    url=url,
                    success=False,
                    error="content_too_short",
                    fetch_method="httpx",
                )

            return FetchedPage(
                url=url,
                content=text,
                content_length=len(text),
                fetch_method="httpx",
                success=True,
            )

        except Exception as e:
            return FetchedPage(
                url=url,
                success=False,
                error=str(e),
                fetch_method="httpx",
            )

    @staticmethod
    def _smart_truncate(text: str) -> str:
        """스마트 잘라내기: 앞 20K + 뒤 4K (중간 생략).

        기존 12K 하드컷 대체. 하단 CTA/apply 링크 보존.
        """
        total = MAX_CONTENT_FRONT + MAX_CONTENT_TAIL
        if len(text) <= total:
            return text

        front = text[:MAX_CONTENT_FRONT]
        tail = text[-MAX_CONTENT_TAIL:]
        return front + "\n\n[... content truncated ...]\n\n" + tail
