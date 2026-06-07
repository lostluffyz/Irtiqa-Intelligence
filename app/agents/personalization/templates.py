import string
from typing import TypedDict

class TemplateContext(TypedDict, total=False):
    company_name: str
    contact_first_name: str
    intent_signal_summary: str
    technology_name: str
    industry: str
    domain: str

class TemplateVariant(TypedDict):
    subject: str | None
    message_body: str
    call_to_action: str | None

def _safe_substitute(template: str, context: TemplateContext) -> str:
    """Safely substitutes variables into a template, ignoring missing ones."""
    # Convert context to defaultdict-like behavior using SafeDict
    class SafeDict(dict):
        def __missing__(self, key):
            # Fallback values for common fields
            if key == "contact_first_name":
                return "there"
            if key == "intent_signal_summary":
                return "recent positive momentum"
            if key == "technology_name":
                return "your current stack"
            if key == "company_name":
                return "your company"
            if key == "industry":
                return "your industry"
            if key == "domain":
                return "your site"
            return "{" + key + "}"

    safe_context = SafeDict(context)
    # Use string.Template for safe substitution. Note: requires $var syntax, 
    # but since the prompt mentioned {var}, let's use str.format with safe wrapper.
    
    # Actually, Python's str.format is tricky with missing keys. string.Template is safer.
    # Let's convert {} to $ for string.Template internally, or just use string.Formatter.
    import string
    
    class SafeFormatter(string.Formatter):
        def get_value(self, key, args, kwargs):
            if isinstance(key, str):
                return kwargs.get(key, SafeDict()[key])
            return super().get_value(key, args, kwargs)
            
    formatter = SafeFormatter()
    return formatter.format(template, **context)


# Templates definition
TEMPLATES = {
    "email": {
        "intent_driven": {
            "subject": "Quick question about {company_name}'s {intent_signal_summary}",
            "message_body": "Hi {contact_first_name},\n\nI noticed {company_name} has had some {intent_signal_summary} recently. Given this growth, I thought it might be a good time to connect. We help companies in {industry} streamline their operations during expansion.",
            "call_to_action": "Do you have 10 minutes next Tuesday to discuss how we could support your growth?",
        },
        "tech_driven": {
            "subject": "Optimizing {technology_name} at {company_name}",
            "message_body": "Hi {contact_first_name},\n\nI saw that {company_name} is currently leveraging {technology_name}. We've worked with several similar teams to maximize their ROI on {technology_name} by integrating our platform.",
            "call_to_action": "Would you be open to a brief chat about your experience with {technology_name}?",
        },
        "fit_driven": {
            "subject": "Ideas for {company_name}",
            "message_body": "Hi {contact_first_name},\n\nI've been following {company_name} and am really impressed by your work in {industry}. Our platform is specifically designed to help teams like yours scale efficiently.",
            "call_to_action": "Are you open to seeing a quick demo next week?",
        }
    },
    "linkedin": {
        "intent_driven": {
            "subject": None,
            "message_body": "Hi {contact_first_name}, saw the {intent_signal_summary} at {company_name}—congrats! I'd love to connect and share how we've helped similar teams scale during this phase.",
            "call_to_action": None,
        },
        "tech_driven": {
            "subject": None,
            "message_body": "Hi {contact_first_name}, noticing {company_name} uses {technology_name}. We help teams optimize this stack. Let's connect!",
            "call_to_action": None,
        },
        "fit_driven": {
            "subject": None,
            "message_body": "Hi {contact_first_name}, I'm impressed by {company_name}'s trajectory in {industry}. I'd love to connect with you.",
            "call_to_action": None,
        }
    }
}

def get_template_for_angle(angle: str, channel: str) -> dict:
    """
    Returns the raw template strings for a given angle and channel.
    Fallback to 'fit_driven' if angle is not found.
    Fallback to 'email' if channel is not found.
    """
    channel_templates = TEMPLATES.get(channel, TEMPLATES["email"])
    return channel_templates.get(angle, channel_templates["fit_driven"])

def render_template(template_dict: dict, context: TemplateContext) -> TemplateVariant:
    """
    Renders the subject, body, and CTA using the given context.
    """
    subject = template_dict.get("subject")
    message_body = template_dict.get("message_body", "")
    cta = template_dict.get("call_to_action")

    rendered_subject = _safe_substitute(subject, context) if subject else None
    rendered_body = _safe_substitute(message_body, context)
    rendered_cta = _safe_substitute(cta, context) if cta else None

    return TemplateVariant(
        subject=rendered_subject,
        message_body=rendered_body,
        call_to_action=rendered_cta
    )
