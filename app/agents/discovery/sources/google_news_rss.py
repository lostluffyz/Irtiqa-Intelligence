from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from typing import Any

from app.agents.discovery.sources.common import (
    BaseDiscoverySource,
    DiscoveredCompany,
    coerce_criteria_list,
    first_criteria_value,
)


COMPANY_SUFFIX_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z0-9&.\-]*(?:\s+[A-Z][A-Za-z0-9&.\-]*){0,4}\s+"
    r"(?:Inc|Corp|Corporation|Company|Co|Ltd|LLC|Technologies|Systems|Labs))\b"
)


class GoogleNewsRssDiscoverySource(BaseDiscoverySource):
    """Searches Google News RSS feeds for company discovery signals."""

    source_name = "google_news_rss"
    base_url = "https://news.google.com/rss/search"

    def search(self, criteria: Mapping[str, Any]) -> list[DiscoveredCompany]:
        if not self.is_enabled():
            self.logger.info("Google News RSS discovery source disabled")
            return []

        query = self._build_query(criteria)
        if query is None:
            self.logger.info("Google News RSS search skipped because criteria produced no query")
            return []

        response = self._get(
            self.base_url,
            params={"q": f"{query} when:30d", "hl": "en-US", "gl": "US", "ceid": "US:en"},
        )
        if response is None:
            return []

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError:
            self.logger.warning("Google News RSS response was malformed XML")
            return []

        companies: list[DiscoveredCompany] = []
        seen_names: set[str] = set()
        for item in root.findall(".//item"):
            title = item.findtext("title") or ""
            link = item.findtext("link")
            published_at = item.findtext("pubDate")
            name = self._extract_company_name(title)
            if name is None:
                continue
            normalized_name = name.lower()
            if normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)
            companies.append(
                DiscoveredCompany(
                    name=name,
                    source=self.source_name,
                    confidence=self._confidence(title),
                    industry=first_criteria_value(criteria, "industry"),
                    metadata={
                        "title": title,
                        "url": link,
                        "published_at": published_at,
                    },
                )
            )
        return companies

    def _build_query(self, criteria: Mapping[str, Any]) -> str | None:
        terms: list[str] = []
        industry = first_criteria_value(criteria, "industry")
        if industry is not None:
            terms.append(industry)
        keywords = coerce_criteria_list(criteria, "keywords")
        terms.extend(keywords)
        if not terms:
            return None
        return " ".join(terms)

    def _extract_company_name(self, title: str) -> str | None:
        match = COMPANY_SUFFIX_PATTERN.search(title)
        if match is not None:
            return match.group(1).strip(" -:")
        if " - " in title:
            candidate = title.split(" - ", 1)[0].strip()
            if candidate and len(candidate.split()) <= 5:
                return candidate
        return None

    def _confidence(self, title: str) -> float:
        lowered = title.lower()
        confidence = 0.55
        for keyword in ("raises", "funding", "series", "launches", "partners", "hiring"):
            if keyword in lowered:
                confidence += 0.05
        return min(confidence, 0.8)
