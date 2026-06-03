"""Technographic Intelligence Agent.

Scans the ``raw_html`` stored by the Deep Scraper Agent and applies
signature-based pattern matching to detect technologies embedded in
a company's web pages.  Findings are persisted as ``Technology``
records via ``TechnologyService``.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup, Comment

from app.agents.base import AgentRunOutput, BaseAgent
from app.agents.context import AgentContext
from app.agents.technographic.scoring import TechnologyDetection, aggregate_detections
from app.agents.technographic.signatures import (
    SIGNATURE_REGISTRY,
    PageSignals,
    TechnologySignature,
    match_technology,
)
from app.core.errors import AgentValidationError
from app.services import TechnologyService, WebsiteService


DEFAULT_MIN_CONFIDENCE = 0.3

VALID_CATEGORIES = frozenset({
    "cms",
    "analytics",
    "frontend_framework",
    "marketing_pixel",
    "hosting",
    "cdn",
    "chat_widget",
    "ecommerce",
})


class TechnographicAgent(BaseAgent):
    """Detects technologies from scraped HTML using signature matching.

    Reads ``Website.raw_html`` via ``WebsiteService``, matches
    against the signature registry, computes confidence scores,
    and persists results as ``Technology`` records.
    """

    name = "technographic"
    version = "1.0.0"

    async def _validate_context(self, context: AgentContext) -> None:
        """Validate base context and agent-specific options."""
        await super()._validate_context(context)

        options = dict(context.options)

        min_confidence = options.get("min_confidence", DEFAULT_MIN_CONFIDENCE)
        if (
            not isinstance(min_confidence, (int, float))
            or min_confidence < 0.0
            or min_confidence > 1.0
        ):
            raise AgentValidationError(
                "min_confidence must be a number between 0.0 and 1.0.",
                details={"min_confidence": min_confidence},
            )

        categories = options.get("categories")
        if categories is not None:
            if not isinstance(categories, list) or not all(
                isinstance(c, str) for c in categories
            ):
                raise AgentValidationError(
                    "categories must be a list of strings.",
                    details={"categories": categories},
                )
            invalid = set(categories) - VALID_CATEGORIES
            if invalid:
                raise AgentValidationError(
                    f"Invalid categories: {sorted(invalid)}.",
                    details={"invalid_categories": sorted(invalid)},
                )

    async def _run(self, context: AgentContext) -> AgentRunOutput:
        """Execute the technographic detection workflow."""
        options = dict(context.options)
        min_confidence: float = options.get("min_confidence", DEFAULT_MIN_CONFIDENCE)
        category_filter: list[str] | None = options.get("categories")

        website_service = self._service("website_service", WebsiteService)
        technology_service = self._service("technology_service", TechnologyService)

        websites = website_service.list_by_company(context.company_id)

        # Filter to signature subset if categories option is set
        if category_filter is not None:
            allowed = frozenset(category_filter)
            signatures = tuple(
                sig for sig in SIGNATURE_REGISTRY if sig.category in allowed
            )
        else:
            signatures = SIGNATURE_REGISTRY

        self.logger.info(
            "Starting technographic analysis",
            extra={
                "company_id": context.company_id,
                "total_websites": len(websites),
                "total_signatures": len(signatures),
            },
        )

        # ── Scan each page ─────────────────────────────────────────
        # per_tech_results: tech_key -> list of (website_id, page_score)
        per_tech_results: dict[str, list[tuple[str, float]]] = defaultdict(list)
        pages_scanned = 0
        pages_skipped_no_html = 0

        for website in websites:
            if not website.raw_html:
                pages_skipped_no_html += 1
                self.logger.debug(
                    "Skipping website without raw_html",
                    extra={"website_id": website.id},
                )
                continue

            signals = self._extract_signals(website.raw_html)
            pages_scanned += 1

            for sig in signatures:
                page_score = match_technology(sig, signals)
                if page_score > 0.0:
                    key = f"{sig.name}::{sig.category}"
                    per_tech_results[key].append((website.id, page_score))

        # ── Aggregate and filter ───────────────────────────────────
        detections: list[TechnologyDetection] = []
        for sig in signatures:
            key = f"{sig.name}::{sig.category}"
            results = per_tech_results.get(key, [])
            detection = aggregate_detections(
                results,
                name=sig.name,
                category=sig.category,
                vendor=sig.vendor,
                total_pages=pages_scanned,
            )
            if detection is not None and detection.confidence >= min_confidence:
                detections.append(detection)

        # ── Persist ────────────────────────────────────────────────
        technology_ids: list[str] = []
        now = datetime.now(timezone.utc)

        for det in detections:
            tech_id = self._persist_technology(
                technology_service=technology_service,
                company_id=context.company_id,
                detection=det,
                agent_run_id=None,  # Will be set after we know the run id
                now=now,
            )
            technology_ids.append(tech_id)

        technologies_created = len(technology_ids)
        technologies_below_threshold = sum(
            1
            for sig in signatures
            for key in [f"{sig.name}::{sig.category}"]
            if key in per_tech_results
            and (
                agg := aggregate_detections(
                    per_tech_results[key],
                    name=sig.name,
                    category=sig.category,
                    vendor=sig.vendor,
                    total_pages=pages_scanned,
                )
            )
            is not None
            and agg.confidence < min_confidence
        )

        summary = (
            f"Detected {technologies_created} technology(ies) across"
            f" {pages_scanned} page(s)."
            f" {technologies_below_threshold} below confidence threshold."
            f" {pages_skipped_no_html} page(s) skipped (no HTML)."
        )

        self.logger.info(
            "Technographic analysis completed",
            extra={
                "company_id": context.company_id,
                "technologies_detected": technologies_created,
                "pages_scanned": pages_scanned,
                "pages_skipped_no_html": pages_skipped_no_html,
            },
        )

        return AgentRunOutput(
            output_ids={"technologies": technology_ids},
            summary=summary,
            stats={
                "pages_scanned": pages_scanned,
                "pages_skipped_no_html": pages_skipped_no_html,
                "technologies_detected": technologies_created,
                "technologies_below_threshold": technologies_below_threshold,
                "min_confidence": min_confidence,
            },
        )

    def _extract_signals(self, raw_html: str) -> PageSignals:
        """Parse HTML once and extract all signal sources."""
        soup = BeautifulSoup(raw_html, "lxml")

        script_srcs: list[str] = []
        inline_scripts_parts: list[str] = []

        for script_tag in soup.find_all("script"):
            src = script_tag.get("src")
            if src:
                script_srcs.append(str(src))
            elif script_tag.string:
                inline_scripts_parts.append(script_tag.string)

        meta_tags: list[tuple[str, str]] = []
        for meta in soup.find_all("meta"):
            name = meta.get("name", "") or meta.get("property", "")
            content = meta.get("content", "")
            if name or content:
                meta_tags.append((str(name), str(content)))

        link_hrefs: list[str] = []
        for link in soup.find_all("link", href=True):
            link_hrefs.append(str(link["href"]))

        html_comments: list[str] = []
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            html_comments.append(str(comment))

        return PageSignals(
            script_srcs=script_srcs,
            meta_tags=meta_tags,
            link_hrefs=link_hrefs,
            inline_scripts="\n".join(inline_scripts_parts),
            html_comments=html_comments,
            full_html=raw_html,
        )

    def _persist_technology(
        self,
        *,
        technology_service: TechnologyService,
        company_id: str,
        detection: TechnologyDetection,
        agent_run_id: str | None,
        now: datetime,
    ) -> str:
        """Create or update a technology record via the service layer."""
        existing = technology_service.get_company_technology(
            company_id=company_id,
            name=detection.name,
            category=detection.category,
        )

        if existing is not None:
            updated = technology_service.update(
                existing.id,
                confidence=detection.confidence,
                last_detected_at=now,
                website_id=detection.best_website_id,
                vendor=detection.vendor,
                detection_method="signature",
            )
            return updated.id

        created = technology_service.create(
            company_id=company_id,
            website_id=detection.best_website_id,
            agent_run_id=agent_run_id,
            name=detection.name,
            category=detection.category,
            vendor=detection.vendor,
            detection_method="signature",
            confidence=detection.confidence,
            first_detected_at=now,
            last_detected_at=now,
        )
        return created.id
