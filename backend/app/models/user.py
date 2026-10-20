"""用户模型（DESIGN §4.1，REQ-20261012-01）。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# ===== 角色常量（REQ-20261020-01 §1.1）=====
ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "admin"
ROLE_CUSTOMER = "customer"
ROLE_PENDING = "pending"
ROLE_ALL = (ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_CUSTOMER, ROLE_PENDING)
#: 等级（REQ §1.3）：只能操作严格低于自己的用户
ROLE_LEVEL = {
    ROLE_SUPER_ADMIN: 3,
    ROLE_ADMIN: 2,
    ROLE_CUSTOMER: 1,
    ROLE_PENDING: 0,
}


class User(Base):
    """内部看板账号：邮箱全局唯一（AC-S4），密码只存 argon2id 摘要（AC-S1）。

    角色与等级规则见 REQ-20261020-01（role 常量在本模块）。
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    #: 规范化小写邮箱（trim + lower 后入库），唯一约束名经命名约定生成 uq_users_email
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    #: 显示用途，不唯一（Q5）
    nickname: Mapped[str] = mapped_column(String(30), nullable=False)
    #: argon2id PHC 字符串（含算法参数与盐），永不存明文、不进日志
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    #: 凭据版本：重置密码 +1，旧 token 因 pwd_ver 不匹配立即失效（Q7）
    credential_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    #: 角色（REQ-20261020-01）；注册默认 pending，等管理员分配
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ROLE_PENDING, server_default=ROLE_PENDING
    )
    #: 注册与登录时更新
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试用途；不含敏感字段
        return f"<User id={self.id} email={self.email!r}>"
