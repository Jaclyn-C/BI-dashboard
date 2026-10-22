"""Offer 模型（REQ-20261022-02）：上游合作 offer——本系统自有配置数据，
上游接口不提供（REQ §1.2 选定库表方案）。分成比例走 Numeric（金额纪律）。
"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Identity, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Offer(Base):
    """一个上游客户 = 一个 offer（合作条款载体）。

    ``supplier_share`` 为供应商分成比例（0.5000 = 50%）；``in_use`` 标记
    是否已在用（页面「在用」/「全部可选」两板块据此拆分，REQ §1.1）。
    """

    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    #: 稳定标识代码（如 'netshort'），唯一
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    #: 展示名
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    #: 补充说明，可空（无则卡片不显示说明行）
    description: Mapped[str | None] = mapped_column(String(500))
    #: 供应商分成比例，Numeric(5,4)；0.5 = 50%
    supplier_share: Mapped[float] = mapped_column(
        Numeric(5, 4), nullable=False, default=0.5, server_default="0.5"
    )
    #: 是否在用
    in_use: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    #: 展示排序（小在前）
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
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

    def __repr__(self) -> str:  # pragma: no cover - 调试用途
        return f"<Offer id={self.id} code={self.code!r} in_use={self.in_use}>"
