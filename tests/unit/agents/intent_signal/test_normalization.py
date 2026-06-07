from app.agents.intent_signal.normalization import (
    build_signal_key,
    extract_evidence_snippet,
    normalize_label,
    normalize_signal_value,
    normalize_text,
)


def test_normalize_text_lowercases_and_collapses_whitespace() -> None:
    assert normalize_text("  We   Are\nHiring  ") == "we are hiring"
    assert normalize_text(None) == ""


def test_normalize_label_preserves_display_case() -> None:
    assert normalize_label("  Hiring   Activity ") == "Hiring Activity"


def test_normalize_signal_value_bounds_long_text() -> None:
    value = "x" * 600
    normalized = normalize_signal_value(value, max_length=20)
    assert normalized is not None
    assert len(normalized) == 20
    assert normalized.endswith("...")


def test_extract_evidence_snippet_literal() -> None:
    snippet = extract_evidence_snippet(
        "Our company is growing quickly. We are hiring sales roles across the team.",
        "we are hiring",
        is_regex=False,
        window_chars=10,
    )
    assert snippet is not None
    assert "We are hiring" in snippet


def test_extract_evidence_snippet_regex() -> None:
    snippet = extract_evidence_snippet(
        "We announced 40% growth in revenue this quarter.",
        r"\b\d+% growth\b",
        is_regex=True,
        window_chars=5,
    )
    assert snippet is not None
    assert "40% growth" in snippet


def test_build_signal_key_normalizes_signal_fields() -> None:
    key = build_signal_key(
        company_id="company",
        signal_type="Hiring_Activity",
        signal_name=" Hiring for Growth Roles ",
        website_id="website",
        technology_id=None,
    )

    assert key == (
        "company",
        "hiring_activity",
        "hiring for growth roles",
        "website",
        None,
    )
