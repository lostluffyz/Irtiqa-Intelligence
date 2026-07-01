from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.agents.discovery.sources.common import (
    BaseDiscoverySource,
    DiscoveredCompany,
    first_criteria_value,
    normalize_domain,
    normalize_url,
)


class OpenCorporatesDiscoverySource(BaseDiscoverySource):
    """Searches OpenCorporates company records for discovery candidates."""

    source_name = "opencorporates"
    base_url = "https://api.opencorporates.com/v0.4/companies/search"

    def search(self, criteria: Mapping[str, Any]) -> list[DiscoveredCompany]:
        if not self.is_enabled():
            self.logger.info("OpenCorporates discovery source disabled")
            return []

        query = self._build_query(criteria)
        if query is None:
            self.logger.info("OpenCorporates search skipped because criteria produced no query")
            return []

        params: dict[str, Any] = {"q": query, "per_page": 50}
        if self.settings.opencorporates_api_key:
            params["api_token"] = self.settings.opencorporates_api_key
        else:
            self.logger.info("OpenCorporates API key not configured; using public free-tier request")

        response = self._get(self.base_url, params=params)
        if response is None:
            return []

        try:
            payload = response.json()
        except ValueError:
            self.logger.warning("OpenCorporates response was not valid JSON")
            return []

        records = self._extract_records(payload)
        companies: list[DiscoveredCompany] = []
        seen_names: set[str] = set()
        for record in records:
            company = record.get("company") if isinstance(record.get("company"), dict) else record
            if not isinstance(company, dict):
                continue
            name = company.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            normalized_name = name.strip().lower()
            if normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)
            website = normalize_url(company.get("homepage_url") or company.get("website"))
            companies.append(
                DiscoveredCompany(
                    name=name.strip(),
                    source=self.source_name,
                    confidence=self._confidence(company),
                    domain=normalize_domain(website),
                    website=website,
                    country=company.get("jurisdiction_code"),
                    city=company.get("registered_address_in_full"),
                    industry=first_criteria_value(criteria, "industry"),
                    metadata={
                        "company_number": company.get("company_number"),
                        "jurisdiction_code": company.get("jurisdiction_code"),
                        "current_status": company.get("current_status"),
                        "opencorporates_url": company.get("opencorporates_url"),
                    },
                )
            )
        return companies

    def _build_query(self, criteria: Mapping[str, Any]) -> str | None:
        industry = first_criteria_value(criteria, "industry")
        if industry is not None:
            return industry
        keywords = criteria.get("keywords")
        if isinstance(keywords, list):
            for keyword in keywords:
                if isinstance(keyword, str) and keyword.strip():
                    return keyword.strip()
        if isinstance(keywords, str) and keywords.strip():
            return keywords.strip()
        return None

    def _extract_records(self, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        results = payload.get("results")
        if isinstance(results, dict) and isinstance(results.get("companies"), list):
            return [item for item in results["companies"] if isinstance(item, dict)]
        if isinstance(payload.get("companies"), list):
            return [item for item in payload["companies"] if isinstance(item, dict)]
        return []

    def _confidence(self, company: Mapping[str, Any]) -> float:
        confidence = 0.65
        if company.get("company_number"):
            confidence += 0.05
        if company.get("current_status") == "Active":
            confidence += 0.1
        if company.get("homepage_url") or company.get("website"):
            confidence += 0.05
        return min(confidence, 0.85)
