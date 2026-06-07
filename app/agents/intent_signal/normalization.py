"""Normalization helpers for intent signal detection."""
from __future__ import annotations

import re


WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(value: str | None) -> str:
    """Normalize free text for deterministic matching."""
    if not value:
        return ""
    normalized = WHITESPACE_RE.sub(" ", value).strip().lower()
    return normalized


def normalize_label(value: str) -> str:
    """Normalize persisted labels without changing their display casing."""
    return WHITESPACE_RE.sub(" ", value).strip()


def normalize_signal_value(value: str | None, *, max_length: int = 500) -> str | None:
    """Normalize and bound a signal value for persistence."""
    if value is None:
        return None
    cleaned = WHITESPACE_RE.sub(" ", value).strip()
    if not cleaned:
        return None
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 3].rstrip() + "..."


def extract_evidence_snippet(
    text: str,
    pattern: str,
    *,
    is_regex: bool,
    window_chars: int,
) -> str | None:
    """Extract a short source snippet around the first pattern match."""
    if not text:
        return None

    flags = re.IGNORECASE | re.MULTILINE
    match: re.Match[str] | None
    if is_regex:
        try:
            match = re.search(pattern, text, flags)
        except re.error:
            return None
    else:
        match = re.search(re.escape(pattern), text, flags)

    if match is None:
        return None

    start = max(match.start() - window_chars, 0)
    end = min(match.end() + window_chars, len(text))
    return normalize_signal_value(text[start:end])


def build_signal_key(
    *,
    company_id: str,
    signal_type: str,
    signal_name: str,
    website_id: str | None,
    technology_id: str | None,
) -> tuple[str, str, str, str | None, str | None]:
    """Build the approved duplicate-detection key."""
    return (
        company_id,
        normalize_text(signal_type),
        normalize_text(signal_name),
        website_id,
        technology_id,
    )
