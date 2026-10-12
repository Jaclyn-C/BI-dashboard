"""同步运行记录模型（DESIGN-20261012-02 §2.3，REQ-20261012-02）。

每次同步任务一行：状态行「更新于 t」、降级横幅（truncated/ad_error）、
覆盖自愈判定（§3.3.3 以成功运行窗口并集计算已覆盖日期）都读本表。
"""

import datetime as dt

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SyncRun(Base):
    """一次同步的运行记录（orders + ad 两阶段）。"""

    __tablename__ = "sync_runs"
    __table_args__ = (
        CheckConstraint("trigger IN ('scheduled', 'manual', 'backfill')", name="trigger_values"),
        CheckConstraint(
            "status IN ('running', 'success', 'partial', 'failed')", name="status_values"
        ),
        # 取最新运行行（状态行 / last_run）
        Index("ix_sync_runs_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    #: scheduled（定时，含覆盖自愈补拉）/ manual（↻ 手动插队）/ backfill（回填）
    trigger: Mapped[str] = mapped_column(String(16), nullable=False)
    #: 本次覆盖日期窗（含两端）
    window_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    window_end: Mapped[dt.date] = mapped_column(Date, nullable=False)
    #: orders 阶段失败→failed；成功但有广告失败或截断→partial；否则 success（DESIGN §2.3）
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    #: 诊断用计数
    orders_fetched: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    orders_upserted: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    #: 二分到底仍整页的日期清单（AC-S7 横幅按日精确呈现）
    truncated_dates: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    #: 两阶段错误分离（AC-S9：广告失败不连坐订单）
    orders_error: Mapped[str | None] = mapped_column(Text)
    ad_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now(), server_default=func.now()
    )
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:  # pragma: no cover - 调试用途
        return f"<SyncRun id={self.id} trigger={self.trigger!r} status={self.status!r}>"
