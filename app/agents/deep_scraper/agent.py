from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from app.agents.base import AgentRunOutput, BaseAgent
from app.agents.context import AgentContext
from app.agents.deep_scraper.url_utils import (
    categorize_page_type,
    extract_domain_base_url,
    normalize_url,
    resolve_link,
)
from app.core.errors import (
    AgentNetworkError,
    AgentRateLimitError,
    AgentTimeoutError,
    AgentValidationError,
)
from app.services import CompanyService, WebsiteService


DEFAULT_CRAWL_DEPTH = 1
DEFAULT_MAX_PAGES = 5
DEFAULT_CONCURRENCY_LIMIT = 3
DEFAULT_USER_AGENT = "IrtiqaBot/1.0"
DEFAULT_TIMEOUT_SECONDS = 10.0

MAX_CRAWL_DEPTH = 5
MAX_MAX_PAGES = 50
MAX_CONCURRENCY_LIMIT = 10
MAX_TIMEOUT_SECONDS = 60.0


class DeepScraperAgent(BaseAgent):
    """Discovers, fetches, and parses web pages for a target company.

    Respects ``robots.txt``, enforces concurrency limits via
    ``asyncio.Semaphore``, and persists results through
    ``WebsiteService``.
    """

    name = "deep_scraper"
    version = "1.0.0"

    async def _validate_context(self, context: AgentContext) -> None:
        """Validate base context and agent-specific options."""
        await super()._validate_context(context)

        options = dict(context.options)

        crawl_depth = options.get("crawl_depth", DEFAULT_CRAWL_DEPTH)
        if not isinstance(crawl_depth, int) or crawl_depth < 0 or crawl_depth > MAX_CRAWL_DEPTH:
            raise AgentValidationError(
                f"crawl_depth must be an integer between 0 and {MAX_CRAWL_DEPTH}.",
                details={"crawl_depth": crawl_depth},
            )

        max_pages = options.get("max_pages", DEFAULT_MAX_PAGES)
        if not isinstance(max_pages, int) or max_pages < 1 or max_pages > MAX_MAX_PAGES:
            raise AgentValidationError(
                f"max_pages must be an integer between 1 and {MAX_MAX_PAGES}.",
                details={"max_pages": max_pages},
            )

        concurrency_limit = options.get("concurrency_limit", DEFAULT_CONCURRENCY_LIMIT)
        if (
            not isinstance(concurrency_limit, int)
            or concurrency_limit < 1
            or concurrency_limit > MAX_CONCURRENCY_LIMIT
        ):
            raise AgentValidationError(
                f"concurrency_limit must be an integer between 1 and {MAX_CONCURRENCY_LIMIT}.",
                details={"concurrency_limit": concurrency_limit},
            )

        timeout_seconds = options.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
        if (
            not isinstance(timeout_seconds, (int, float))
            or timeout_seconds < 1.0
            or timeout_seconds > MAX_TIMEOUT_SECONDS
        ):
            raise AgentValidationError(
                f"timeout_seconds must be a number between 1.0 and {MAX_TIMEOUT_SECONDS}.",
                details={"timeout_seconds": timeout_seconds},
            )

    async def _run(self, context: AgentContext) -> AgentRunOutput:
        """Execute the deep scraping workflow."""
        options = dict(context.options)
        crawl_depth: int = options.get("crawl_depth", DEFAULT_CRAWL_DEPTH)
        max_pages: int = options.get("max_pages", DEFAULT_MAX_PAGES)
        concurrency_limit: int = options.get("concurrency_limit", DEFAULT_CONCURRENCY_LIMIT)
        user_agent: str = options.get("user_agent", DEFAULT_USER_AGENT)
        timeout_seconds: float = options.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)

        company_service = self._service("company_service", CompanyService)
        website_service = self._service("website_service", WebsiteService)

        company = company_service.get_required(context.company_id)
        domain = company.domain
        base_url = extract_domain_base_url(domain)

        self.logger.info(
            "Starting crawl",
            extra={
                "domain": domain,
                "crawl_depth": crawl_depth,
                "max_pages": max_pages,
            },
        )

        robot_parser = await self._fetch_robots_txt(base_url, user_agent, timeout_seconds)

        semaphore = asyncio.Semaphore(concurrency_limit)
        visited: set[str] = set()
        website_ids: list[str] = []
        pages_scraped = 0
        pages_skipped_robots = 0
        pages_failed = 0

        homepage_url = normalize_url(base_url + "/")
        queue: deque[tuple[str, int]] = deque([(homepage_url, 0)])

        async with httpx.AsyncClient(
            headers={"User-Agent": user_agent},
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
        ) as client:
            while queue and pages_scraped < max_pages:
                current_url, depth = queue.popleft()

                if current_url in visited:
                    continue
                visited.add(current_url)

                if not self._is_allowed_by_robots(robot_parser, user_agent, current_url):
                    self.logger.info(
                        "URL disallowed by robots.txt",
                        extra={"url": current_url},
                    )
                    pages_skipped_robots += 1
                    continue

                try:
                    async with semaphore:
                        response = await client.get(current_url)
                except httpx.TimeoutException as exc:
                    self.logger.warning(
                        "Request timed out",
                        extra={"url": current_url},
                    )
                    pages_failed += 1
                    raise AgentTimeoutError(
                        f"HTTP request timed out for {current_url}.",
                        details={"url": current_url, "timeout_seconds": timeout_seconds},
                        cause=exc,
                    )
                except (httpx.ConnectError, httpx.ReadError) as exc:
                    self.logger.warning(
                        "Network error fetching URL",
                        extra={"url": current_url},
                    )
                    pages_failed += 1
                    raise AgentNetworkError(
                        f"Network error fetching {current_url}.",
                        details={"url": current_url},
                        cause=exc,
                    )

                if response.status_code == 429:
                    raise AgentRateLimitError(
                        f"Rate limited on {current_url}.",
                        details={"url": current_url, "status_code": 429},
                    )

                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type:
                    self.logger.debug(
                        "Skipping non-HTML content",
                        extra={"url": current_url, "content_type": content_type},
                    )
                    continue

                raw_html = response.text
                soup = BeautifulSoup(raw_html, "lxml")
                extracted_text = self._extract_text(soup)
                page_type = categorize_page_type(current_url)

                website_id = self._persist_website(
                    website_service=website_service,
                    company_id=context.company_id,
                    url=current_url,
                    page_type=page_type,
                    http_status=response.status_code,
                    raw_html=raw_html,
                    extracted_text=extracted_text,
                )
                website_ids.append(website_id)
                pages_scraped += 1

                self.logger.info(
                    "Page scraped",
                    extra={
                        "url": current_url,
                        "page_type": page_type,
                        "http_status": response.status_code,
                        "depth": depth,
                    },
                )

                if depth < crawl_depth:
                    discovered_links = self._extract_links(soup, current_url, domain)
                    for link in discovered_links:
                        if link not in visited:
                            queue.append((link, depth + 1))

        summary = (
            f"Scraped {pages_scraped} page(s) from {domain}."
            f" Skipped {pages_skipped_robots} URL(s) blocked by robots.txt."
        )

        return AgentRunOutput(
            output_ids={"websites": website_ids},
            summary=summary,
            stats={
                "domain": domain,
                "pages_scraped": pages_scraped,
                "pages_skipped_robots": pages_skipped_robots,
                "pages_failed": pages_failed,
                "crawl_depth": crawl_depth,
                "max_pages": max_pages,
            },
        )

    async def _fetch_robots_txt(
        self,
        base_url: str,
        user_agent: str,
        timeout_seconds: float,
    ) -> RobotFileParser | None:
        """Fetch and parse robots.txt for the target domain.

        Returns ``None`` when robots.txt cannot be fetched or is not
        found, which downstream callers treat as "allow all".
        """
        robots_url = f"{base_url}/robots.txt"

        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": user_agent},
                timeout=httpx.Timeout(timeout_seconds),
                follow_redirects=True,
            ) as client:
                response = await client.get(robots_url)

            if response.status_code == 200:
                rp = RobotFileParser()
                rp.parse(response.text.splitlines())
                self.logger.info(
                    "robots.txt parsed successfully",
                    extra={"url": robots_url},
                )
                return rp

            self.logger.info(
                "robots.txt not found or inaccessible, allowing all URLs",
                extra={"url": robots_url, "status_code": response.status_code},
            )
            return None

        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError):
            self.logger.warning(
                "Failed to fetch robots.txt, allowing all URLs",
                extra={"url": robots_url},
            )
            return None

    def _is_allowed_by_robots(
        self,
        robot_parser: RobotFileParser | None,
        user_agent: str,
        url: str,
    ) -> bool:
        """Check if a URL is allowed by robots.txt.

        Returns ``True`` when no robots.txt was loaded (``None``).
        """
        if robot_parser is None:
            return True
        try:
            return robot_parser.can_fetch(user_agent, url)
        except Exception:
            return True

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """Extract visible text from parsed HTML."""
        for element in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            element.decompose()

        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    def _extract_links(
        self,
        soup: BeautifulSoup,
        current_url: str,
        domain: str,
    ) -> list[str]:
        """Extract and resolve same-domain links from parsed HTML."""
        links: list[str] = []
        for anchor in soup.find_all("a", href=True):
            resolved = resolve_link(current_url, anchor["href"], domain)
            if resolved is not None:
                links.append(resolved)
        return links

    def _persist_website(
        self,
        *,
        website_service: WebsiteService,
        company_id: str,
        url: str,
        page_type: str,
        http_status: int,
        raw_html: str,
        extracted_text: str,
    ) -> str:
        """Create or update a website record via the service layer."""
        normalized = normalize_url(url)
        now = datetime.now(timezone.utc)

        existing = website_service.get_by_normalized_url(normalized)
        if existing is not None:
            updated = website_service.update(
                existing.id,
                url=url,
                page_type=page_type,
                http_status=http_status,
                last_scraped_at=now,
                raw_html=raw_html,
                extracted_text=extracted_text,
            )
            return updated.id

        created = website_service.create(
            company_id=company_id,
            url=url,
            normalized_url=normalized,
            page_type=page_type,
            http_status=http_status,
            last_scraped_at=now,
            raw_html=raw_html,
            extracted_text=extracted_text,
        )
        return created.id
