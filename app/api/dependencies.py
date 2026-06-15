from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.core.tenant import TenantContext
from app.database.session import SessionLocal
from app.services import (
    AgentRunService,
    AuthService,
    CompanyService,
    ContactService,
    EvidenceService,
    IntelligenceScoreService,
    IntentSignalService,
    JobService,
    MembershipService,
    OrganizationService,
    OutreachMessageService,
    TechnologyService,
    WebsiteService,
)


def get_app_settings() -> Settings:
    return get_settings()


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_company_service() -> CompanyService:
    return CompanyService()


def get_contact_service() -> ContactService:
    return ContactService()


def get_website_service() -> WebsiteService:
    return WebsiteService()


def get_technology_service() -> TechnologyService:
    return TechnologyService()


def get_intent_signal_service() -> IntentSignalService:
    return IntentSignalService()


def get_intelligence_score_service() -> IntelligenceScoreService:
    return IntelligenceScoreService()


def get_outreach_message_service() -> OutreachMessageService:
    return OutreachMessageService()


def get_agent_run_service() -> AgentRunService:
    return AgentRunService()


def get_job_service() -> JobService:
    return JobService()


def get_evidence_service() -> EvidenceService:
    return EvidenceService()


def get_organization_service() -> OrganizationService:
    return OrganizationService()


def get_membership_service() -> MembershipService:
    return MembershipService()


def get_auth_service() -> AuthService:
    return AuthService()


# Reusable bearer security scheme for OpenAPI / Swagger UI.
# HTTPBearer automatically extracts the token from the
# ``Authorization: Bearer <token>`` header and integrates with the
# "Authorize" button in Swagger UI so that generated requests include
# the header.
bearer_scheme = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    try:
        user = auth_service.authenticate_with_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }


def get_current_organization(
    authorization: str | None = Header(default=None),
    auth_service: AuthService = Depends(get_auth_service),
    membership_service: MembershipService = Depends(get_membership_service),
) -> TenantContext:
    """Authenticate the user and verify membership in the org specified
    in the JWT claims.

    Performs a membership database lookup on every request.
    This is the F-1 fix: never trust the JWT claim alone.
    """
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ")

    # Decode JWT — reuses existing auth logic
    user = auth_service.authenticate_with_token(token)
    user_id = user["id"] if isinstance(user, dict) else user.id

    # Decode JWT a second time to extract org/role claims
    # (Two decodes per request. This avoids refactoring get_current_user()
    # which would affect 30+ callers. Cost: ~1ms.)
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    org_id = payload.get("org")
    jwt_role = payload.get("role")

    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No organization context. Please authenticate with an organization.",
        )

    # Verify membership (F-1 fix: never trust JWT alone)
    membership = membership_service.get_membership(user_id, org_id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization.",
        )

    return TenantContext(
        organization_id=org_id,
        user_id=user_id,
        role=membership.role,
        is_api_key=False,
    )
