from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.base import IrtiqaSchema


class UserResponse(IrtiqaSchema):
    id: str
    email: str
    display_name: str
    is_active: bool
    created_at: datetime


class RegisterRequest(IrtiqaSchema):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=200)


class RegisterResponse(IrtiqaSchema):
    id: str
    email: str
    display_name: str
    message: str = "Account created. Verify your email to activate."


class VerifyEmailRequest(IrtiqaSchema):
    token: str = Field(min_length=1)


class LoginRequest(IrtiqaSchema):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=1)


class LoginResponse(IrtiqaSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshTokenRequest(IrtiqaSchema):
    refresh_token: str = Field(min_length=1)


class RefreshTokenResponse(IrtiqaSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UpdateProfileRequest(IrtiqaSchema):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)


class SwitchOrganizationRequest(IrtiqaSchema):
    organization_id: str = Field(min_length=36, max_length=36)


class JWKSResponse(IrtiqaSchema):
    keys: list[dict]
