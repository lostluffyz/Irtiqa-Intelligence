from __future__ import annotations

from urllib.parse import urljoin, urlparse, urlunparse


PAGE_TYPE_MAP: dict[str, str] = {
    "/": "homepage",
    "": "homepage",
    "/about": "about",
    "/about-us": "about",
    "/about-us/": "about",
    "/pricing": "pricing",
    "/plans": "pricing",
    "/contact": "contact",
    "/contact-us": "contact",
    "/blog": "blog",
    "/news": "blog",
    "/careers": "careers",
    "/jobs": "careers",
    "/products": "product",
    "/solutions": "product",
    "/features": "product",
    "/platform": "product",
    "/case-studies": "case_study",
    "/customers": "case_study",
    "/privacy": "legal",
    "/privacy-policy": "legal",
    "/terms": "legal",
    "/terms-of-service": "legal",
    "/resources": "resources",
    "/docs": "resources",
    "/documentation": "resources",
    "/integrations": "integrations",
    "/partners": "partners",
    "/team": "team",
    "/leadership": "team",
}


def normalize_url(url: str) -> str:
    """Standardize a URL for deduplication and unique indexing.

    - Lowercases scheme and host.
    - Strips default ports (80, 443).
    - Removes fragments.
    - Removes trailing slashes (except for the root path).
    - Sorts and preserves query parameters.
    """
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "https").lower()
    hostname = (parsed.hostname or "").lower()

    port = parsed.port
    if port in (80, 443, None):
        netloc = hostname
    else:
        netloc = f"{hostname}:{port}"

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    query = parsed.query
    fragment = ""

    return urlunparse((scheme, netloc, path, parsed.params, query, fragment))


def categorize_page_type(url: str) -> str:
    """Classify a URL into a page type based on its path.

    Returns a page type string like ``'homepage'``, ``'about'``,
    ``'pricing'``, etc.  Falls back to ``'other'`` for unrecognized
    paths.
    """
    parsed = urlparse(url)
    path = parsed.path.lower().rstrip("/")

    if path in PAGE_TYPE_MAP:
        return PAGE_TYPE_MAP[path]

    for known_path, page_type in PAGE_TYPE_MAP.items():
        if known_path and known_path != "/" and path.startswith(known_path):
            return page_type

    return "other"


def is_same_domain(url: str, domain: str) -> bool:
    """Check whether a URL belongs to the given domain.

    Handles ``www.`` prefix variations and subdomain matching.
    """
    parsed = urlparse(url)
    url_host = (parsed.hostname or "").lower()
    target = domain.lower()

    if url_host == target:
        return True
    if url_host == f"www.{target}":
        return True
    if target.startswith("www.") and url_host == target[4:]:
        return True
    return False


def extract_domain_base_url(domain: str) -> str:
    """Build the HTTPS base URL for a given domain."""
    clean = domain.strip().lower()
    if clean.startswith("http://") or clean.startswith("https://"):
        return clean.rstrip("/")
    return f"https://{clean}"


def resolve_link(base_url: str, href: str, domain: str) -> str | None:
    """Resolve a relative or absolute link against a base URL.

    Returns the normalized absolute URL if it belongs to the same
    domain and uses HTTP(S).  Returns ``None`` otherwise.
    """
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None

    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)

    if parsed.scheme not in ("http", "https"):
        return None

    if not is_same_domain(absolute, domain):
        return None

    return normalize_url(absolute)
