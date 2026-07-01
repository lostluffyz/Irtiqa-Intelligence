from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from app.agents.discovery.sources.common import (
    BaseDiscoverySource,
    DiscoveredCompany,
    coerce_criteria_list,
    first_criteria_value,
)


class SecEdgarDiscoverySource(BaseDiscoverySource):
    """Searches SEC EDGAR full-text filings for company discovery."""

    source_name = "sec_edgar"
    base_url = "https://efts.sec.gov/LATEST/search-index"

    def search(self, criteria: Mapping[str, Any]) -> list[DiscoveredCompany]:
        if not self.is_enabled():
            self.logger.info("SEC EDGAR discovery source disabled")
            return []

        query = self._build_query(criteria)
        if query is None:
            self.logger.info("SEC EDGAR search skipped because criteria produced no query")
            return []

        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        response = self._get(
            self.base_url,
            params={
                "q": query,
                "dateRange": "custom",
                "startdt": start_date.isoformat(),
                "enddt": end_date.isoformat(),
            },
            headers={"User-Agent": self.settings.sec_edgar_user_agent},
        )
        if response is None:
            return []

        try:
            payload = response.json()
        except ValueError:
            self.logger.warning("SEC EDGAR response was not valid JSON")
            return []

        filings = self._extract_filings(payload)
        companies: list[DiscoveredCompany] = []
        seen_names: set[str] = set()
        for filing in filings:
            name = self._extract_company_name(filing)
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
                    confidence=self._confidence(filing),
                    industry=first_criteria_value(criteria, "industry"),
                    metadata={
                        "cik": filing.get("cik") or filing.get("ciks"),
                        "form_type": filing.get("formType") or filing.get("form"),
                        "filed_at": filing.get("filedAt") or filing.get("file_date"),
                        "accession_number": filing.get("adsh") or filing.get("accession_number"),
                    },
                )
            )
        return companies

    def _build_query(self, criteria: Mapping[str, Any]) -> str | None:
        terms: list[str] = []
        industry = first_criteria_value(criteria, "industry")
        if industry is not None:
            terms.append(industry)
        terms.extend(coerce_criteria_list(criteria, "keywords"))
        if not terms:
            return None
        return " ".join(terms)

    def _extract_filings(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            hits = payload.get("hits")
            if isinstance(hits, dict) and isinstance(hits.get("hits"), list):
                return [item.get("_source", item) for item in hits["hits"] if isinstance(item, dict)]
            if isinstance(payload.get("filings"), list):
                return [item for item in payload["filings"] if isinstance(item, dict)]
            if isinstance(payload.get("results"), list):
                return [item for item in payload["results"] if isinstance(item, dict)]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []

    def _extract_company_name(self, filing: Mapping[str, Any]) -> str | None:
        for key in ("entity", "companyName", "company_name", "name"):
            value = filing.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        display_names = filing.get("display_names")
        if isinstance(display_names, list):
            for value in display_names:
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def _confidence(self, filing: Mapping[str, Any]) -> float:
        confidence = 0.7
        if filing.get("cik") or filing.get("ciks"):
            confidence += 0.1
        if filing.get("formType") or filing.get("form"):
            confidence += 0.05
        if filing.get("filedAt") or filing.get("file_date"):
            confidence += 0.05
        return min(confidence, 0.9)
