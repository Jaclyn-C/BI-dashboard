"""请求级依赖：数据库会话、邮件发送器、当前用户（DESIGN §2.1/§3.3(6)）。"""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.db import get_db
from app.models import User
from app.services import token_service
from app.services.email_sender import EmailSender
from app.services.token_service import TokenError

__all__ = ["get_current_user", "get_db", "get_email_sender", "require_role"]

_bearer = HTTPBearer(auto_error=False, description="登录接口返回的 access token（Bearer）")


def get_email_sender(request: Request) -> EmailSender:
    """从应用状态取邮件发送器（main.py lifespan 装配，测试经 dependency_overrides 覆写）。"""
    return request.app.state.email_sender


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """受保护接口的鉴权样板：解码 → 查用户 → 比对 credential_version。

    旧 token 因 ``pwd_ver`` 与 ``users.credential_version`` 不符即 401
    （重置密码全端失效，DESIGN D2/Q7）。
    """
    if credentials is None:
        raise ApiError(401, "UNAUTHORIZED", "missing or invalid bearer token")
    try:
        payload = token_service.decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise ApiError(401, "UNAUTHORIZED", "missing or invalid bearer token") from exc

    user = db.get(User, payload.user_id)
    if user is None or user.credential_version != payload.credential_version:
        raise ApiError(401, "UNAUTHORIZED", "missing or invalid bearer token")
    return user


def require_role(*allowed: str):
    """角色门禁（REQ-20261020-01 §1.5）：先过 get_current_user，再校验角色。

    用法：端点 dependencies=[Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN))]。
    pending 用户任何数据接口即 403；401 语义（未登录）不变。
    """

    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise ApiError(403, "FORBIDDEN", "insufficient role")
        return user

    return _checker
