"""角色业务（REQ-20261020-01）：等级判定 + 超管启动提权。

被 api/deps（require_role）与 api/v1/users（角色调整）、main.lifespan（提权）复用。
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import (
    ROLE_ADMIN,
    ROLE_CUSTOMER,
    ROLE_LEVEL,
    ROLE_PENDING,
    ROLE_SUPER_ADMIN,
    User,
)

logger = logging.getLogger("app")

#: 接口可赋的角色——super_admin 只能由 SUPER_ADMIN_EMAIL 启动机制产生（REQ §1.3）
ASSIGNABLE_ROLES = (ROLE_ADMIN, ROLE_CUSTOMER, ROLE_PENDING)


def can_assign_role(operator: User, target: User, new_role: str) -> bool:
    """等级规则（REQ §1.3）：不许动自己；只能动严格低于自己的人；新角色不得超过自己等级。

    操作者须 admin 及以上（customer/pending 无分配权，REQ §1.5）。
    """
    if operator.id == target.id:
        return False
    if new_role not in ASSIGNABLE_ROLES:
        return False
    if ROLE_LEVEL[operator.role] < ROLE_LEVEL[ROLE_ADMIN]:
        return False
    return (
        ROLE_LEVEL[operator.role] > ROLE_LEVEL[target.role]
        and ROLE_LEVEL[new_role] <= ROLE_LEVEL[operator.role]
    )


def ensure_super_admin(db: Session, email: str) -> User | None:
    """启动幂等提权（REQ §1.4）：账号存在则确保 super_admin，缺失记日志跳过。

    不 bump credential_version——超管本人无需重新登录。
    """
    normalized = email.strip().lower()
    if not normalized:
        return None
    user = db.scalar(select(User).where(User.email == normalized))
    if user is None:
        logger.warning("SUPER_ADMIN_EMAIL=%s 未注册，跳过超管提权", normalized)
        return None
    if user.role != ROLE_SUPER_ADMIN:
        user.role = ROLE_SUPER_ADMIN
        db.commit()
        logger.info("用户 %s 已提权为 super_admin", normalized)
    return user
