import pytest

from app.agents.technographic.signatures import (
    PageSignals,
    SignaturePattern,
    TechnologySignature,
    match_pattern,
    match_technology,
)


def test_signature_pattern_literal_match():
    pattern = SignaturePattern(source="script_src", pattern="analytics.js", is_regex=False)
    assert pattern.matches("https://google-analytics.com/analytics.js") is True
    assert pattern.matches("https://example.com/other.js") is False
    # Case-insensitive
    assert pattern.matches("ANALYTICS.JS") is True


def test_signature_pattern_regex_match():
    pattern = SignaturePattern(source="html_content", pattern=r"data-v-\w+", is_regex=True)
    assert pattern.matches('<div data-v-1234abcd="true"></div>') is True
    assert pattern.matches("<div></div>") is False


def test_match_pattern_script_src():
    pattern = SignaturePattern(source="script_src", pattern="gtm.js")
    signals = PageSignals(script_srcs=["https://googletagmanager.com/gtm.js", "main.js"])
    assert match_pattern(pattern, signals) is True

    signals_no_match = PageSignals(script_srcs=["main.js"])
    assert match_pattern(pattern, signals_no_match) is False


def test_match_pattern_meta_tag():
    pattern = SignaturePattern(source="meta_tag", pattern="WordPress")
    signals = PageSignals(meta_tags=[("generator", "WordPress 6.2"), ("viewport", "width=device-width")])
    assert match_pattern(pattern, signals) is True

    signals_no_match = PageSignals(meta_tags=[("generator", "Drupal")])
    assert match_pattern(pattern, signals_no_match) is False


def test_match_pattern_inline_script():
    pattern = SignaturePattern(source="inline_script", pattern="fbq(")
    signals = PageSignals(inline_scripts="!function(f,b,e,v,n,t,s){if(f.fbq)return;... fbq('init', '123');")
    assert match_pattern(pattern, signals) is True

    signals_no_match = PageSignals(inline_scripts="console.log('hello');")
    assert match_pattern(pattern, signals_no_match) is False


def test_match_technology_capping():
    sig = TechnologySignature(
        name="TestTech",
        category="cms",
        patterns=(
            SignaturePattern(source="html_content", pattern="a", weight=0.6),
            SignaturePattern(source="html_content", pattern="b", weight=0.6),
        ),
    )
    signals = PageSignals(full_html="a b")
    score = match_technology(sig, signals)
    # 0.6 + 0.6 = 1.2, capped at 1.0
    assert score == 1.0


def test_match_technology_partial():
    sig = TechnologySignature(
        name="TestTech",
        category="cms",
        patterns=(
            SignaturePattern(source="html_content", pattern="a", weight=0.4),
            SignaturePattern(source="html_content", pattern="c", weight=0.4),
        ),
    )
    signals = PageSignals(full_html="a b")
    score = match_technology(sig, signals)
    # 'a' matches (0.4), 'c' does not
    assert score == 0.4
