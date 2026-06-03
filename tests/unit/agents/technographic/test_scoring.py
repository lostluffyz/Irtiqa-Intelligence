import pytest

from app.agents.technographic.scoring import aggregate_detections, compute_confidence


def test_compute_confidence_empty():
    assert compute_confidence([], 5) == 0.0
    assert compute_confidence([0.5], 0) == 0.0


def test_compute_confidence_single_page():
    # max_score = 0.8, breadth = 1/5 = 0.2
    # conf = 0.7*0.8 + 0.3*0.2 = 0.56 + 0.06 = 0.62
    assert compute_confidence([0.8], 5) == 0.62


def test_compute_confidence_multi_page():
    # max_score = 0.8, breadth = 5/5 = 1.0
    # conf = 0.7*0.8 + 0.3*1.0 = 0.56 + 0.3 = 0.86
    assert compute_confidence([0.8, 0.4, 0.8, 0.5, 0.2], 5) == 0.86


def test_compute_confidence_capping():
    # max_score = 1.0, breadth = 1.0
    # conf = 0.7*1.0 + 0.3*1.0 = 1.0
    assert compute_confidence([1.0, 1.0], 2) == 1.0


def test_aggregate_detections_empty():
    assert aggregate_detections([], name="Tech", category="cms", vendor=None, total_pages=5) is None


def test_aggregate_detections_success():
    results = [
        ("web1", 0.5),
        ("web2", 0.9),  # Best score
        ("web3", 0.4),
    ]
    det = aggregate_detections(results, name="Tech", category="cms", vendor="Vendor", total_pages=3)
    assert det is not None
    assert det.name == "Tech"
    assert det.category == "cms"
    assert det.vendor == "Vendor"
    assert det.best_website_id == "web2"
    assert det.pages_detected == 3
    # conf = 0.7*0.9 + 0.3*1.0 = 0.63 + 0.3 = 0.93
    assert det.confidence == 0.93
