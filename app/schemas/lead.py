from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import IrtiqaSchema, ListSchema


class LeadTechnologyResponse(IrtiqaSchema):
    """Technology summary embedded in a lead response."""

    name: str
    category: str


class LeadIntentSignalResponse(IrtiqaSchema):
    """Intent signal summary embedded in a lead response."""

    signal_type: str
    confidence: float = Field(ge=0.0, le=1.0)


class LeadIntelligenceScoreResponse(IrtiqaSchema):
    """Latest intelligence score summary embedded in a lead response.

    Maps from the persisted ``IntelligenceScore`` fields:
    - ``total_score`` → ``total_score``
    - ``opportunity_score`` → ``fit_score`` (how well the company fits the ICP)
    - ``urgency_score`` → ``intent_score`` (how recent and strong the buying signals are)
    """

    total_score: float = Field(ge=0.0, le=100.0)
    opportunity_score: float = Field(ge=0.0, le=100.0)
    urgency_score: float = Field(ge=0.0, le=100.0)


class LeadOutreachMessageResponse(IrtiqaSchema):
    """Outreach message summary embedded in a lead response."""

    channel: str
    subject: str | None
    message_body: str


CompanyStatus = Literal["active", "needs_review", "archived"]


class LeadResponse(IrtiqaSchema):
    """Aggregated lead intelligence for a single company."""

    company_id: str
    company_name: str
    domain: str
    industry: str | None
    status: CompanyStatus
    technologies: list[LeadTechnologyResponse]
    intent_signals: list[LeadIntentSignalResponse]
    latest_intelligence_score: LeadIntelligenceScoreResponse | None
    outreach_messages: list[LeadOutreachMessageResponse]
    updated_at: datetime


class LeadListResponse(ListSchema):
    """Paginated list of aggregated lead intelligence."""

    items: list[LeadResponse]
