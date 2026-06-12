from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    get_jwks,
    hash_password,
    hash_refresh_token,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify(self) -> None:
        password = "test-password-123!@#"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_wrong_password_rejected(self) -> None:
        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_different_hashes_per_call(self) -> None:
        password = "same-password"
        h1 = hash_password(password)
        h2 = hash_password(password)
        assert h1 != h2
        assert verify_password(password, h1) is True
        assert verify_password(password, h2) is True

    def test_empty_password(self) -> None:
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("x", hashed) is False


class TestJWTToken:
    def test_encode_decode_roundtrip(self) -> None:
        token = create_access_token("user-123")
        decoded = decode_access_token(token)
        assert decoded["sub"] == "user-123"
        assert decoded["type"] == "access"
        assert decoded["iss"] == "irtiqa-api"
        assert decoded["aud"] == "irtiqa-client"
        assert decoded["kid"] == "key-v1"

    def test_encode_with_org_and_role(self) -> None:
        token = create_access_token("user-456", organization_id="org-789", role="admin")
        decoded = decode_access_token(token)
        assert decoded["sub"] == "user-456"
        assert decoded["org"] == "org-789"
        assert decoded["role"] == "admin"

    def test_expired_token_rejected(self) -> None:
        token = create_access_token("user-expired", expires_in=-1)
        time.sleep(0.01)
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_tampered_token_rejected(self) -> None:
        token = create_access_token("user-tamper")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token(tampered)

    def test_missing_token_rejected(self) -> None:
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token("")

    def test_token_contains_iat_and_exp(self) -> None:
        now = datetime.now(timezone.utc)
        token = create_access_token("user-789")
        decoded = decode_access_token(token)
        assert "iat" in decoded
        assert "exp" in decoded
        assert decoded["exp"] > decoded["iat"]
        # 15 min default
        expected_exp = decoded["iat"] + 15 * 60
        assert abs(decoded["exp"] - expected_exp) <= 2


class TestRefreshToken:
    def test_generate_returns_raw_and_hash(self) -> None:
        raw, hashed = generate_refresh_token()
        assert len(raw) == 128  # 64 bytes = 128 hex chars
        assert len(hashed) == 64  # SHA-256 = 64 hex chars
        expected_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert hashed == expected_hash

    def test_hash_roundtrip(self) -> None:
        raw, hashed = generate_refresh_token()
        assert hash_refresh_token(raw) == hashed

    def test_unique_per_call(self) -> None:
        raw1, _ = generate_refresh_token()
        raw2, _ = generate_refresh_token()
        assert raw1 != raw2
        assert len(raw1) == 128
        assert len(raw2) == 128


class TestJWKS:
    def test_jwks_structure(self) -> None:
        jwks = get_jwks()
        assert "keys" in jwks
        assert len(jwks["keys"]) == 1
        key = jwks["keys"][0]
        assert key["kty"] == "RSA"
        assert key["use"] == "sig"
        assert key["kid"] == "key-v1"
        assert key["alg"] == "RS256"
        assert "n" in key
        assert "e" in key
        assert len(key["n"]) > 0
