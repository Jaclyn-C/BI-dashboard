"""用户管理路由（REQ-20261020-01 §1.3/§1.6，DESIGN §2.2）。

- GET   /users               列表（admin+）
- PATCH /users/{id}/role     角色调整（等级规则在 role_service.can_assign_role）
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.api.errors import ApiError
from app.models.user import ROLE_ADMIN, ROLE_SUPER_ADMIN, User
from app.schemas.auth import UserPublic
from app.schemas.users import UserListItem, UserRoleUpdateRequest, UsersListResponse
from app.services import role_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    response_model=UsersListResponse,
    summary="用户列表（管理员）",
    description="全部账号按注册时间倒序：邮箱/昵称/角色/注册时间/最近登录。"
    "仅 admin 与 super_admin 可访问（REQ-20261020-01）。",
)
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN)),
) -> UsersListResponse:
    """GET /users。"""
    users = db.scalars(select(User).order_by(User.created_at.desc(), User.id.desc())).all()
    return UsersListResponse(users=[UserListItem.model_validate(u) for u in users])


@router.patch(
    "/{user_id}/role",
    response_model=UserPublic,
    summary="调整用户角色（等级制）",
    description="可赋 admin/customer/pending。规则：只能操作等级严格低于自己的用户，"
    "新角色不得超过自己等级，不能操作自己（REQ-20261020-01 §1.3）。"
    "super_admin 角色不可经此接口赋值。",
)
def set_user_role(
    user_id: int,
    payload: UserRoleUpdateRequest,
    db: Session = Depends(get_db),
    operator: User = Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN)),
) -> UserPublic:
    """PATCH /users/{id}/role。不 bump 凭据版本：目标会话不中断，下一请求按新角色生效。"""
    target = db.get(User, user_id)
    if target is None:
        raise ApiError(404, "USER_NOT_FOUND", "user not found")
    if not role_service.can_assign_role(operator, target, payload.role):
        raise ApiError(403, "FORBIDDEN", "not allowed to assign this role")
    target.role = payload.role
    db.commit()
    db.refresh(target)
    return UserPublic.model_validate(target)
