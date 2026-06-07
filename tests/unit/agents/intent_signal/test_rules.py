from app.agents.intent_signal.rules import (
    RULE_REGISTRY,
    SUPPORTED_SIGNAL_TYPES,
    SIGNAL_ENTERPRISE_READINESS,
    SIGNAL_HIRING_ACTIVITY,
    SIGNAL_PRODUCT_LAUNCH_INDICATOR,
    TextPattern,
    TechnologyBoost,
    calculate_specificity_boost,
    match_rule,
    rules_for_signal_types,
)


def test_registry_covers_supported_signal_types() -> None:
    registry_types = {rule.signal_type for rule in RULE_REGISTRY}
    assert registry_types == SUPPORTED_SIGNAL_TYPES


def test_rule_definitions_have_valid_weights_and_scores() -> None:
    for rule in RULE_REGISTRY:
        assert 0.0 <= rule.base_strength <= 1.0
        assert 0.0 <= rule.base_confidence <= 1.0
        assert rule.patterns
        for pattern in rule.patterns:
            assert 0.0 <= pattern.weight <= 1.0
        for boost in rule.technology_boosts:
            assert 0.0 <= boost.weight <= 1.0


def test_text_pattern_literal_match_is_case_insensitive() -> None:
    pattern = TextPattern(pattern="we are hiring", weight=0.4)
    assert pattern.matches("WE ARE HIRING sales roles") is True
    assert pattern.matches("nothing relevant") is False


def test_text_pattern_regex_match() -> None:
    pattern = TextPattern(pattern=r"\bseries [a-e]\b", weight=0.4, is_regex=True)
    assert pattern.matches("we raised a series b") is True
    assert pattern.matches("we wrote a series of posts") is False


def test_match_rule_returns_evidence_for_hiring() -> None:
    rule = next(rule for rule in RULE_REGISTRY if rule.signal_type == SIGNAL_HIRING_ACTIVITY)
    match = match_rule(rule, "Careers: We are hiring sales and RevOps roles in New York.")

    assert match is not None
    assert match.rule.signal_type == SIGNAL_HIRING_ACTIVITY
    assert match.signal_value is not None
    assert "We are hiring" in match.signal_value
    assert match.specificity_boost > 0.0


def test_match_rule_rejects_unrelated_text() -> None:
    rule = next(
        rule for rule in RULE_REGISTRY if rule.signal_type == SIGNAL_PRODUCT_LAUNCH_INDICATOR
    )
    assert match_rule(rule, "This is a generic company overview.") is None


def test_technology_boost_matches_category_and_name() -> None:
    category_boost = TechnologyBoost("category", "analytics", 0.1)
    name_boost = TechnologyBoost("name", "Cloudflare", 0.1)

    assert category_boost.matches(technology_name="Google Analytics", technology_category="analytics")
    assert name_boost.matches(technology_name="Cloudflare CDN", technology_category="cdn")
    assert not name_boost.matches(technology_name="Fastly", technology_category="cdn")


def test_specificity_boost_detects_concrete_terms() -> None:
    boost = calculate_specificity_boost(
        "SOC 2 support for enterprise customers across Europe with 40% growth."
    )
    assert boost == 0.2


def test_rules_for_signal_types_filters_registry() -> None:
    rules = rules_for_signal_types([SIGNAL_ENTERPRISE_READINESS])
    assert len(rules) == 1
    assert rules[0].signal_type == SIGNAL_ENTERPRISE_READINESS
