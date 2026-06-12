from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select, func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    EntityConflictError,
    EntityNotFoundError,
    ServiceError,
    ValidationError,
)
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.email_verification_token import EmailVerificationToken
from app.models.failed_login_attempt import FailedLoginAttempt
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.base import BaseService
from app.core.logging import get_logger


logger = get_logger("services.auth")


class AuthService(BaseService[User, UserRepository]):
    model = User
    repository = UserRepository

    # ── Registration ──────────────────────────────────────────────────────

    def register(
        self,
        email: str,
        password: str,
        display_name: str,
    ) -> User:
        normalized_email = email.strip().lower()

        # Check for existing user
        existing = self.get_by_email(normalized_email)
        if existing is not None:
            # Don't reveal whether the account exists
            raise EntityConflictError(
                "A user with this email already exists.",
                details={"field": "email"},
            )

        hashed = hash_password(password)
        now = datetime.now(timezone.utc)

        def operation(session: Session) -> User:
            repo = self._repository(session)
            user = User(
                email=normalized_email,
                password_hash=hashed,
                display_name=display_name,
                is_active=False,
                created_at=now,
                updated_at=now,
            )
            repo.add(user)
            session.flush()

            # Create email verification token
            raw_token = secrets.token_hex(32)
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            session.add(
                EmailVerificationToken(
                    user_id=user.id,
                    token_hash=token_hash,
                    expires_at=now + timedelta(minutes=15),
                    created_at=now,
                )
            )
            session.flush()

            # Store raw token on the user object for the response
            user._verification_token_raw = raw_token  # type: ignore[attr-defined]
            return user

        return self._run_in_transaction("register", operation)

    def get_verification_token(self, user: User) -> str:
        return getattr(user, "_verification_token_raw", "")

    # ── Email verification ────────────────────────────────────────────────

    def verify_email(self, token: str) -> User:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc)

        def operation(session: Session) -> User:
            stmt = select(EmailVerificationToken).where(
                EmailVerificationToken.token_hash == token_hash,
                EmailVerificationToken.used_at.is_(None),
                EmailVerificationToken.expires_at > now,
            )
            ver_token = session.scalar(stmt)
            if ver_token is None:
                raise ValidationError(
                    "Invalid or expired verification token.",
                    details={"field": "token"},
                )

            ver_token.used_at = now
            user = session.get(User, ver_token.user_id)
            if user is None:
                raise EntityNotFoundError(
                    "User not found.",
                    details={"entity_id": ver_token.user_id},
                )
            user.is_active = True
            user.email_verified_at = now
            return user

        return self._run_in_transaction("verify_email", operation)

    # ── Login ─────────────────────────────────────────────────────────────

    def login(self, email: str, password: str, ip_address: str) -> tuple[User, str, str]:
        normalized_email = email.strip().lower()
        settings = get_settings()

        # Rate limit check
        self._check_rate_limit(normalized_email)

        user = self.get_by_email(normalized_email)
        if user is None or user.deleted_at is not None:
            self._record_failed_attempt(normalized_email, ip_address)
            raise ValidationError(
                "Invalid email or password.",
                details={"field": "credentials"},
            )

        if not user.is_active:
            raise ValidationError(
                "Account is not activated. Please verify your email.",
                details={"field": "account"},
            )

        if not verify_password(password, user.password_hash):
            self._record_failed_attempt(normalized_email, ip_address)
            raise ValidationError(
                "Invalid email or password.",
                details={"field": "credentials"},
            )

        # Clear failed attempts on successful login
        self._clear_failed_attempts(normalized_email)

        # Generate tokens
        access_token = create_access_token(
            user_id=user.id,
        )
        raw_refresh, hashed_refresh = generate_refresh_token()
        self._store_refresh_token(user.id, hashed_refresh)

        return user, access_token, raw_refresh

    # ── Logout ────────────────────────────────────────────────────────────

    def logout(self, refresh_token: str, user_id: str) -> None:
        token_hash = hash_refresh_token(refresh_token)

        def operation(session: Session) -> None:
            stmt = select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            token = session.scalar(stmt)
            if token is not None:
                token.revoked_at = datetime.now(timezone.utc)

        self._run_in_transaction("logout", operation)

    # ── Token refresh ─────────────────────────────────────────────────────

    def refresh(self, refresh_token: str) -> tuple[str, str]:
        token_hash = hash_refresh_token(refresh_token)

        def operation(session: Session) -> tuple[str, str]:
            stmt = select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
            )
            token = session.scalar(stmt)
            if token is None:
                raise ValidationError(
                    "Invalid or revoked refresh token.",
                    details={"field": "refresh_token"},
                )

            expires = token.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires < datetime.now(timezone.utc):
                raise ValidationError(
                    "Refresh token has expired.",
                    details={"field": "refresh_token"},
                )

            # Revoke old token
            token.revoked_at = datetime.now(timezone.utc)

            # Issue new tokens
            new_access = create_access_token(user_id=token.user_id)
            new_raw, new_hashed = generate_refresh_token()

            session.add(
                RefreshToken(
                    user_id=token.user_id,
                    token_hash=new_hashed,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=7),
                    created_at=datetime.now(timezone.utc),
                )
            )
            return new_access, new_raw

        return self._run_in_transaction("refresh", operation)

    # ── User queries ──────────────────────────────────────────────────────

    def get_by_email(self, email: str) -> User | None:
        def operation(session: Session) -> User | None:
            return self._repository(session).get_by_email(email)

        return self._run_in_transaction("get_by_email", operation)

    def get_by_id(self, user_id: str) -> User | None:
        return self.get(user_id)

    def update_profile(self, user_id: str, **values: Any) -> User:
        return self.update(user_id, **values)

    def delete_account(self, user_id: str) -> None:
        now = datetime.now(timezone.utc)

        def operation(session: Session) -> None:
            user = session.get(User, user_id)
            if user is None:
                raise EntityNotFoundError(
                    "User not found.",
                    details={"entity_id": user_id},
                )
            user.deleted_at = now

            # Revoke all refresh tokens
            stmt = select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            for token in session.scalars(stmt):
                token.revoked_at = now

        self._run_in_transaction("delete_account", operation)

    # ── Authenticate with token ──────────────────────────────────────────

    def authenticate_with_token(self, token: str) -> User:
        """Decode JWT access token and return the user.

        The org claim is NOT verified here — calling code must verify
        membership separately.
        """
        try:
            payload = decode_access_token(token)
        except Exception as exc:
            raise ValidationError(
                "Invalid or expired access token.",
                details={"field": "token"},
                cause=exc,
            )

        user_id = payload.get("sub")
        if not user_id:
            raise ValidationError(
                "Invalid token payload.",
                details={"field": "token"},
            )

        user = self.get_by_id(user_id)
        if user is None:
            raise EntityNotFoundError(
                "User not found.",
                details={"entity_id": user_id},
            )

        if user.deleted_at is not None:
            raise ValidationError(
                "Account has been deleted.",
                details={"field": "account"},
            )

        return user

    # ── Rate limiting ────────────────────────────────────────────────────

    def _check_rate_limit(self, email: str) -> None:
        settings = get_settings()
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=settings.auth.login_lockout_minutes)

        def operation(session: Session) -> None:
            stmt = select(func.count()).select_from(FailedLoginAttempt).where(
                FailedLoginAttempt.email == email,
                FailedLoginAttempt.attempted_at >= window_start,
            )
            count = session.scalar(stmt) or 0
            if count >= settings.auth.max_login_attempts:
                raise ValidationError(
                    "Too many login attempts. Please try again later.",
                    details={"field": "credentials", "retry_after_minutes": settings.auth.login_lockout_minutes},
                )

        self._run_in_transaction("check_rate_limit", operation)

    def _record_failed_attempt(self, email: str, ip_address: str) -> None:
        now = datetime.now(timezone.utc)

        def operation(session: Session) -> None:
            session.add(
                FailedLoginAttempt(
                    email=email,
                    ip_address=ip_address,
                    attempted_at=now,
                )
            )

        self._run_in_transaction("record_failed_attempt", operation)

    def _clear_failed_attempts(self, email: str) -> None:
        def operation(session: Session) -> None:
            stmt = delete(FailedLoginAttempt).where(
                FailedLoginAttempt.email == email,
            )
            session.execute(stmt)

        self._run_in_transaction("clear_failed_attempts", operation)

    # ── Refresh token storage ────────────────────────────────────────────

    def _store_refresh_token(self, user_id: str, token_hash: str) -> None:
        now = datetime.now(timezone.utc)

        def operation(session: Session) -> None:
            session.add(
                RefreshToken(
                    user_id=user_id,
                    token_hash=token_hash,
                    expires_at=now + timedelta(days=7),
                    created_at=now,
                )
            )

        self._run_in_transaction("store_refresh_token", operation)
