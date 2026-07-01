from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from app.agents.base import AgentRunOutput, BaseAgent
from app.agents.context import AgentContext
from app.agents.discovery.sources import (
    DiscoverySource,
    GoogleNewsRssDiscoverySource,
    OpenCorporatesDiscoverySource,
    SecEdgarDiscoverySource,
)
from app.agents.discovery.sources.common import DiscoveredCompany, normalize_domain
from app.core.errors import AgentValidationError
from app.schemas.evidence import EvidenceItem
from app.services import CompanyService, DiscoveryRunService


DISCOVERY_PIPELINE_SOURCE = "discovery_pipeline"


@dataclass
class MergedDiscoveryCandidate:
    name: str
    domain: str
    website: str | None = None
    country: str | None = None
    city: str | None = None
    industry: str | None = None
    confidence: float = 0.0
    sources: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)


class DiscoveryAgent(BaseAgent):
    """Orchestrates external discovery sources into persisted company records."""

    name = "discovery"
    version = "1.0.0"

    async def _validate_context(self, context: AgentContext) -> None:
        await super()._validate_context(context)
        if context.organization_id is None:
            raise AgentValidationError(
                "DiscoveryAgent requires organization_id in the agent context.",
                details={"agent_name": self.name, "field": "organization_id"},
            )

        options = dict(context.options)
        for field_name in ("discovery_search_id", "discovery_run_id"):
            value = options.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise AgentValidationError(
                    f"DiscoveryAgent requires {field_name} in context options.",
                    details={"agent_name": self.name, "field": field_name},
                )

        if "criteria" not in options:
            raise AgentValidationError(
                "DiscoveryAgent requires criteria in context options.",
                details={"agent_name": self.name, "field": "criteria"},
            )

    async def _run(self, context: AgentContext) -> AgentRunOutput:
        started_at = time.perf_counter()
        options = dict(context.options)
        organization_id = context.organization_id or ""
        search_id = str(options["discovery_search_id"])
        run_id = str(options["discovery_run_id"])
        criteria = self._normalize_criteria(options["criteria"])

        company_service = self._service("company_service", CompanyService)
        run_service = self._service("discovery_run_service", DiscoveryRunService)

        providers = self._load_providers()
        raw_results: list[DiscoveredCompany] = []
        provider_failures: dict[str, str] = {}

        for provider in providers:
            provider_name = provider.source_name
            self.logger.info(
                "Discovery provider started",
                extra={"provider": provider_name, "discovery_run_id": run_id},
            )
            try:
                provider_results = provider.search(criteria)
            except Exception as exc:
                provider_failures[provider_name] = exc.__class__.__name__
                self.logger.warning(
                    "Discovery provider failed",
                    extra={
                        "provider": provider_name,
                        "discovery_run_id": run_id,
                        "error": exc.__class__.__name__,
                    },
                    exc_info=True,
                )
                continue

            raw_results.extend(provider_results)
            self.logger.info(
                "Discovery provider completed",
                extra={
                    "provider": provider_name,
                    "discovery_run_id": run_id,
                    "discovered_count": len(provider_results),
                },
            )

        candidates, skipped_without_domain = self._deduplicate(raw_results)
        created_company_ids: list[str] = []
        evidence: list[EvidenceItem] = []
        skipped_existing = 0

        # Batch-load existing companies to avoid N+1 queries
        candidate_domains = [c.domain for c in candidates]
        existing_domains = self._get_existing_domains(company_service, candidate_domains, organization_id)

        for candidate in candidates:
            if candidate.domain in existing_domains:
                skipped_existing += 1
                continue

            discovery_score = self._calculate_discovery_score(candidate, criteria)
            company = company_service.create(
                organization_id=organization_id,
                name=candidate.name,
                domain=candidate.domain,
                industry=candidate.industry or self._optional_string(criteria.get("industry")),
                headquarters=self._headquarters(candidate),
                description=self._description(candidate, discovery_score),
                status="needs_review",
                discovered_via=DISCOVERY_PIPELINE_SOURCE,
                discovery_search_id=search_id,
                discovery_score=discovery_score,
            )
            created_company_ids.append(company.id)
            evidence.append(self._build_evidence_item(company.id, candidate, discovery_score))

        companies_found = len(raw_results)
        companies_created = len(created_company_ids)
        companies_skipped = skipped_without_domain + skipped_existing

        run_service.update_statistics(
            run_id,
            organization_id=organization_id,
            sources_queried=len(providers),
            companies_found=companies_found,
            companies_created=companies_created,
            companies_skipped=companies_skipped,
        )

        duration_ms = (time.perf_counter() - started_at) * 1000.0
        self.logger.info(
            "Discovery execution completed",
            extra={
                "discovery_run_id": run_id,
                "discovered_count": companies_found,
                "deduplicated_count": len(candidates),
                "companies_created": companies_created,
                "companies_skipped": companies_skipped,
                "duration_ms": round(duration_ms, 2),
            },
        )

        summary = (
            f"Discovery found {companies_found} candidate(s), deduplicated to "
            f"{len(candidates)}, created {companies_created} companie(s), "
            f"skipped {companies_skipped}."
        )

        return AgentRunOutput(
            output_ids={"companies": created_company_ids},
            evidence=evidence,
            summary=summary,
            stats={
                "sources_queried": len(providers),
                "providers_failed": len(provider_failures),
                "provider_failures": provider_failures,
                "companies_found": companies_found,
                "companies_deduplicated": len(candidates),
                "companies_created": companies_created,
                "companies_skipped": companies_skipped,
                "skipped_without_domain": skipped_without_domain,
                "skipped_existing": skipped_existing,
                "discovery_run_id": run_id,
                "discovery_search_id": search_id,
            },
        )

    def _load_providers(self) -> list[DiscoverySource]:
        configured = self.services.get("discovery_sources")
        if configured is not None:
            return list(configured)
        return [
            SecEdgarDiscoverySource(),
            GoogleNewsRssDiscoverySource(),
            OpenCorporatesDiscoverySource(),
        ]

    def _normalize_criteria(self, criteria: Any) -> dict[str, Any]:
        if isinstance(criteria, str):
            try:
                loaded = json.loads(criteria)
            except json.JSONDecodeError as exc:
                raise AgentValidationError(
                    "Discovery criteria must be valid JSON.",
                    details={"agent_name": self.name, "field": "criteria"},
                    cause=exc,
                ) from exc
            if not isinstance(loaded, dict):
                raise AgentValidationError(
                    "Discovery criteria must decode to an object.",
                    details={"agent_name": self.name, "field": "criteria"},
                )
            return loaded
        if isinstance(criteria, dict):
            return dict(criteria)
        raise AgentValidationError(
            "Discovery criteria must be a dictionary or JSON object string.",
            details={"agent_name": self.name, "field": "criteria"},
        )

    def _deduplicate(
        self,
        discovered: list[DiscoveredCompany],
    ) -> tuple[list[MergedDiscoveryCandidate], int]:
        by_domain: dict[str, MergedDiscoveryCandidate] = {}
        skipped_without_domain = 0

        for company in discovered:
            domain = normalize_domain(company.domain or company.website)
            if domain is None:
                skipped_without_domain += 1
                continue

            existing = by_domain.get(domain)
            if existing is None:
                by_domain[domain] = MergedDiscoveryCandidate(
                    name=company.name,
                    domain=domain,
                    website=company.website,
                    country=company.country,
                    city=company.city,
                    industry=company.industry,
                    confidence=company.confidence,
                    sources={company.source},
                    metadata={company.source: dict(company.metadata)},
                )
                continue

            existing.sources.add(company.source)
            existing.confidence = max(existing.confidence, company.confidence)
            existing.metadata[company.source] = dict(company.metadata)
            if existing.website is None:
                existing.website = company.website
            if existing.country is None:
                existing.country = company.country
            if existing.city is None:
                existing.city = company.city
            if existing.industry is None:
                existing.industry = company.industry
            if len(company.name) > len(existing.name):
                existing.name = company.name

        return list(by_domain.values()), skipped_without_domain

    def _calculate_discovery_score(
        self,
        candidate: MergedDiscoveryCandidate,
        criteria: dict[str, Any],
    ) -> float:
        score = 0.35 + min(candidate.confidence, 1.0) * 0.30

        if len(candidate.sources) > 1:
            score += 0.15
        if candidate.domain:
            score += 0.10
        if self._matches(candidate.industry, criteria.get("industry")):
            score += 0.05
        if self._matches(candidate.country, criteria.get("geography")):
            score += 0.03
        if candidate.website and candidate.city and candidate.country:
            score += 0.02

        return round(min(score, 1.0), 4)

    def _build_evidence_item(
        self,
        company_id: str,
        candidate: MergedDiscoveryCandidate,
        discovery_score: float,
    ) -> EvidenceItem:
        source_detail = ",".join(sorted(candidate.sources))
        return EvidenceItem(
            source_type="agent_run",
            source_id=company_id,
            source_detail=f"Discovery sources: {source_detail}",
            evidence_type="computed_metric",
            evidence_value=(
                f"Discovered {candidate.name} ({candidate.domain}) via "
                f"{source_detail}; discovery_score={discovery_score}"
            ),
            relationship_type="generates",
            target_type="intelligence_score",
            target_id=company_id,
            confidence=discovery_score,
        )

    def _headquarters(self, candidate: MergedDiscoveryCandidate) -> str | None:
        parts = [part for part in (candidate.city, candidate.country) if part]
        if not parts:
            return None
        return ", ".join(parts)

    def _description(self, candidate: MergedDiscoveryCandidate, discovery_score: float) -> str:
        sources = ", ".join(sorted(candidate.sources))
        return (
            f"Discovered by the Lead Discovery Engine via {sources}. "
            f"Discovery score: {discovery_score:.2f}."
        )

    def _matches(self, value: str | None, criterion: Any) -> bool:
        if value is None or not isinstance(criterion, str) or not criterion.strip():
            return False
        return criterion.strip().lower() in value.lower()

    def _optional_string(self, value: Any) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _get_existing_domains(
        self,
        company_service: CompanyService,
        domains: list[str],
        organization_id: str,
    ) -> set[str]:
        """Batch-load existing company domains to avoid N+1 queries."""
        if not domains:
            return set()
        return company_service.get_existing_domains(domains, organization_id)
