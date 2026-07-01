from __future__ import annotations

import json
from collections.abc import Callable

import httpx

from app.agents.discovery.sources.common import DiscoveredCompany
from app.agents.discovery.sources.google_news_rss import GoogleNewsRssDiscoverySource
from app.agents.discovery.sources.opencorporates import OpenCorporatesDiscoverySource
from app.agents.discovery.sources.sec_edgar import SecEdgarDiscoverySource
from app.core.config import DiscoverySettings


def _settings(
    *,
    enabled_sources: str = "sec_edgar,google_news_rss,opencorporates",
    opencorporates_api_key: str | None = None,
    retry_count: int = 0,
) -> DiscoverySettings:
    return DiscoverySettings(
        sec_edgar_user_agent="IrtiqaTest/1.0 (test@example.com)",
        opencorporates_api_key=opencorporates_api_key,
        enabled_sources=enabled_sources,
        request_timeout_seconds=1.0,
        retry_count=retry_count,
    )


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _criteria() -> dict[str, object]:
    return {
        "industry": "fintech",
        "keywords": ["Series A", "hiring engineer"],
        "technologies": ["hubspot"],
    }


def test_discovered_company_model_carries_normalized_fields() -> None:
    company = DiscoveredCompany(
        name="Acme Corp",
        source="unit_test",
        confidence=0.8,
        domain="acme.test",
        metadata={"source_id": "123"},
    )

    assert company.name == "Acme Corp"
    assert company.source == "unit_test"
    assert company.confidence == 0.8
    assert company.metadata["source_id"] == "123"


def test_sec_edgar_successful_response_normalizes_companies() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == "IrtiqaTest/1.0 (test@example.com)"
        assert "fintech" in str(request.url)
        payload = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "entity": "Acme Financial Corp",
                            "cik": "000123",
                            "formType": "8-K",
                            "filedAt": "2026-06-20",
                        }
                    },
                    {
                        "_source": {
                            "entity": "Acme Financial Corp",
                            "cik": "000123",
                            "formType": "10-K",
                        }
                    },
                ]
            }
        }
        return httpx.Response(200, json=payload)

    source = SecEdgarDiscoverySource(settings=_settings(), client=_client(handler))

    results = source.search(_criteria())

    assert len(results) == 1
    assert results[0].name == "Acme Financial Corp"
    assert results[0].source == "sec_edgar"
    assert results[0].industry == "fintech"
    assert results[0].confidence == 0.9
    assert results[0].metadata["cik"] == "000123"


def test_sec_edgar_handles_malformed_payload() -> None:
    source = SecEdgarDiscoverySource(
        settings=_settings(),
        client=_client(lambda request: httpx.Response(200, text="not-json")),
    )

    assert source.search(_criteria()) == []


def test_sec_edgar_handles_http_failures() -> None:
    source = SecEdgarDiscoverySource(
        settings=_settings(),
        client=_client(lambda request: httpx.Response(503)),
    )

    assert source.search(_criteria()) == []


def test_sec_edgar_retries_timeout_then_succeeds() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.TimeoutException("timeout", request=request)
        return httpx.Response(200, json=[{"companyName": "Retry Corp", "cik": "000456"}])

    source = SecEdgarDiscoverySource(
        settings=_settings(retry_count=1),
        client=_client(handler),
    )

    results = source.search(_criteria())

    assert calls == 2
    assert [company.name for company in results] == ["Retry Corp"]


def test_sec_edgar_provider_disable_returns_empty() -> None:
    source = SecEdgarDiscoverySource(
        settings=_settings(enabled_sources="google_news_rss"),
        client=_client(lambda request: httpx.Response(500)),
    )

    assert source.search(_criteria()) == []


def test_google_news_rss_successful_response_normalizes_companies() -> None:
    xml = """
    <rss>
      <channel>
        <item>
          <title>Acme Labs raises Series A funding - Example News</title>
          <link>https://news.example/acme</link>
          <pubDate>Sat, 20 Jun 2026 10:00:00 GMT</pubDate>
        </item>
        <item>
          <title>Acme Labs raises Series A funding - Duplicate</title>
          <link>https://news.example/acme-2</link>
        </item>
      </channel>
    </rss>
    """
    source = GoogleNewsRssDiscoverySource(
        settings=_settings(),
        client=_client(lambda request: httpx.Response(200, text=xml)),
    )

    results = source.search(_criteria())

    assert len(results) == 1
    assert results[0].name == "Acme Labs"
    assert results[0].source == "google_news_rss"
    assert results[0].industry == "fintech"
    assert results[0].confidence >= 0.65
    assert results[0].metadata["url"] == "https://news.example/acme"


