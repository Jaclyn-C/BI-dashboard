"""订单模型（DESIGN-20261012-02 §2.1，REQ-20261012-02）。

上游 /open/order/list 全量落库：order_id 唯一约束是同步幂等键（AC-S3/U3）；
createTime 字符串原值存储（零时区换算，D6/AC-S8），create_date 为派生日界列
（=原值前 10 位，对标 HTML slice(0,10)）。金额列全 Numeric（AC-U6，禁 float）。
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
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Order(Base):
    """上游 CPS 订单。

    order_class（REQ-20261014-01）：入库时经 sha256(salt:order_id) 哈希判定
    （included=已计入/下发供应商，excluded=剔除/不下发），只写一次、永不改变
    （sync_service 的 upsert 更新集不含该列）。存量回填见迁移 0003。
    """

    __tablename__ = "orders"
    __table_args__ = (
        # tag 合法值约束（存量回填前可为 NULL），无索引（DESIGN §2.1）
        CheckConstraint("order_class IN ('included', 'excluded')", name="order_class_values"),
        Index("ix_orders_create_date", "create_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    #: 上游 orderId；UNIQUE uq_orders_order_id = upsert 冲突目标（幂等键）
    order_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    #: 订单归属上游（REQ-20261022-02 §1.4）；同步 upsert 不写此列，恒取默认
    #: 'netshort'（当前唯一真实上游）。mock 演示订单走独立表，绝不进本表。
    upstream_code: Mapped[str] = mapped_column(
        String(32), nullable=False, default="netshort", server_default="netshort"
    )
    #: 上游原值 `YYYY-MM-DD HH:mm:ss`；字符串字典序 = 时间序（排序直接用它）
    create_time: Mapped[str] = mapped_column(String(32), nullable=False)
    #: 派生日界 = create_time[:10]（区间查询 / 按日聚合走此列）
    create_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    #: 上游透传（空串兜底）
    theater_id: Mapped[str] = mapped_column(String(64), nullable=False)
    chapter_id: Mapped[str] = mapped_column(String(64), nullable=False)
    #: 如 `en_US`；国家推断输入（AC-AG4）
    language: Mapped[str | None] = mapped_column(String(16))
    currency_type: Mapped[str] = mapped_column(String(8), nullable=False)
    #: 原币金额·最小单位（RQ-4：/100 仅展示层，存储保留 Decimal 原值）
    amount_minor: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    #: 上游 orderAmount 规范名（上游自报美元·最小单位）；缺失 = NULL → 新口径排除+计数（AC-AG3）
    usd_order_amount_minor: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    #: 上游原值；空白归一为 NULL
    refund_time: Mapped[str | None] = mapped_column(String(32))
    #: 入库派生：refund_time 非空白（HTML isReturned 同规则，AC-O7）
    is_returned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    promotion_code: Mapped[str | None] = mapped_column(String(64))
    #: B1 恒 NULL（分类器空实现），CHECK 见 __table_args__
    order_class: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试用途
        return f"<Order order_id={self.order_id!r} create_time={self.create_time!r}>"
