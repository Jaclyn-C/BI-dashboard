"""邮箱验证码模型（DESIGN §4.2/§4.3，REQ-20261012-01）。

只存 HMAC-SHA256 摘要（密钥派生自 SECRET_KEY），明文仅出现在邮件与
开发日志两个出口（AC-S2）。purpose 用 VARCHAR+CHECK 而非 PG 原生 enum，
保证迁移可逆（DESIGN §4.2）。
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Identity,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class VerificationCode(Base):
    """验证码记录：发码限流计数与验码状态机的唯一载体。"""

    __tablename__ = "verification_codes"
    __table_args__ = (
        CheckConstraint("purpose IN ('register', 'reset')", name="purpose_values"),
        # 限流计数查询锚点（email 跨 purpose 共用额度，Q4）
        Index("ix_verification_codes_email_created", "email", "created_at"),
        # 取最新有效码（partial index）
        Index(
            "ix_verification_codes_email_purpose_active",
            "email",
            "purpose",
            postgresql_where=text("consumed_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    #: 规范化小写；不建 FK——注册场景用户行尚不存在（DESIGN §4.2）
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    #: HMAC-SHA256(code, 派生密钥) 十六进制——无服务端密钥无法离线爆破
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    #: 校验失败 +1（行级 UPDATE 自增防并发绕过），达上限作废（Q3）
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    #: 验证成功 / 被新码顶替 / 尝试耗尽时打点
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now()
    )
