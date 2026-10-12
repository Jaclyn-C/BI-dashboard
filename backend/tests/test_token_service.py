"""token_service 单测（纯逻辑，无 DB）。"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import get_settings
from app.services.token_service import (
    TokenExpiredError,
    TokenInvalidError,
    create_access_token,
    decode_access_token,
)


def test_roundtrip_claims() -> None:
    token, expires_in = create_access_token(user_id=7, credential_version=3)
    assert expires_in == get_settings().access_token_ttl_minutes * 60

    payload = decode_access_token(token)
    assert payload.user_id == 7
    assert payload.credential_version == 3
    assert payload.expires_at > payload.issued_at


def test_expired_token_raises() -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    expired = jwt.encode(
        {"sub": "1", "iat": int((now - timedelta(hours=9)).timestamp()),
         "exp": int((now - timedelta(hours=1)).timestamp()), "pwd_ver": 1},
        settings.secret_key,
        algorithm="HS256",
    )
    with pytest.raises(TokenExpiredError):
        decode_access_token(expired)


def test_tampered_token_raises() -> None:
    token, _ = create_access_token(user_id=1, credential_version=1)
    with pytest.raises(TokenInvalidError):
        decode_access_token(token + "tampered")


def test_wrong_signing_key_raises() -> None:
    now = datetime.now(UTC)
    forged = jwt.encode(
        {"sub": "1", "iat": int(now.timestamp()),
         "exp": int((now + timedelta(hours=1)).timestamp()), "pwd_ver": 1},
        "attacker-key-not-the-real-one-0123456789",
        algorithm="HS256",
    )
    with pytest.raises(TokenInvalidError):
        decode_access_token(forged)


def test_missing_pwd_ver_claim_raises() -> None:
    # require 列表强制 pwd_ver 存在：老形状 token 不能当有效会话用
    settings = get_settings()
    now = datetime.now(UTC)
    no_pwd_ver = jwt.encode(
        {"sub": "1", "iat": int(now.timestamp()),
         "exp": int((now + timedelta(hours=1)).timestamp())},
        settings.secret_key,
        algorithm="HS256",
    )
    with pytest.raises(TokenInvalidError):
        decode_access_token(no_pwd_ver)
