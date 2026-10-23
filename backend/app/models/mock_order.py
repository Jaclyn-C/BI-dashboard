"""MockOrder 模型（REQ-20261022-02 §1.5）：mock 上游演示订单。

与 orders **严格分表**（用户定稿隔离红线）：mock 订单绝不进 orders，
真实数据链路（同步管道 / 看板 / 客户订单 / CSV）一律不读本表；
唯一消费方 = 供应商收益计算（offers/earnings，把 mock 上游的收益算进来）。

数据只经开发种子脚本写入（tools/seed_mock_data.py，幂等），
不进 Alembic 数据迁移；order_class 由同一分类器规则打标（sha256 salt）。
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Identity,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MockOrder(Base):
    """mock 上游演示订单（每个 mock 上游 order_id 独立编号，复合唯一）。"""

    __tablename__ = "mock_orders"
    __table_args__ = (
        CheckConstraint("order_class IN ('included', 'excluded')", name="mock_order_class_values"),
        UniqueConstraint("upstream_code", "order_id", name="uq_mock_orders_upstream_order"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    #: 所属 mock 上游（offers.code）
    upstream_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    #: 演示订单号（mock 上游内唯一，如 '1'..'10'）
    order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    create_time: Mapped[str] = mapped_column(String(32), nullable=False)
    create_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    currency_type: Mapped[str] = mapped_column(String(8), nullable=False)
    #: 原币金额·最小单位（同 orders 口径）
    amount_minor: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    #: 上游自报美元·最小单位
    usd_order_amount_minor: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    is_returned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    #: 同一分类器规则打标（sha256(salt:order_id) < 0.8 → included）
    order_class: Mapped[str] = mapped_column(String(16), nullable=False)
    #: 与 orders.revoked_at 对称（收益聚合统一排除条件）；mock 侧实际恒 NULL
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试用途
        return f"<MockOrder {self.upstream_code}/{self.order_id} class={self.order_class}>"
