from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from app.core.config import DiscoverySettings, get_settings
from app.core.logging import get_logger


@dataclass(frozen=True)
class DiscoveredCompany:
    name: str
    source: str
    confidence: float
    domain: str | None = None
    website: str | None = None
    country: str | None = None
    city: str | None = None
    industry: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class DiscoverySource(Protocol):
    source_name: str

    def search(self, criteria: Mapping[str, Any]) -> list[DiscoveredCompany]:
        ...


class BaseDiscoverySource:
    source_name: str

    def __init__(
        self,
        *,
        settings: DiscoverySettings | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings().discovery
        self.client = client or httpx.Client(timeout=self.settings.request_timeout_seconds)
        self._owns_client = client is None
        self.logger = get_logger(f"agents.discovery.sources.{self.source_name}")

    def is_enabled(self) -> bool:
        return self.settings.is_source_enabled(self.source_name)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _get(self, url: str, **kwargs: Any) -> httpx.Response | None:
        for attempt in range(self.settings.retry_count + 1):
            try:
                response = self.client.get(url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.TimeoutException as exc:
                self.logger.warning(
                    "Discovery source request timed out",
                    extra={
                        "source": self.source_name,
                        "url": url,
                        "attempt": attempt + 1,
                    },
                )
                if attempt >= self.settings.retry_count:
                    self.logger.warning(
                        "Discovery source request exhausted retries",
                        extra={"source": self.source_name, "url": url},
                    )
                    return None
            except httpx.HTTPStatusError as exc:
                self.logger.warning(
                    "Discovery source returned unsuccessful status",
                    extra={
                        "source": self.source_name,
                        "url": url,
                        "status_code": exc.response.status_code,
                    },
                )
                if 400 <= exc.response.status_code < 500:
                    return None
                if attempt >= self.settings.retry_count:
                    return None
            except httpx.HTTPError as exc:
                self.logger.warning(
                    "Discovery source request failed",
                    extra={
                        "source": self.source_name,
                        "url": url,
                        "attempt": attempt + 1,
                        "error": exc.__class__.__name__,
                    },
                )
                if attempt >= self.settings.retry_count:
                    return None
        return None


def normalize_domain(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip().lower()
    if not candidate:
        return None
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    hostname = parsed.hostname
    if hostname is None:
        return None
    if hostname.startswith("www."):
        return hostname[4:]
    return hostname


def normalize_url(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    if parsed.hostname is None:
        return None
    return candidate.rstrip("/")


def coerce_criteria_list(criteria: Mapping[str, Any], key: str) -> list[str]:
    value = criteria.get(key)
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item.strip()]
    return []


def first_criteria_value(criteria: Mapping[str, Any], key: str) -> str | None:
    value = criteria.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
