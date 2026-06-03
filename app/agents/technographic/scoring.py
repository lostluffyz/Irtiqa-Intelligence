"""Confidence scoring for technographic detections.

Aggregates per-page detection scores into a single company-level
confidence value for each technology.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TechnologyDetection:
    """Aggregated detection result for a single technology across pages.

    Attributes:
        name: Technology name.
        category: Technology category.
        vendor: Optional vendor name.
        confidence: Aggregated confidence score (``0.0`` – ``1.0``).
        best_website_id: The website ID with the strongest single-page
            detection.
        pages_detected: Number of pages where the technology was found.
    """

    name: str
    category: str
    vendor: str | None
    confidence: float
    best_website_id: str
    pages_detected: int


def compute_confidence(
    page_scores: list[float],
    total_pages: int,
) -> float:
    """Compute company-level confidence from per-page scores.

    Uses a 70/30 weighted formula:

    - **70%** best single-page evidence (``max(page_scores)``)
    - **30%** breadth factor (proportion of pages where detected)

    Returns ``0.0`` when *page_scores* is empty.
    """
    if not page_scores or total_pages <= 0:
        return 0.0

    max_page_score = max(page_scores)
    breadth_factor = min(len(page_scores) / total_pages, 1.0)

    confidence = 0.7 * max_page_score + 0.3 * breadth_factor
    return round(min(confidence, 1.0), 4)


def aggregate_detections(
    per_page_results: list[tuple[str, float]],
    *,
    name: str,
    category: str,
    vendor: str | None,
    total_pages: int,
) -> TechnologyDetection | None:
    """Build a :class:`TechnologyDetection` from per-page evidence.

    Parameters:
        per_page_results: List of ``(website_id, page_score)`` tuples
            for pages where this technology was detected.
        name: Technology name.
        category: Technology category.
        vendor: Optional vendor.
        total_pages: Total number of pages scanned.

    Returns:
        A ``TechnologyDetection`` or ``None`` when no detections exist.
    """
    if not per_page_results:
        return None

    page_scores = [score for _, score in per_page_results]
    confidence = compute_confidence(page_scores, total_pages)

    # Find the website with the strongest individual detection
    best_website_id = max(per_page_results, key=lambda x: x[1])[0]

    return TechnologyDetection(
        name=name,
        category=category,
        vendor=vendor,
        confidence=confidence,
        best_website_id=best_website_id,
        pages_detected=len(per_page_results),
    )
