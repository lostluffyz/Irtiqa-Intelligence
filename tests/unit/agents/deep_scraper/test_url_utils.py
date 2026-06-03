from __future__ import annotations

import pytest

from app.agents.deep_scraper.url_utils import (
    categorize_page_type,
    extract_domain_base_url,
    is_same_domain,
    normalize_url,
    resolve_link,
)


class TestNormalizeUrl:
    def test_strips_trailing_slash(self) -> None:
        assert normalize_url("https://example.com/about/") == "https://example.com/about"

    def test_preserves_root_path(self) -> None:
        assert normalize_url("https://example.com/") == "https://example.com/"

    def test_lowercases_scheme_and_host(self) -> None:
        assert normalize_url("HTTPS://EXAMPLE.COM/About") == "https://example.com/About"

    def test_removes_fragment(self) -> None:
        assert normalize_url("https://example.com/page#section") == "https://example.com/page"

    def test_strips_default_port(self) -> None:
        assert normalize_url("https://example.com:443/page") == "https://example.com/page"

    def test_preserves_non_default_port(self) -> None:
        assert normalize_url("https://example.com:8080/page") == "https://example.com:8080/page"

    def test_defaults_to_https(self) -> None:
        result = normalize_url("//example.com/page")
        assert result.startswith("https://")

    def test_preserves_query_string(self) -> None:
        assert normalize_url("https://example.com/search?q=test") == "https://example.com/search?q=test"


class TestCategorizePageType:
    def test_homepage(self) -> None:
        assert categorize_page_type("https://example.com/") == "homepage"

    def test_about_page(self) -> None:
        assert categorize_page_type("https://example.com/about") == "about"

    def test_pricing_page(self) -> None:
        assert categorize_page_type("https://example.com/pricing") == "pricing"

    def test_contact_page(self) -> None:
        assert categorize_page_type("https://example.com/contact") == "contact"

    def test_blog_page(self) -> None:
        assert categorize_page_type("https://example.com/blog") == "blog"

    def test_careers_page(self) -> None:
        assert categorize_page_type("https://example.com/careers") == "careers"

    def test_product_page(self) -> None:
        assert categorize_page_type("https://example.com/products") == "product"

    def test_unknown_page(self) -> None:
        assert categorize_page_type("https://example.com/some-random-page") == "other"

    def test_subpath_matching(self) -> None:
        assert categorize_page_type("https://example.com/blog/my-post") == "blog"

    def test_case_insensitive(self) -> None:
        assert categorize_page_type("https://example.com/About") == "about"


class TestIsSameDomain:
    def test_exact_match(self) -> None:
        assert is_same_domain("https://example.com/page", "example.com") is True

    def test_www_prefix_on_url(self) -> None:
        assert is_same_domain("https://www.example.com/page", "example.com") is True

    def test_www_prefix_on_domain(self) -> None:
        assert is_same_domain("https://example.com/page", "www.example.com") is True

    def test_different_domain(self) -> None:
        assert is_same_domain("https://other.com/page", "example.com") is False

    def test_subdomain_not_matched(self) -> None:
        assert is_same_domain("https://sub.example.com/page", "example.com") is False


class TestExtractDomainBaseUrl:
    def test_plain_domain(self) -> None:
        assert extract_domain_base_url("example.com") == "https://example.com"

    def test_domain_with_scheme(self) -> None:
        assert extract_domain_base_url("https://example.com") == "https://example.com"

    def test_strips_trailing_slash(self) -> None:
        assert extract_domain_base_url("https://example.com/") == "https://example.com"

    def test_lowercases(self) -> None:
        assert extract_domain_base_url("Example.COM") == "https://example.com"


class TestResolveLink:
    def test_resolves_relative_link(self) -> None:
        result = resolve_link("https://example.com/", "/about", "example.com")
        assert result == "https://example.com/about"

    def test_resolves_absolute_link_same_domain(self) -> None:
        result = resolve_link("https://example.com/", "https://example.com/pricing", "example.com")
        assert result == "https://example.com/pricing"

    def test_rejects_external_link(self) -> None:
        result = resolve_link("https://example.com/", "https://other.com/page", "example.com")
        assert result is None

    def test_rejects_mailto_link(self) -> None:
        result = resolve_link("https://example.com/", "mailto:info@example.com", "example.com")
        assert result is None

    def test_rejects_javascript_link(self) -> None:
        result = resolve_link("https://example.com/", "javascript:void(0)", "example.com")
        assert result is None

    def test_rejects_empty_href(self) -> None:
        result = resolve_link("https://example.com/", "", "example.com")
        assert result is None

    def test_rejects_fragment_only(self) -> None:
        result = resolve_link("https://example.com/", "#top", "example.com")
        assert result is None
