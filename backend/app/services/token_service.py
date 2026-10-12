"""JWT 签发与解码（DESIGN D2/§6.8）。

HS256 + SECRET_KEY，claim 最小化 ``{sub, iat, exp, pwd_ver}``；
``pwd_ver`` 与 ``users.credential_version`` 比对，重置密码即全端失效（Q7）。
有效期 8 小时（ACCESS_TOKEN_TTL_MINUTES），无 refresh token。
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings

_ALGORITHM = "HS256"


class TokenError(Exception):
    """token 无效/过期（路由层翻译为 401 UNAUTHORIZED）。"""


class TokenExpiredError(TokenError):
    """token 已过期。"""


class TokenInvalidError(TokenError):
    """签名不符 / 载荷缺失 / 篡改。"""


@dataclass(frozen=True)
class TokenPayload:
    user_id: int
    credential_version: int
    issued_at: int
    expires_at: int


def create_access_token(user_id: int, credential_version: int) -> tuple[str, int]:
    """签发 access token；返回 (token, expires_in 秒)。"""
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_ttl_minutes)
    claims = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "pwd_ver": credential_version,
    }
    token = jwt.encode(claims, settings.secret_key, algorithm=_ALGORITHM)
    return token, settings.access_token_ttl_minutes * 60


def decode_access_token(token: str) -> TokenPayload:
    """解码并校验 token；失败抛 TokenExpiredError / TokenInvalidError。"""
    settings = get_settings()
    try:
        raw = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[_ALGORITHM],
            options={"require": ["exp", "iat", "sub", "pwd_ver"]},
        )
        return TokenPayload(
            user_id=int(raw["sub"]),
            credential_version=int(raw["pwd_ver"]),
            issued_at=int(raw["iat"]),
            expires_at=int(raw["exp"]),
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("token expired") from exc
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise TokenInvalidError("token invalid") from exc
