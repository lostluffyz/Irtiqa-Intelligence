from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt as pyjwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from passlib.context import CryptContext

from app.core.config import get_settings


# ── Password hashing ─────────────────────────────────────────────────────────

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


# ── Key management ───────────────────────────────────────────────────────────

_KEY_PAIR: tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey] | None = None


def _get_key_pair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    global _KEY_PAIR
    if _KEY_PAIR is None:
        settings = get_settings()
        if settings.auth.jwt_private_key:
            private_key = serialization.load_pem_private_key(
                settings.jwt_private_key.encode("utf-8"),
                password=None,
                backend=default_backend(),
            )
            if not isinstance(private_key, rsa.RSAPrivateKey):
                raise TypeError("JWT_PRIVATE_KEY must be an RSA private key")
            public_key = private_key.public_key()
        else:
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend(),
            )
            public_key = private_key.public_key()
        _KEY_PAIR = (private_key, public_key)
    return _KEY_PAIR


def _get_private_key() -> rsa.RSAPrivateKey:
    return _get_key_pair()[0]


def get_public_key_pem() -> str:
    public_key = _get_key_pair()[1]
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def get_jwks() -> dict[str, Any]:
    """Return a JWKS dictionary for the current public key."""
    public_key = _get_key_pair()[1]
    public_numbers = public_key.public_numbers()

    # Encode modulus (n) and exponent (e) as base64url
    import base64

    def _to_base64url(num: int) -> str:
        byte_length = (num.bit_length() + 7) // 8
        return base64.urlsafe_b64encode(
            num.to_bytes(byte_length, byteorder="big")
        ).rstrip(b"=").decode("ascii")

    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "kid": "key-v1",
                "alg": "RS256",
                "n": _to_base64url(public_numbers.n),
                "e": _to_base64url(public_numbers.e),
            }
        ]
    }


# ── JWT token management ────────────────────────────────────────────────────

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
JWT_ISSUER = "irtiqa-api"
JWT_AUDIENCE = "irtiqa-client"


def create_access_token(
    user_id: str,
    organization_id: str | None = None,
    role: str | None = None,
    *,
    expires_in: int | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=expires_in or ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "kid": "key-v1",
    }
    if organization_id is not None:
        payload["org"] = organization_id
    if role is not None:
        payload["role"] = role
    return pyjwt.encode(payload, _get_private_key(), algorithm="RS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify an RS256 JWT access token.

    Raises ``jwt.PyJWTError`` on any validation failure.
    """
    public_key = _get_key_pair()[1]
    return pyjwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
    )


# ── Refresh token generation ─────────────────────────────────────────────────

def generate_refresh_token() -> tuple[str, str]:
    """Return ``(raw_token, sha256_hash)``.

    The raw token is returned to the client exactly once.
    The hash is stored in the database.
    """
    import hashlib

    raw = secrets.token_hex(64)
    hashed = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, hashed


def hash_refresh_token(raw_token: str) -> str:
    import hashlib

    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


# ── API key generation ──────────────────────────────────────────────────────

def generate_api_key() -> tuple[str, str]:
    """Return ``(full_key, sha256_hash)``.

    Full key format: ``irt_sk_<64-char-hex>``.
    """
    import hashlib

    entropy = secrets.token_hex(64)
    full_key = f"irt_sk_{entropy}"
    hashed = hashlib.sha256(full_key.encode("utf-8")).hexdigest()
    return full_key, hashed
