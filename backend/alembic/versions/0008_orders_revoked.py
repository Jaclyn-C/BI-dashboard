"""orders_revoked：orders / mock_orders 撤单时间列（REQ-20261022-02 §1.7）。

上游会静默撤下部分订单（10 月实测 7 笔，均为非退款单）。本迁移加
revoked_at（NULL=正常，非空=已撤单）：同步逐日比对完整拉取日的上游
order_id 集合，本地多出的标撤单、重新出现的恢复。存量行不回填——
下一次窗口同步自动比对出历史撤单。与 order_class 正交，分类标签不动。

Revision ID: 0008_orders_revoked
Revises: 0007_mock_orders
Create Date: 2026-10-23
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_orders_revoked"
down_revision: str | None = "0007_mock_orders"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "mock_orders", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("mock_orders", "revoked_at")
    op.drop_column("orders", "revoked_at")
