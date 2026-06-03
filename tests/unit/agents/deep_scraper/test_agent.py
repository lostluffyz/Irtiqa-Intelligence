from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from app.agents.context import AgentContext
from app.agents.deep_scraper.agent import DeepScraperAgent
from app.agents.result import AGENT_STATUS_FAILED, AGENT_STATUS_SUCCEEDED


VALID_COMPANY_ID = "00000000-0000-0000-0000-000000000000"
VALID_AGENT_RUN_ID = "22222222-2222-2222-2222-222222222222"
VALID_WEBSITE_ID = "33333333-3333-3333-3333-333333333333"


ROBOTS_TXT_ALLOW_ALL = "User-agent: *\nAllow: /"
ROBOTS_TXT_DISALLOW_ALL = "User-agent: *\nDisallow: /"
ROBOTS_TXT_DISALLOW_PRICING = "User-agent: *\nDisallow: /pricing"

SIMPLE_HTML = """<!DOCTYPE html>
<html>
<head><title>Example Company</title></head>
<body>
<h1>Welcome to Example</h1>
<p>We build great products.</p>
<a href="/about">About Us</a>
<a href="/pricing">Pricing</a>
<a href="/contact">Contact</a>
</body>
</html>"""

ABOUT_HTML = """<!DOCTYPE html>
<html>
<head><title>About Example</title></head>
<body>
<h1>About Us</h1>
<p>We are a technology company.</p>
<a href="/team">Our Team</a>
</body>
</html>"""


def _mock_company(domain: str = "example.com") -> MagicMock:
    company = MagicMock()
    company.id = VALID_COMPANY_ID
    company.domain = domain
    return company


def _mock_website(website_id: str = VALID_WEBSITE_ID) -> MagicMock:
    website = MagicMock()
    website.id = website_id
    return website


def _mock_services(
    *,
    company_domain: str = "example.com",
    existing_website: MagicMock | None = None,
) -> dict[str, Any]:
    """Create mock services for the agent."""
    agent_run_service = MagicMock()
    mock_run = MagicMock()
    mock_run.id = VALID_AGENT_RUN_ID
    agent_run_service.start_workflow_run.return_value = mock_run
    agent_run_service.mark_succeeded.return_value = mock_run
    agent_run_service.mark_failed.return_value = mock_run

    company_service = MagicMock()
    company_service.get_required.return_value = _mock_company(company_domain)

    website_service = MagicMock()
    website_service.get_by_normalized_url.return_value = existing_website

    created_ids: list[str] = []
    call_counter = {"n": 0}

    def _create_side_effect(**kwargs: Any) -> MagicMock:
        call_counter["n"] += 1
        w = MagicMock()
        w.id = f"aaaaaaaa-aaaa-aaaa-aaaa-{call_counter['n']:012d}"
        created_ids.append(w.id)
        return w

    def _update_side_effect(entity_id: str, **kwargs: Any) -> MagicMock:
        w = MagicMock()
        w.id = entity_id
        return w

    website_service.create.side_effect = _create_side_effect
    website_service.update.side_effect = _update_side_effect

    return {
        "agent_run_service": agent_run_service,
        "company_service": company_service,
        "website_service": website_service,
    }


def _make_context(**overrides: Any) -> AgentContext:
    defaults: dict[str, Any] = {
        "agent_name": "deep_scraper",
        "company_id": VALID_COMPANY_ID,
    }
    defaults.update(overrides)
    return AgentContext(**defaults)


@pytest.mark.asyncio
@respx.mock
async def test_successful_homepage_scrape() -> None:
    """Agent scrapes homepage successfully and persists website record."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_TXT_ALLOW_ALL)
    )
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(
            200,
            text=SIMPLE_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )

    services = _mock_services()
    agent = DeepScraperAgent(**services)
    context = _make_context(options={"crawl_depth": 0, "max_pages": 1})

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_SUCCEEDED
    assert "websites" in result.output_ids
    assert len(result.output_ids["websites"]) == 1
    assert result.stats["pages_scraped"] == 1
    assert result.stats["domain"] == "example.com"

    services["website_service"].create.assert_called_once()
    create_kwargs = services["website_service"].create.call_args
    assert "raw_html" in create_kwargs.kwargs
    assert "extracted_text" in create_kwargs.kwargs
    assert create_kwargs.kwargs["raw_html"] == SIMPLE_HTML
    assert "Welcome to Example" in create_kwargs.kwargs["extracted_text"]


@pytest.mark.asyncio
@respx.mock
async def test_crawl_depth_limit_respected() -> None:
    """Agent only crawls to the specified depth."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_TXT_ALLOW_ALL)
    )
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(
            200,
            text=SIMPLE_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    respx.get("https://example.com/about").mock(
        return_value=httpx.Response(
            200,
            text=ABOUT_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    respx.get("https://example.com/pricing").mock(
        return_value=httpx.Response(
            200,
            text="<html><body>Pricing</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    respx.get("https://example.com/contact").mock(
        return_value=httpx.Response(
            200,
            text="<html><body>Contact</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    # team page should NOT be fetched at depth=1 (it's linked from /about at depth 1)
    respx.get("https://example.com/team").mock(
        return_value=httpx.Response(
            200,
            text="<html><body>Team</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )

    services = _mock_services()
    agent = DeepScraperAgent(**services)
    context = _make_context(options={"crawl_depth": 1, "max_pages": 10})

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_SUCCEEDED
    # homepage (depth 0) + about/pricing/contact (depth 1) = 4
    assert result.stats["pages_scraped"] == 4
    # team page should not have been scraped (depth 2)
    assert len(result.output_ids["websites"]) == 4


@pytest.mark.asyncio
@respx.mock
async def test_max_pages_limit_respected() -> None:
    """Agent stops scraping after reaching max_pages."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_TXT_ALLOW_ALL)
    )
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(
            200,
            text=SIMPLE_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    respx.get("https://example.com/about").mock(
        return_value=httpx.Response(
            200,
            text=ABOUT_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    respx.get("https://example.com/pricing").mock(
        return_value=httpx.Response(
            200,
            text="<html><body>Pricing</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    respx.get("https://example.com/contact").mock(
        return_value=httpx.Response(
            200,
            text="<html><body>Contact</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )

    services = _mock_services()
    agent = DeepScraperAgent(**services)
    context = _make_context(options={"crawl_depth": 1, "max_pages": 2})

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_SUCCEEDED
    assert result.stats["pages_scraped"] == 2
    assert len(result.output_ids["websites"]) == 2


@pytest.mark.asyncio
@respx.mock
async def test_robots_txt_disallowed_url_skipped() -> None:
    """Agent skips URLs disallowed by robots.txt."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_TXT_DISALLOW_PRICING)
    )
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(
            200,
            text=SIMPLE_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    respx.get("https://example.com/about").mock(
        return_value=httpx.Response(
            200,
            text=ABOUT_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    respx.get("https://example.com/contact").mock(
        return_value=httpx.Response(
            200,
            text="<html><body>Contact</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )

    services = _mock_services()
    agent = DeepScraperAgent(**services)
    context = _make_context(options={"crawl_depth": 1, "max_pages": 10})

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_SUCCEEDED
    # homepage + about + contact = 3 pages (pricing skipped)
    assert result.stats["pages_scraped"] == 3
    assert result.stats["pages_skipped_robots"] == 1


@pytest.mark.asyncio
@respx.mock
async def test_robots_txt_disallow_all_returns_empty() -> None:
    """When robots.txt disallows everything, agent returns empty output without error."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_TXT_DISALLOW_ALL)
    )

    services = _mock_services()
    agent = DeepScraperAgent(**services)
    context = _make_context(options={"crawl_depth": 0, "max_pages": 5})

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_SUCCEEDED
    assert result.output_ids.get("websites", []) == []
    assert result.stats["pages_scraped"] == 0
    assert result.stats["pages_skipped_robots"] == 1


@pytest.mark.asyncio
@respx.mock
async def test_http_timeout_raises_structured_error() -> None:
    """Agent translates httpx.TimeoutException to AgentTimeoutError."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_TXT_ALLOW_ALL)
    )
    respx.get("https://example.com/").mock(side_effect=httpx.ReadTimeout("timed out"))

    services = _mock_services()
    agent = DeepScraperAgent(**services)
    context = _make_context(options={"crawl_depth": 0})

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_FAILED
    assert result.error is not None
    assert result.error["code"] == "irtiqa.agent_timeout_error"


@pytest.mark.asyncio
@respx.mock
async def test_http_connect_error_raises_structured_error() -> None:
    """Agent translates httpx.ConnectError to AgentNetworkError."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_TXT_ALLOW_ALL)
    )
    respx.get("https://example.com/").mock(side_effect=httpx.ConnectError("connection refused"))

    services = _mock_services()
    agent = DeepScraperAgent(**services)
    context = _make_context(options={"crawl_depth": 0})

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_FAILED
    assert result.error is not None
    assert result.error["code"] == "irtiqa.agent_network_error"


@pytest.mark.asyncio
@respx.mock
async def test_http_429_raises_rate_limit_error() -> None:
    """Agent translates HTTP 429 to AgentRateLimitError."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_TXT_ALLOW_ALL)
    )
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(
            429,
            text="Rate limited",
            headers={"content-type": "text/html"},
        )
    )

    services = _mock_services()
    agent = DeepScraperAgent(**services)
    context = _make_context(options={"crawl_depth": 0})

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_FAILED
    assert result.error is not None
    assert result.error["code"] == "irtiqa.agent_rate_limit_error"


@pytest.mark.asyncio
async def test_invalid_crawl_depth_rejected() -> None:
    """Agent rejects crawl_depth exceeding maximum."""
    services = _mock_services()
    agent = DeepScraperAgent(**services)
    context = _make_context(options={"crawl_depth": 100})

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_FAILED
    assert result.error is not None
    assert result.error["code"] == "irtiqa.agent_validation_error"


@pytest.mark.asyncio
async def test_invalid_max_pages_rejected() -> None:
    """Agent rejects max_pages below 1."""
    services = _mock_services()
    agent = DeepScraperAgent(**services)
    context = _make_context(options={"max_pages": 0})

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_FAILED
    assert result.error is not None
    assert result.error["code"] == "irtiqa.agent_validation_error"


@pytest.mark.asyncio
async def test_invalid_timeout_rejected() -> None:
    """Agent rejects timeout_seconds outside valid range."""
    services = _mock_services()
    agent = DeepScraperAgent(**services)
    context = _make_context(options={"timeout_seconds": 0.1})

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_FAILED
    assert result.error is not None
    assert result.error["code"] == "irtiqa.agent_validation_error"


@pytest.mark.asyncio
@respx.mock
async def test_existing_website_is_updated() -> None:
    """Agent updates existing website records instead of creating duplicates."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_TXT_ALLOW_ALL)
    )
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(
            200,
            text=SIMPLE_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )

    existing = _mock_website(VALID_WEBSITE_ID)
    services = _mock_services(existing_website=existing)
    agent = DeepScraperAgent(**services)
    context = _make_context(options={"crawl_depth": 0, "max_pages": 1})

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_SUCCEEDED
    assert VALID_WEBSITE_ID in result.output_ids["websites"]
    services["website_service"].update.assert_called_once()
    services["website_service"].create.assert_not_called()


@pytest.mark.asyncio
@respx.mock
async def test_non_html_content_is_skipped() -> None:
    """Agent skips pages with non-HTML content types."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_TXT_ALLOW_ALL)
    )
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(
            200,
            text='{"key": "value"}',
            headers={"content-type": "application/json"},
        )
    )

    services = _mock_services()
    agent = DeepScraperAgent(**services)
    context = _make_context(options={"crawl_depth": 0})

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_SUCCEEDED
    assert result.output_ids.get("websites", []) == []
    assert result.stats["pages_scraped"] == 0


@pytest.mark.asyncio
async def test_robots_txt_fetch_failure_allows_crawl() -> None:
    """When robots.txt cannot be fetched, agent allows all URLs."""
    with respx.mock:
        respx.get("https://example.com/robots.txt").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        respx.get("https://example.com/").mock(
            return_value=httpx.Response(
                200,
                text=SIMPLE_HTML,
                headers={"content-type": "text/html; charset=utf-8"},
            )
        )

        services = _mock_services()
        agent = DeepScraperAgent(**services)
        context = _make_context(options={"crawl_depth": 0, "max_pages": 1})

        result = await agent.execute(context)

        assert result.status == AGENT_STATUS_SUCCEEDED
        assert result.stats["pages_scraped"] == 1


@pytest.mark.asyncio
@respx.mock
async def test_output_ids_populated_correctly() -> None:
    """Agent populates output_ids with all created/updated website IDs."""
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, text=ROBOTS_TXT_ALLOW_ALL)
    )
    respx.get("https://example.com/").mock(
        return_value=httpx.Response(
            200,
            text=SIMPLE_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    respx.get("https://example.com/about").mock(
        return_value=httpx.Response(
            200,
            text=ABOUT_HTML,
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    respx.get("https://example.com/pricing").mock(
        return_value=httpx.Response(
            200,
            text="<html><body>Pricing</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    respx.get("https://example.com/contact").mock(
        return_value=httpx.Response(
            200,
            text="<html><body>Contact</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )

    services = _mock_services()
    agent = DeepScraperAgent(**services)
    context = _make_context(options={"crawl_depth": 1, "max_pages": 10})

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_SUCCEEDED
    assert len(result.output_ids["websites"]) == result.stats["pages_scraped"]
    for wid in result.output_ids["websites"]:
        assert isinstance(wid, str)
        assert len(wid) == 36