def test_google_news_rss_handles_malformed_xml() -> None:
    source = GoogleNewsRssDiscoverySource(
        settings=_settings(),
        client=_client(lambda request: httpx.Response(200, text="<rss>")),
    )

    assert source.search(_criteria()) == []


def test_google_news_rss_handles_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout", request=request)

    source = GoogleNewsRssDiscoverySource(settings=_settings(), client=_client(handler))

    assert source.search(_criteria()) == []


def test_google_news_rss_provider_disable_returns_empty() -> None:
    source = GoogleNewsRssDiscoverySource(
        settings=_settings(enabled_sources="sec_edgar"),
        client=_client(lambda request: httpx.Response(500)),
    )

    assert source.search(_criteria()) == []


def test_opencorporates_successful_response_normalizes_companies() -> None:
    captured_url = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_url
        captured_url = str(request.url)
        payload = {
            "results": {
                "companies": [
                    {
                        "company": {
                            "name": "Acme Registry Ltd",
                            "company_number": "12345",
                            "jurisdiction_code": "us_de",
                            "current_status": "Active",
                            "homepage_url": "https://www.acmeregistry.example",
                            "opencorporates_url": "https://opencorporates.com/companies/us_de/12345",
                        }
                    }
                ]
            }
        }
        return httpx.Response(200, json=payload)

    source = OpenCorporatesDiscoverySource(
        settings=_settings(opencorporates_api_key="secret-token"),
        client=_client(handler),
    )

    results = source.search(_criteria())

    assert "api_token=secret-token" in captured_url
    assert len(results) == 1
    assert results[0].name == "Acme Registry Ltd"
    assert results[0].domain == "acmeregistry.example"
    assert results[0].website == "https://www.acmeregistry.example"
    assert results[0].confidence == 0.85
    assert results[0].metadata["company_number"] == "12345"


def test_opencorporates_missing_api_key_uses_public_request() -> None:
    captured_url = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_url
        captured_url = str(request.url)
        return httpx.Response(200, json={"results": {"companies": []}})

    source = OpenCorporatesDiscoverySource(settings=_settings(), client=_client(handler))

    assert source.search(_criteria()) == []
    assert "api_token" not in captured_url


def test_opencorporates_handles_malformed_payload() -> None:
    source = OpenCorporatesDiscoverySource(
        settings=_settings(),
        client=_client(lambda request: httpx.Response(200, content=b"{not-json")),
    )

    assert source.search(_criteria()) == []


def test_opencorporates_handles_http_failure() -> None:
    source = OpenCorporatesDiscoverySource(
        settings=_settings(),
        client=_client(lambda request: httpx.Response(429)),
    )

    assert source.search(_criteria()) == []


def test_opencorporates_provider_disable_returns_empty() -> None:
    source = OpenCorporatesDiscoverySource(
        settings=_settings(enabled_sources="sec_edgar"),
        client=_client(lambda request: httpx.Response(500)),
    )

    assert source.search(_criteria()) == []


def test_all_sources_return_common_discovered_company_shape() -> None:
    sec = SecEdgarDiscoverySource(
        settings=_settings(),
        client=_client(lambda request: httpx.Response(200, json=[{"companyName": "Sec Corp"}])),
    )
    rss = GoogleNewsRssDiscoverySource(
        settings=_settings(),
        client=_client(
            lambda request: httpx.Response(
                200,
                text="<rss><channel><item><title>News Corp raises funding</title></item></channel></rss>",
            )
        ),
    )
    opencorporates = OpenCorporatesDiscoverySource(
        settings=_settings(),
        client=_client(
            lambda request: httpx.Response(
                200,
                json={
                    "results": {
                        "companies": [
                            {"company": {"name": "Registry Corp", "current_status": "Active"}}
                        ]
                    }
                },
            )
        ),
    )

    results = [
        *sec.search(_criteria()),
        *rss.search(_criteria()),
        *opencorporates.search(_criteria()),
    ]

    assert results
    assert all(isinstance(company, DiscoveredCompany) for company in results)
    assert {company.source for company in results} == {
        "sec_edgar",
        "google_news_rss",
        "opencorporates",
    }
