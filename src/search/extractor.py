"""
Opportunity Extractor — 2-tier LLM 추출.

Tier 1 (Fast, 8b): 페이지별 구조화 추출
Tier 2 (Strong, 70b): 크로스소스 종합 (중복 병합, 갭 채우기, 모순 감지)
"""

from __future__ import annotations

from datetime import datetime
import json
import re
import time
from urllib.parse import urlparse

import structlog

from src.core.config import Config
from src.search.fetcher import KNOWN_APPLICATION_HOST_TOKENS
from src.search.types import ExtractedOpportunity, FetchedPage

logger = structlog.get_logger()

KNOWN_PROGRAM_TO_ORG = {
    "nitro accelerator": "Monad",
    "chainlink build": "Chainlink",
    "ethereum ecosystem support program": "Ethereum Foundation",
    "near funding": "NEAR",
    "alliance accelerator": "Alliance",
    "outlier ventures base camp": "Outlier Ventures",
    "speedrun": "a16z",
}

KNOWN_SOURCE_HINTS = [
    {
        "patterns": ["nitroacc.xyz"],
        "organization": "Monad",
        "program": "Nitro Accelerator",
    },
    {
        "patterns": ["a16z.com/speedrun", "speedrun.xyz"],
        "organization": "a16z",
        "program": "Speedrun",
    },
    {
        "patterns": ["alliance.xyz/apply"],
        "organization": "Alliance",
        "program": "Alliance Accelerator",
    },
    {
        "patterns": ["outlierventures.io/apply/form", "outlierventures.io/base-camp"],
        "organization": "Outlier Ventures",
        "program": "Outlier Ventures Base Camp",
    },
    {
        "patterns": ["chain.link/build"],
        "organization": "Chainlink",
        "program": "Chainlink BUILD",
    },
    {
        "patterns": ["near.org/funding"],
        "organization": "NEAR",
        "program": "NEAR Funding",
    },
    {
        "patterns": ["momentum.monad.xyz"],
        "organization": "Monad",
        "program": "Monad Momentum",
    },
    {
        "patterns": ["solana.org/grants"],
        "organization": "Solana Foundation",
        "program": "Solana Foundation Grants",
    },
    {
        "patterns": ["arbitrum.foundation/grants"],
        "organization": "Arbitrum Foundation",
        "program": "Arbitrum Grants",
    },
]

# ============================================================
# 페이지별 추출 프롬프트 (Fast LLM용)
# ============================================================

PAGE_EXTRACT_PROMPT = """You are a funding opportunity extraction agent. Extract ALL funding opportunities from the webpage content below.

EXTRACTION RULES:
1. Extract ONLY facts explicitly stated in the content
2. NEVER guess deadlines — if not explicitly stated, set deadline to null
3. For apply_url: Search the "APPLY CANDIDATES" section at the bottom first. It contains scored submission endpoints discovered from the official page.
4. Valid apply_url can be on external form hosts even if the URL itself does not contain the word "apply". Custom Typeform subdomains, Airtable forms, Google Forms, and HubSpot forms are valid.
5. Extract the EXACT budget/funding amount as written
6. For focus_areas: Extract the organization's focus sectors (e.g., "DeFi", "Infrastructure", "Gaming", "AI", "ZK")

OUTPUT FORMAT — Return ONLY a valid JSON array:
[
  {
    "organization": "Funding organization name",
    "program": "Specific program name",
    "category": "grant | accelerator | vc_cohort | ecosystem_builder",
    "status": "open | rolling | upcoming | closed | unknown",
    "deadline": "YYYY-MM-DD or null",
    "budget": "Exact amount text (e.g., '$50K-$500K') or null",
    "apply_url": "URL from APPLY CANDIDATES or content, or null if truly not found",
    "description": "One sentence summary of the program",
    "focus_areas": ["sector1", "sector2"]
  }
]

If no opportunities found, return [].

WEBPAGE CONTENT:
"""

# ============================================================
# 종합 프롬프트 (Strong LLM용)
# ============================================================

