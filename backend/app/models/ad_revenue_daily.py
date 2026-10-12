"""广告收益日汇总模型（DESIGN-20261012-02 §2.2，REQ-20261012-02 AC-U4）。

上游 /open/order/adSummary 按日上报（ad_revenue_dollars 为美元单位），
入库 ×100 统一为美元最小单位；date 主键即幂等键（重跑按日 upsert）。
单渠道无其他维度，行数上界 92 + 少量溢出，无额外索引。
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AdRevenueDaily(Base):
    """每日广告收益（美元最小单位）。"""

    __tablename__ = "ad_revenue_daily"

    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    amount_minor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )
