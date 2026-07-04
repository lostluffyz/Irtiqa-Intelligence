from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.dependencies import get_auth_service, get_current_user
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import get_jwks
from app.schemas.auth import (
    JWKSResponse,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RegisterRequest,
    RegisterResponse,
    UpdateProfileRequest,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.auth_service import AuthService


router = APIRouter(tags=["auth"])

logger = get_logger("endpoints.auth")


@router.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> RegisterResponse:
    user = auth_service.register(
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
    )
    token = auth_service.get_verification_token(user)
    settings = get_settings()
    if settings.auth.dev_mode:
        logger.info("Dev mode — email verification token: %s", token)
        message = f"Account created. Verify your email. Token: {token}"
    else:
        message = "Account created. Verify your email to activate."
    org_data = getattr(user, "_organization_summary", None)
    return RegisterResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        message=message,
        organization=org_data,
    )


@router.post("/auth/verify-email", status_code=status.HTTP_200_OK)
def verify_email(
    payload: VerifyEmailRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    user = auth_service.verify_email(payload.token)
    return {"message": "Email verified successfully.", "email": user.email}


@router.post("/auth/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    ip_address = request.client.host if request.client else "unknown"
    user, access_token, refresh_token, org_summary = auth_service.login(
        email=payload.email,
        password=payload.password,
        ip_address=ip_address,
    )
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
        organization=org_summary,
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: dict = Depends(get_current_user),
) -> Response:
    auth_service.logout(payload.refresh_token, current_user["id"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auth/refresh", response_model=RefreshTokenResponse)
def refresh(
    payload: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> RefreshTokenResponse:
    access_token, new_refresh_token = auth_service.refresh(payload.refresh_token)
    return RefreshTokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.get("/auth/me", response_model=UserResponse)
def get_me(
    current_user: dict = Depends(get_current_user),
) -> UserResponse:
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        display_name=current_user["display_name"],
        is_active=current_user["is_active"],
        created_at=current_user["created_at"],
    )


@router.patch("/auth/me", response_model=UserResponse)
def update_me(
    payload: UpdateProfileRequest,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: dict = Depends(get_current_user),
) -> UserResponse:
    values = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not values:
        from app.core.errors import ValidationError
        raise ValidationError(
            "At least one field must be provided for update.",
            details={"field": "body"},
        )
    user = auth_service.update_profile(current_user["id"], **values)
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.delete("/auth/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    auth_service: AuthService = Depends(get_auth_service),
    current_user: dict = Depends(get_current_user),
) -> Response:
    auth_service.delete_account(current_user["id"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/.well-known/jwks.json", response_model=JWKSResponse)
def jwks_endpoint() -> JWKSResponse:
    return JWKSResponse(keys=get_jwks()["keys"])