SYNTHESIZE_PROMPT = """You are a funding intelligence analyst. You have extracted opportunities from multiple web pages. Now synthesize them into a final deduplicated, enriched list.

TASKS:
1. MERGE duplicates: same organization + same program from different sources → combine info
2. FILL GAPS: if source A has deadline but source B has budget for the same program, combine both
3. DETECT CONTRADICTIONS: if different sources disagree on deadline or status, add a contradiction_note
4. REMOVE IRRELEVANT: remove entries that are not actual funding opportunities
5. CONFIDENCE: assign 0.0-1.0 confidence based on source quality and information completeness
   - 1.0: all fields present, from official source
   - 0.7-0.9: most fields present
   - 0.4-0.6: partial info
   - 0.1-0.3: minimal info, uncertain

OUTPUT FORMAT — Return ONLY a valid JSON array:
[
  {
    "organization": "string",
    "program": "string",
    "category": "grant | accelerator | vc_cohort | ecosystem_builder",
    "status": "open | rolling | upcoming | closed | unknown",
    "deadline": "YYYY-MM-DD or null",
    "budget": "string or null",
    "apply_url": "URL or null",
    "description": "string",
    "focus_areas": ["string"],
    "confidence": 0.0-1.0,
    "source_urls": ["url1", "url2"],
    "contradiction_note": "string or null"
  }
]

RAW EXTRACTED DATA:
"""


