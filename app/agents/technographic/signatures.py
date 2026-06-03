"""Signature-based technology detection registry.

This module defines the data structures and the static signature
registry used by the :class:`TechnographicAgent` to detect
technologies embedded in HTML pages.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SignaturePattern:
    """A single detection pattern within a technology signature.

    Attributes:
        source: The HTML signal source to examine.  One of
            ``script_src``, ``meta_tag``, ``html_content``,
            ``inline_script``, ``link_href``, or ``html_comment``.
        pattern: A literal substring or regex pattern to match.
        is_regex: When ``True``, *pattern* is compiled as a regex.
        weight: Contribution to the per-page confidence score
            (``0.0`` – ``1.0``).
    """

    source: str
    pattern: str
    is_regex: bool = False
    weight: float = 0.5

    def matches(self, text: str) -> bool:
        """Return ``True`` if *text* contains this pattern."""
        if self.is_regex:
            return bool(re.search(self.pattern, text, re.IGNORECASE))
        return self.pattern.lower() in text.lower()


@dataclass(frozen=True, slots=True)
class TechnologySignature:
    """Defines a technology and the patterns used to detect it.

    Attributes:
        name: Human-readable technology name (e.g. ``"Google Analytics"``).
        category: One of the supported category strings.
        vendor: Optional vendor / company name.
        patterns: Ordered list of detection patterns.
    """

    name: str
    category: str
    vendor: str | None = None
    patterns: tuple[SignaturePattern, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class PageSignals:
    """Pre-extracted signal sources from a single HTML page.

    Created once per page so that the signature matcher iterates
    the registry without re-parsing the DOM for every technology.
    """

    script_srcs: list[str] = field(default_factory=list)
    meta_tags: list[tuple[str, str]] = field(default_factory=list)
    link_hrefs: list[str] = field(default_factory=list)
    inline_scripts: str = ""
    html_comments: list[str] = field(default_factory=list)
    full_html: str = ""


# ---------------------------------------------------------------------------
# Signal source accessor helpers
# ---------------------------------------------------------------------------

_SOURCE_ACCESSORS: dict[str, str] = {
    "script_src": "script_srcs",
    "link_href": "link_hrefs",
    "html_comment": "html_comments",
}


def match_pattern(pattern: SignaturePattern, signals: PageSignals) -> bool:
    """Check whether *pattern* fires against *signals*."""
    source = pattern.source

    if source in ("script_src", "link_href"):
        items: list[str] = getattr(signals, _SOURCE_ACCESSORS[source])
        return any(pattern.matches(item) for item in items)

    if source == "meta_tag":
        for _name, content in signals.meta_tags:
            if pattern.matches(content):
                return True
        # Also check the name attribute itself
        for name, _content in signals.meta_tags:
            if pattern.matches(name):
                return True
        return False

    if source == "inline_script":
        return pattern.matches(signals.inline_scripts)

    if source == "html_comment":
        return any(pattern.matches(c) for c in signals.html_comments)

    if source == "html_content":
        return pattern.matches(signals.full_html)

    return False


def match_technology(
    signature: TechnologySignature,
    signals: PageSignals,
) -> float:
    """Return the per-page score for *signature* against *signals*.

    The score is the sum of weights of all matched patterns, capped
    at ``1.0``.  Returns ``0.0`` when no patterns match.
    """
    total = 0.0
    for pat in signature.patterns:
        if match_pattern(pat, signals):
            total += pat.weight
    return min(total, 1.0)


# ---------------------------------------------------------------------------
# Signature Registry
# ---------------------------------------------------------------------------

SIGNATURE_REGISTRY: tuple[TechnologySignature, ...] = (
    # ── CMS ────────────────────────────────────────────────────────────
    TechnologySignature(
        name="WordPress",
        category="cms",
        vendor="Automattic",
        patterns=(
            SignaturePattern(source="meta_tag", pattern="WordPress", weight=0.9),
            SignaturePattern(source="link_href", pattern="/wp-content/", weight=0.8),
            SignaturePattern(source="link_href", pattern="/wp-includes/", weight=0.7),
            SignaturePattern(source="script_src", pattern="/wp-includes/", weight=0.7),
            SignaturePattern(source="html_comment", pattern="WordPress", weight=0.4),
        ),
    ),
    TechnologySignature(
        name="Drupal",
        category="cms",
        vendor="Drupal Association",
        patterns=(
            SignaturePattern(source="meta_tag", pattern="Drupal", weight=0.9),
            SignaturePattern(source="script_src", pattern="/sites/default/files/", weight=0.6),
            SignaturePattern(source="html_content", pattern="data-drupal-", weight=0.7),
            SignaturePattern(source="html_content", pattern="Drupal.settings", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="Joomla",
        category="cms",
        vendor="Open Source Matters",
        patterns=(
            SignaturePattern(source="meta_tag", pattern="Joomla", weight=0.9),
            SignaturePattern(source="script_src", pattern="/media/jui/", weight=0.7),
            SignaturePattern(source="html_content", pattern="/administrator/", weight=0.3),
        ),
    ),
    TechnologySignature(
        name="Wix",
        category="cms",
        vendor="Wix",
        patterns=(
            SignaturePattern(source="meta_tag", pattern="Wix.com", weight=0.9),
            SignaturePattern(source="html_content", pattern="wix-custom-", weight=0.6),
            SignaturePattern(source="script_src", pattern="static.parastorage.com", weight=0.8),
            SignaturePattern(source="script_src", pattern="static.wixstatic.com", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="Squarespace",
        category="cms",
        vendor="Squarespace",
        patterns=(
            SignaturePattern(source="meta_tag", pattern="Squarespace", weight=0.9),
            SignaturePattern(source="html_content", pattern="squarespace.com", weight=0.5),
            SignaturePattern(source="script_src", pattern="static1.squarespace.com", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="Ghost",
        category="cms",
        vendor="Ghost Foundation",
        patterns=(
            SignaturePattern(source="meta_tag", pattern="Ghost", weight=0.8),
            SignaturePattern(source="link_href", pattern="/assets/built/", weight=0.5),
            SignaturePattern(source="html_content", pattern="ghost-", weight=0.4),
        ),
    ),
    # ── Analytics ──────────────────────────────────────────────────────
    TechnologySignature(
        name="Google Analytics",
        category="analytics",
        vendor="Google",
        patterns=(
            SignaturePattern(source="script_src", pattern="google-analytics.com/analytics.js", weight=0.9),
            SignaturePattern(source="script_src", pattern="googletagmanager.com/gtag/", weight=0.9),
            SignaturePattern(source="inline_script", pattern="UA-", weight=0.5),
            SignaturePattern(source="inline_script", pattern="G-", weight=0.5),
        ),
    ),
    TechnologySignature(
        name="Google Tag Manager",
        category="analytics",
        vendor="Google",
        patterns=(
            SignaturePattern(source="script_src", pattern="googletagmanager.com/gtm.js", weight=0.9),
            SignaturePattern(source="inline_script", pattern="GTM-", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="Mixpanel",
        category="analytics",
        vendor="Mixpanel",
        patterns=(
            SignaturePattern(source="script_src", pattern="cdn.mxpnl.com", weight=0.9),
            SignaturePattern(source="inline_script", pattern="mixpanel.init", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="Amplitude",
        category="analytics",
        vendor="Amplitude",
        patterns=(
            SignaturePattern(source="script_src", pattern="cdn.amplitude.com", weight=0.9),
            SignaturePattern(source="inline_script", pattern="amplitude.getInstance", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="Heap",
        category="analytics",
        vendor="Heap",
        patterns=(
            SignaturePattern(source="script_src", pattern="cdn.heapanalytics.com", weight=0.9),
            SignaturePattern(source="inline_script", pattern="heap.load", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="Plausible",
        category="analytics",
        vendor="Plausible",
        patterns=(
            SignaturePattern(source="script_src", pattern="plausible.io/js/", weight=0.9),
        ),
    ),
    TechnologySignature(
        name="Matomo",
        category="analytics",
        vendor="Matomo",
        patterns=(
            SignaturePattern(source="script_src", pattern="matomo.js", weight=0.8),
            SignaturePattern(source="inline_script", pattern="_paq.push", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="Hotjar",
        category="analytics",
        vendor="Hotjar",
        patterns=(
            SignaturePattern(source="script_src", pattern="static.hotjar.com", weight=0.9),
            SignaturePattern(source="inline_script", pattern="hotjar", weight=0.5),
        ),
    ),
    TechnologySignature(
        name="Segment",
        category="analytics",
        vendor="Twilio",
        patterns=(
            SignaturePattern(source="script_src", pattern="cdn.segment.com", weight=0.9),
            SignaturePattern(source="inline_script", pattern="analytics.load", weight=0.6),
        ),
    ),
    # ── Frontend Frameworks ───────────────────────────────────────────
    TechnologySignature(
        name="React",
        category="frontend_framework",
        vendor="Meta",
        patterns=(
            SignaturePattern(source="html_content", pattern="data-reactroot", weight=0.9),
            SignaturePattern(source="html_content", pattern="__NEXT_DATA__", weight=0.7),
            SignaturePattern(source="html_content", pattern="_reactListening", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="Next.js",
        category="frontend_framework",
        vendor="Vercel",
        patterns=(
            SignaturePattern(source="html_content", pattern="__NEXT_DATA__", weight=0.9),
            SignaturePattern(source="script_src", pattern="/_next/static/", weight=0.8),
            SignaturePattern(source="meta_tag", pattern="next-head-count", weight=0.7),
        ),
    ),
    TechnologySignature(
        name="Vue.js",
        category="frontend_framework",
        vendor="Evan You",
        patterns=(
            SignaturePattern(source="html_content", pattern="data-v-", weight=0.7),
            SignaturePattern(source="html_content", pattern="__vue__", weight=0.8),
            SignaturePattern(source="script_src", pattern="vue.js", weight=0.5),
            SignaturePattern(source="script_src", pattern="vue.min.js", weight=0.6),
        ),
    ),
    TechnologySignature(
        name="Nuxt",
        category="frontend_framework",
        vendor="NuxtLabs",
        patterns=(
            SignaturePattern(source="html_content", pattern="__NUXT__", weight=0.9),
            SignaturePattern(source="script_src", pattern="/_nuxt/", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="Angular",
        category="frontend_framework",
        vendor="Google",
        patterns=(
            SignaturePattern(source="html_content", pattern="ng-version", weight=0.9),
            SignaturePattern(source="html_content", pattern="ng-app", weight=0.7),
            SignaturePattern(source="script_src", pattern="angular", weight=0.5),
        ),
    ),
    TechnologySignature(
        name="Svelte",
        category="frontend_framework",
        vendor="Svelte",
        patterns=(
            SignaturePattern(source="html_content", pattern="svelte-", weight=0.7),
            SignaturePattern(source="html_content", pattern="__svelte", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="Bootstrap",
        category="frontend_framework",
        vendor="Bootstrap",
        patterns=(
            SignaturePattern(source="link_href", pattern="bootstrap", weight=0.6),
            SignaturePattern(source="script_src", pattern="bootstrap", weight=0.6),
        ),
    ),
    TechnologySignature(
        name="Tailwind CSS",
        category="frontend_framework",
        vendor="Tailwind Labs",
        patterns=(
            SignaturePattern(source="link_href", pattern="tailwindcss", weight=0.7),
            SignaturePattern(source="script_src", pattern="tailwindcss", weight=0.7),
            SignaturePattern(source="html_content", pattern="tailwind", weight=0.3),
        ),
    ),
    TechnologySignature(
        name="jQuery",
        category="frontend_framework",
        vendor="OpenJS Foundation",
        patterns=(
            SignaturePattern(source="script_src", pattern="jquery", weight=0.7),
            SignaturePattern(source="inline_script", pattern="jQuery(", weight=0.6),
            SignaturePattern(source="inline_script", pattern="$(document).ready", weight=0.5),
        ),
    ),
    # ── Marketing Pixels ──────────────────────────────────────────────
    TechnologySignature(
        name="Facebook Pixel",
        category="marketing_pixel",
        vendor="Meta",
        patterns=(
            SignaturePattern(source="script_src", pattern="connect.facebook.net", weight=0.8),
            SignaturePattern(source="inline_script", pattern="fbq(", weight=0.9),
        ),
    ),
    TechnologySignature(
        name="Google Ads",
        category="marketing_pixel",
        vendor="Google",
        patterns=(
            SignaturePattern(source="script_src", pattern="googleadservices.com", weight=0.9),
            SignaturePattern(source="script_src", pattern="googlesyndication.com", weight=0.7),
            SignaturePattern(source="inline_script", pattern="gtag('config', 'AW-", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="LinkedIn Insight",
        category="marketing_pixel",
        vendor="Microsoft",
        patterns=(
            SignaturePattern(source="script_src", pattern="snap.licdn.com", weight=0.9),
            SignaturePattern(source="inline_script", pattern="_linkedin_partner_id", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="Twitter Pixel",
        category="marketing_pixel",
        vendor="X Corp",
        patterns=(
            SignaturePattern(source="script_src", pattern="static.ads-twitter.com", weight=0.9),
            SignaturePattern(source="inline_script", pattern="twq(", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="HubSpot Tracking",
        category="marketing_pixel",
        vendor="HubSpot",
        patterns=(
            SignaturePattern(source="script_src", pattern="js.hs-scripts.com", weight=0.9),
            SignaturePattern(source="script_src", pattern="js.hs-analytics.net", weight=0.8),
            SignaturePattern(source="inline_script", pattern="hs-script-loader", weight=0.6),
        ),
    ),
    # ── Hosting ────────────────────────────────────────────────────────
    TechnologySignature(
        name="Netlify",
        category="hosting",
        vendor="Netlify",
        patterns=(
            SignaturePattern(source="html_content", pattern="netlify", weight=0.4),
            SignaturePattern(source="link_href", pattern="netlify", weight=0.5),
            SignaturePattern(source="html_comment", pattern="netlify", weight=0.6),
        ),
    ),
    TechnologySignature(
        name="Vercel",
        category="hosting",
        vendor="Vercel",
        patterns=(
            SignaturePattern(source="html_content", pattern="vercel", weight=0.4),
            SignaturePattern(source="script_src", pattern="vercel", weight=0.5),
            SignaturePattern(source="html_content", pattern="__NEXT_DATA__", weight=0.3),
        ),
    ),
    TechnologySignature(
        name="Heroku",
        category="hosting",
        vendor="Salesforce",
        patterns=(
            SignaturePattern(source="html_content", pattern="herokuapp.com", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="GitHub Pages",
        category="hosting",
        vendor="Microsoft",
        patterns=(
            SignaturePattern(source="html_content", pattern="github.io", weight=0.7),
            SignaturePattern(source="link_href", pattern="github.io", weight=0.6),
        ),
    ),
    # ── CDN ────────────────────────────────────────────────────────────
    TechnologySignature(
        name="Cloudflare",
        category="cdn",
        vendor="Cloudflare",
        patterns=(
            SignaturePattern(source="script_src", pattern="cdnjs.cloudflare.com", weight=0.7),
            SignaturePattern(source="link_href", pattern="cdnjs.cloudflare.com", weight=0.7),
            SignaturePattern(source="html_content", pattern="cf-ray", weight=0.5),
        ),
    ),
    TechnologySignature(
        name="CloudFront",
        category="cdn",
        vendor="Amazon",
        patterns=(
            SignaturePattern(source="script_src", pattern="cloudfront.net", weight=0.7),
            SignaturePattern(source="link_href", pattern="cloudfront.net", weight=0.7),
        ),
    ),
    TechnologySignature(
        name="Cloudinary",
        category="cdn",
        vendor="Cloudinary",
        patterns=(
            SignaturePattern(source="html_content", pattern="res.cloudinary.com", weight=0.8),
            SignaturePattern(source="script_src", pattern="cloudinary", weight=0.6),
        ),
    ),
    TechnologySignature(
        name="jsDelivr",
        category="cdn",
        vendor="jsDelivr",
        patterns=(
            SignaturePattern(source="script_src", pattern="cdn.jsdelivr.net", weight=0.8),
            SignaturePattern(source="link_href", pattern="cdn.jsdelivr.net", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="unpkg",
        category="cdn",
        vendor="unpkg",
        patterns=(
            SignaturePattern(source="script_src", pattern="unpkg.com", weight=0.8),
            SignaturePattern(source="link_href", pattern="unpkg.com", weight=0.8),
        ),
    ),
    # ── Chat Widgets ──────────────────────────────────────────────────
    TechnologySignature(
        name="Intercom",
        category="chat_widget",
        vendor="Intercom",
        patterns=(
            SignaturePattern(source="script_src", pattern="widget.intercom.io", weight=0.9),
            SignaturePattern(source="inline_script", pattern="Intercom(", weight=0.8),
            SignaturePattern(source="html_content", pattern="intercom-frame", weight=0.7),
        ),
    ),
    TechnologySignature(
        name="Drift",
        category="chat_widget",
        vendor="Salesloft",
        patterns=(
            SignaturePattern(source="script_src", pattern="js.driftt.com", weight=0.9),
            SignaturePattern(source="inline_script", pattern="drift.load", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="Zendesk",
        category="chat_widget",
        vendor="Zendesk",
        patterns=(
            SignaturePattern(source="script_src", pattern="static.zdassets.com", weight=0.9),
            SignaturePattern(source="html_content", pattern="zE(", weight=0.5),
        ),
    ),
    TechnologySignature(
        name="Crisp",
        category="chat_widget",
        vendor="Crisp",
        patterns=(
            SignaturePattern(source="script_src", pattern="client.crisp.chat", weight=0.9),
            SignaturePattern(source="inline_script", pattern="$crisp", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="LiveChat",
        category="chat_widget",
        vendor="LiveChat",
        patterns=(
            SignaturePattern(source="script_src", pattern="cdn.livechatinc.com", weight=0.9),
            SignaturePattern(source="inline_script", pattern="LiveChatWidget", weight=0.7),
        ),
    ),
    TechnologySignature(
        name="Tawk.to",
        category="chat_widget",
        vendor="Tawk.to",
        patterns=(
            SignaturePattern(source="script_src", pattern="embed.tawk.to", weight=0.9),
            SignaturePattern(source="inline_script", pattern="Tawk_API", weight=0.8),
        ),
    ),
    # ── E-commerce ────────────────────────────────────────────────────
    TechnologySignature(
        name="Shopify",
        category="ecommerce",
        vendor="Shopify",
        patterns=(
            SignaturePattern(source="meta_tag", pattern="Shopify", weight=0.9),
            SignaturePattern(source="script_src", pattern="cdn.shopify.com", weight=0.9),
            SignaturePattern(source="link_href", pattern="cdn.shopify.com", weight=0.8),
            SignaturePattern(source="html_content", pattern="shopify-section", weight=0.7),
        ),
    ),
    TechnologySignature(
        name="WooCommerce",
        category="ecommerce",
        vendor="Automattic",
        patterns=(
            SignaturePattern(source="html_content", pattern="woocommerce", weight=0.7),
            SignaturePattern(source="script_src", pattern="woocommerce", weight=0.8),
            SignaturePattern(source="html_content", pattern="wc-block", weight=0.6),
        ),
    ),
    TechnologySignature(
        name="Magento",
        category="ecommerce",
        vendor="Adobe",
        patterns=(
            SignaturePattern(source="html_content", pattern="Magento", weight=0.5),
            SignaturePattern(source="script_src", pattern="mage/", weight=0.7),
            SignaturePattern(source="html_content", pattern="checkout/cart", weight=0.3),
        ),
    ),
    TechnologySignature(
        name="BigCommerce",
        category="ecommerce",
        vendor="BigCommerce",
        patterns=(
            SignaturePattern(source="html_content", pattern="bigcommerce.com", weight=0.7),
            SignaturePattern(source="script_src", pattern="bigcommerce.com", weight=0.8),
        ),
    ),
    TechnologySignature(
        name="Stripe",
        category="ecommerce",
        vendor="Stripe",
        patterns=(
            SignaturePattern(source="script_src", pattern="js.stripe.com", weight=0.9),
            SignaturePattern(source="inline_script", pattern="Stripe(", weight=0.7),
        ),
    ),
)
