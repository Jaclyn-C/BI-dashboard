"""用户管理入出参（REQ-20261020-01 §1.6/DESIGN §2.2）。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.auth import UserPublic


class UserRoleUpdateRequest(BaseModel):
    """PATCH /users/{id}/role 入参。super_admin 不是合法值（仅启动机制可产生）。"""

    role: Literal["admin", "customer", "pending"]


class UserListItem(UserPublic):
    """列表行：在 UserPublic 基础上补最近登录。"""

    last_login_at: datetime | None


class UsersListResponse(BaseModel):
    """GET /users 响应（created_at 倒序，全量不分页）。"""

    users: list[UserListItem]