class OpportunityExtractor:
    """2-tier LLM 기회 추출기."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._groq_cooldown_until = 0.0

    async def extract_per_page(
        self, pages: list[FetchedPage]
    ) -> list[ExtractedOpportunity]:
        """Fast LLM (8b)으로 페이지별 기회 추출.

        Args:
            pages: 페치된 페이지 리스트

        Returns:
            모든 페이지에서 추출된 기회 리스트 (중복 가능)
        """
        all_opportunities: list[ExtractedOpportunity] = []

        for page in pages:
            if not page.content:
                continue

            try:
                raw_opps = await self._extract_single_page(
                    page.content, page.url
                )
                all_opportunities.extend(raw_opps)
            except Exception as e:
                logger.warning(
                    "search.extractor.page_error",
                    url=page.url,
                    error=str(e),
                )
                continue

        logger.info(
            "search.extractor.per_page_done",
            pages=len(pages),
            opportunities=len(all_opportunities),
        )
        return all_opportunities

    async def synthesize(
        self, opportunities: list[ExtractedOpportunity]
    ) -> list[ExtractedOpportunity]:
        """Strong LLM (70b)으로 크로스소스 종합.

        중복 병합, 갭 채우기, 모순 감지, 무관 결과 제거.
        기회가 적으면 (≤3) LLM 호출 없이 그대로 반환.
        """
        if len(opportunities) <= 3:
            return opportunities

        # Strong LLM 호출
        synthesized = await self._synthesize_with_llm(opportunities)
        if synthesized:
            logger.info(
                "search.extractor.synthesize_done",
                input=len(opportunities),
                output=len(synthesized),
            )
            return synthesized

        # LLM 실패 시 원본 반환 (단순 dedup만)
        return self._simple_dedup(opportunities)

    # ============================================================
    # Internal: Fast LLM 추출
    # ============================================================

    async def _extract_single_page(
        self, content: str, source_url: str
    ) -> list[ExtractedOpportunity]:
        """단일 페이지에서 Fast LLM으로 추출."""
        raw_json = await self._call_fast_llm(
            PAGE_EXTRACT_PROMPT + content
        )
        if not raw_json:
            return self._heuristic_extract_page(content, source_url)

        opps = self._parse_opportunities_json(raw_json, source_url)
        if opps:
            return opps
        return self._heuristic_extract_page(content, source_url)

    async def _call_fast_llm(self, prompt: str) -> str:
        """Fast LLM (8b) 호출."""
        provider = self._config.llm_provider

        if (
            provider == "groq"
            or (provider != "anthropic" and self._config.groq_key)
        ) and not self._groq_rate_limited:
            return await self._call_groq(
                prompt, self._config.llm_model_fast, max_tokens=3000
            )
        elif self._config.anthropic_key:
            return await self._call_anthropic(
                prompt, self._config.llm_model_fast, max_tokens=3000
            )
        return ""

    async def _call_strong_llm(self, prompt: str) -> str:
        """Strong LLM (70b) 호출."""
        if self._config.groq_key and not self._groq_rate_limited:
            return await self._call_groq(
                prompt, self._config.llm_model_strong, max_tokens=4000
            )
        elif self._config.anthropic_key:
            return await self._call_anthropic(
                prompt, self._config.llm_model_strong, max_tokens=4000
            )
        return ""

    async def _call_groq(
        self, prompt: str, model: str, max_tokens: int
    ) -> str:
        """Groq API 호출."""
        try:
            from groq import Groq

            client = Groq(api_key=self._config.groq_key)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.1,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error("search.extractor.groq_error", model=model, error=str(e))
            if _is_quota_error(e):
                self._groq_cooldown_until = time.monotonic() + 300
            return ""

    async def _call_anthropic(
        self, prompt: str, model: str, max_tokens: int
    ) -> str:
        """Anthropic API 호출."""
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self._config.anthropic_key)
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.error("search.extractor.anthropic_error", model=model, error=str(e))
            return ""

    # ============================================================
    # Internal: Strong LLM 종합
    # ============================================================

    async def _synthesize_with_llm(
        self, opportunities: list[ExtractedOpportunity]
    ) -> list[ExtractedOpportunity]:
        """Strong LLM으로 종합."""
        # 기회들을 JSON으로 직렬화
        raw_data = []
        for opp in opportunities:
            raw_data.append({
                "organization": opp.organization,
                "program": opp.program,
                "category": opp.category,
                "status": opp.status,
                "deadline": opp.deadline,
                "budget": opp.budget,
                "apply_url": opp.apply_url,
                "description": opp.description,
                "focus_areas": opp.focus_areas,
                "source_url": opp.source_url,
            })

        prompt = SYNTHESIZE_PROMPT + json.dumps(raw_data, ensure_ascii=False, indent=2)
        raw_response = await self._call_strong_llm(prompt)

        if not raw_response:
            return []

        return self._parse_synthesized_json(raw_response)

    # ============================================================
    # JSON 파싱
    # ============================================================

    @property
    def _groq_rate_limited(self) -> bool:
        return time.monotonic() < self._groq_cooldown_until

    def _parse_opportunities_json(
        self, raw_text: str, source_url: str
    ) -> list[ExtractedOpportunity]:
        """LLM 응답 → ExtractedOpportunity 리스트."""
        parsed = self._extract_json_array(raw_text)
        if not parsed:
            return []

        results: list[ExtractedOpportunity] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            if not item.get("organization") or not item.get("program"):
                continue

            apply_url = self._sanitize_apply_url(item.get("apply_url", ""))

            organization, program = self._canonicalize_names(
                item.get("organization", ""),
                item.get("program", ""),
                source_url=source_url,
                apply_url=apply_url,
                description=item.get("description", ""),
            )

            results.append(
                ExtractedOpportunity(
                    organization=organization,
                    program=program,
                    category=item.get("category", "grant"),
                    status=item.get("status", "unknown"),
                    deadline=item.get("deadline"),
                    budget=item.get("budget"),
                    apply_url=apply_url,
                    description=item.get("description"),
                    focus_areas=item.get("focus_areas", []),
                    source_url=source_url,
                    confidence=float(item.get("confidence", 0.5)),
                )
            )

        return results

    def _parse_synthesized_json(
        self, raw_text: str
    ) -> list[ExtractedOpportunity]:
        """종합 LLM 응답 → ExtractedOpportunity 리스트."""
        parsed = self._extract_json_array(raw_text)
        if not parsed:
            return []

        results: list[ExtractedOpportunity] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            if not item.get("organization") or not item.get("program"):
                continue

            apply_url = self._sanitize_apply_url(item.get("apply_url", ""))

            source_urls = item.get("source_urls", [])
            source_url = source_urls[0] if source_urls else ""
            organization, program = self._canonicalize_names(
                item.get("organization", ""),
                item.get("program", ""),
                source_url=source_url,
                apply_url=apply_url,
                description=item.get("description", ""),
            )

            results.append(
                ExtractedOpportunity(
                    organization=organization,
                    program=program,
                    category=item.get("category", "grant"),
                    status=item.get("status", "unknown"),
                    deadline=item.get("deadline"),
                    budget=item.get("budget"),
                    apply_url=apply_url,
                    description=item.get("description"),
                    focus_areas=item.get("focus_areas", []),
                    source_url=source_url,
                    confidence=float(item.get("confidence", 0.5)),
                )
            )

        return results

    @staticmethod
    def _sanitize_apply_url(apply_url: str | None) -> str | None:
        cleaned = (apply_url or "").strip()
        if not cleaned:
            return None
        if "example.com" in cleaned.lower():
            return None
        if not cleaned.startswith("http"):
            return None
        return cleaned

    @staticmethod
    def _extract_json_array(raw_text: str) -> list[dict]:
        """LLM 응답에서 JSON 배열 추출 (강화)."""
        try:
            text = raw_text

            # markdown 코드블록 추출
            if "```" in text:
                blocks = text.split("```")
                for block in blocks[1:]:
                    cleaned = block.strip()
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:].strip()
                    if cleaned.startswith("["):
                        text = cleaned
                        break

            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1 and end > start:
                text = text[start:end + 1]

            result = json.loads(text)
            return result if isinstance(result, list) else []

        except (json.JSONDecodeError, IndexError):
            return []

    # ============================================================
    # Heuristic fallback extraction
    # ============================================================

    def _heuristic_extract_page(
        self, content: str, source_url: str
    ) -> list[ExtractedOpportunity]:
        """LLM이 실패하거나 quota에 걸릴 때 쓰는 deterministic fallback."""
        normalized = " ".join(content.split())
        lowered = normalized.lower()
        url_lower = source_url.lower()

        if not any(
            keyword in lowered or keyword in url_lower
            for keyword in (
                "grant", "grants", "accelerator", "cohort", "funding",
                "builder program", "support program", "build", "residency",
                "application", "apply",
            )
        ):
            return []

        organization = self._infer_organization(content, source_url)
        program = self._infer_program_name(content, source_url, organization)
        if program and program.lower() in KNOWN_PROGRAM_TO_ORG:
            organization = KNOWN_PROGRAM_TO_ORG[program.lower()]
        if not organization or not program:
            return []

        category = self._infer_category(lowered, url_lower)
        status = self._infer_status(lowered)
        deadline = self._extract_deadline(lowered)
        budget = self._extract_budget(normalized)
        apply_url = self._extract_apply_url(content, source_url)
        description = self._extract_description(content, program)
        focus_areas = self._extract_focus_areas(lowered)
        organization, program = self._canonicalize_names(
            organization,
            program,
            source_url=source_url,
            apply_url=apply_url,
            description=description or "",
        )

        confidence = 0.55 if apply_url else 0.42
        if status in {"open", "rolling"}:
            confidence += 0.05
        if deadline:
            confidence += 0.05

        return [
            ExtractedOpportunity(
                organization=organization,
                program=program,
                category=category,
                status=status,
                deadline=deadline,
                budget=budget,
                apply_url=apply_url,
                description=description,
                focus_areas=focus_areas,
                source_url=source_url,
                confidence=min(0.75, confidence),
            )
        ]

    def _canonicalize_names(
        self,
        organization: str,
        program: str,
        *,
        source_url: str,
        apply_url: str | None,
        description: str,
    ) -> tuple[str, str]:
        text = " ".join([
            organization or "",
            program or "",
            description or "",
            source_url or "",
            apply_url or "",
        ]).lower()

        for hint in KNOWN_SOURCE_HINTS:
            if any(pattern in text for pattern in hint["patterns"]):
                return hint["organization"], hint["program"]

        normalized_program = (program or "").strip().lower()
        if normalized_program in KNOWN_PROGRAM_TO_ORG:
            return KNOWN_PROGRAM_TO_ORG[normalized_program], program

        return organization, program

    @staticmethod
    def _infer_organization(content: str, source_url: str) -> str:
        known_orgs = [
            "Monad", "Chainlink", "Ethereum Foundation", "NEAR", "Solana Foundation",
            "Arbitrum Foundation", "Alliance", "Outlier Ventures", "a16z",
            "Binance Labs", "Techstars", "Avalanche", "Polygon", "Bittensor",
        ]
        lowered = content.lower()
        for org in known_orgs:
            if org.lower() in lowered:
                return org

        host = urlparse(source_url).netloc.lower()
        host = host.replace("www.", "")
        host = host.split(":")[0]
        if host:
            stem = host.split(".")[0].replace("-", " ").strip()
            if stem:
                return " ".join(part.capitalize() for part in stem.split())
        return ""

    @staticmethod
    def _infer_program_name(content: str, source_url: str, organization: str) -> str:
        candidates = [
            "Nitro Accelerator",
            "Chainlink BUILD",
            "Ethereum Ecosystem Support Program",
            "NEAR Funding",
            "Alliance Accelerator",
            "Outlier Ventures Base Camp",
            "Speedrun",
            "Monad Momentum",
            "Solana Foundation Grants",
            "Arbitrum Grants",
        ]
        lowered = content.lower()
        for candidate in candidates:
            if candidate.lower() in lowered:
                return candidate

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        for line in lines[:25]:
            lower_line = line.lower()
            if any(
                token in lower_line
                for token in ("grant", "accelerator", "funding", "build", "cohort", "residency", "program")
            ) and len(line) <= 120:
                return re.sub(r"\s+", " ", line).strip(" -:")

        if organization:
            host = urlparse(source_url).netloc.lower()
            if "grant" in host or "grant" in lowered:
                return f"{organization} Grants"
            if "accelerator" in lowered or "cohort" in lowered:
                return f"{organization} Accelerator"
            if "funding" in lowered:
                return f"{organization} Funding"
        return ""

    @staticmethod
    def _infer_category(lowered: str, url_lower: str) -> str:
        if "build" in lowered or "builder program" in lowered:
            return "builder_program"
        if "accelerator" in lowered or "cohort" in lowered or "residency" in lowered:
            return "accelerator"
        if "funding" in lowered and "grant" not in lowered and "accelerator" not in lowered:
            return "grant"
        if "grant" in lowered or "support program" in lowered or "protocol rewards" in lowered:
            return "grant"
        if "build" in url_lower:
            return "builder_program"
        return "grant"

    @staticmethod
    def _infer_status(lowered: str) -> str:
        if "rolling" in lowered or "reviewed on a rolling basis" in lowered:
            return "rolling"
        if "applications close" in lowered or "deadline" in lowered or "open until" in lowered:
            return "open"
        if "applications are open" in lowered or "apply now" in lowered or "now accepting" in lowered:
            return "open"
        if "upcoming" in lowered or "coming soon" in lowered:
            return "upcoming"
        if "closed" in lowered or "applications closed" in lowered:
            return "closed"
        return "unknown"

    @staticmethod
    def _extract_deadline(lowered: str) -> str | None:
        match = re.search(
            r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),\s*(20\d{2})",
            lowered,
        )
        if not match:
            return None
        month_name, day, year = match.groups()
        try:
            parsed = datetime.strptime(
                f"{month_name.title()} {int(day)} {year}",
                "%B %d %Y",
            )
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            return None

    @staticmethod
    def _extract_budget(content: str) -> str | None:
        match = re.search(
            r"(\$[\d,.]+(?:[KMBkmb])?(?:\s*(?:-|to|–)\s*\$?[\d,.]+(?:[KMBkmb])?)?)",
            content,
        )
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_apply_url(content: str, source_url: str) -> str | None:
        if "APPLY CANDIDATES:" in content:
            _, _, tail = content.partition("APPLY CANDIDATES:")
            candidate_lines = [line.strip() for line in tail.splitlines() if line.strip()]
            for line in candidate_lines:
                if line.startswith("[score=") and "->" in line:
                    candidate = line.split("->", 1)[1].strip().rstrip(".,)")
                    if candidate.startswith("http"):
                        host = urlparse(candidate).netloc.lower()
                        if any(token in host for token in KNOWN_APPLICATION_HOST_TOKENS):
                            return candidate
            for line in candidate_lines:
                if line.startswith("[score=") and "->" in line:
                    candidate = line.split("->", 1)[1].strip().rstrip(".,)")
                    if candidate.startswith("http"):
                        return candidate

        link_matches = re.findall(r"https?://[^\s)>\"]+", content)
        for link in link_matches:
            cleaned = link.rstrip(".,)")
            lowered = cleaned.lower()
            host = urlparse(cleaned).netloc.lower()
            if any(token in host for token in KNOWN_APPLICATION_HOST_TOKENS):
                return cleaned
            if any(token in lowered for token in ("apply", "typeform", "airtable", "grant", "funding", "program", "build", "forms.gle", "docs.google.com/forms")):
                return cleaned
        if any(token in source_url.lower() for token in ("apply", "grant", "funding", "accelerator", "build", "nitroacc")):
            return source_url
        return None

    @staticmethod
    def _extract_description(content: str, program: str) -> str | None:
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        for line in lines[:20]:
            if program.lower() in line.lower():
                continue
            if len(line) >= 40:
                return re.sub(r"\s+", " ", line)[:220]
        return None

    @staticmethod
    def _extract_focus_areas(lowered: str) -> list[str]:
        areas: list[str] = []
        keyword_map = {
            "ai": "AI",
            "infra": "Infrastructure",
            "tooling": "Tooling",
            "developer": "Developer Tools",
            "web3": "Web3",
            "crypto": "Crypto",
            "agent": "Agents",
            "compute": "Compute",
        }
        for token, label in keyword_map.items():
            if token in lowered and label not in areas:
                areas.append(label)
        return areas[:5]

    @staticmethod
    def _simple_dedup(
        opportunities: list[ExtractedOpportunity],
    ) -> list[ExtractedOpportunity]:
        """단순 dedup (org+program 기준)."""
        seen: set[tuple[str, str]] = set()
        deduped: list[ExtractedOpportunity] = []
        for opp in opportunities:
            key = (opp.organization.lower().strip(), opp.program.lower().strip())
            if key not in seen:
                seen.add(key)
                deduped.append(opp)
        return deduped


def _is_quota_error(error: Exception) -> bool:
    text = str(error).lower()
    return (
        "rate limit" in text
        or "rate_limit_exceeded" in text
        or "quota" in text
        or "tokens per day" in text
        or "usage limit" in text
    )
