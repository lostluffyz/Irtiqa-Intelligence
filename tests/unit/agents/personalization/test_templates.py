import pytest
from app.agents.personalization.templates import (
    TemplateContext,
    get_template_for_angle,
    render_template,
)

def test_get_template_for_angle_valid():
    template = get_template_for_angle("intent_driven", "email")
    assert template["subject"] is not None
    assert "message_body" in template
    assert template["call_to_action"] is not None

def test_get_template_for_angle_fallback_channel():
    template = get_template_for_angle("intent_driven", "unknown_channel")
    # Should fallback to email
    assert template["subject"] is not None

def test_get_template_for_angle_fallback_angle():
    template = get_template_for_angle("unknown_angle", "linkedin")
    # Should fallback to fit_driven linkedin
    assert template["subject"] is None
    assert "trajectory" in template["message_body"]

def test_render_template_all_fields_present():
    context: TemplateContext = {
        "company_name": "Acme Corp",
        "contact_first_name": "Alice",
        "intent_signal_summary": "Series A funding",
        "technology_name": "React",
        "industry": "Software",
        "domain": "acme.com"
    }
    raw = get_template_for_angle("intent_driven", "email")
    rendered = render_template(raw, context)
    
    assert "Acme Corp" in rendered["subject"]
    assert "Series A funding" in rendered["subject"]
    assert "Alice" in rendered["message_body"]
    assert "Software" in rendered["message_body"]

def test_render_template_missing_fields_uses_fallbacks():
    context: TemplateContext = {
        "company_name": "Acme Corp"
        # missing contact_first_name, intent_signal_summary, etc.
    }
    raw = get_template_for_angle("intent_driven", "email")
    rendered = render_template(raw, context)
    
    assert "Acme Corp" in rendered["subject"]
    assert "recent positive momentum" in rendered["subject"]
    assert "Hi there" in rendered["message_body"]
    assert "your industry" in rendered["message_body"]

def test_render_template_no_cta_or_subject():
    context: TemplateContext = {
        "company_name": "Acme Corp",
        "contact_first_name": "Alice",
    }
    raw = get_template_for_angle("fit_driven", "linkedin")
    rendered = render_template(raw, context)
    
    assert rendered["subject"] is None
    assert rendered["call_to_action"] is None
    assert "Acme Corp" in rendered["message_body"]
    assert "Alice" in rendered["message_body"]
