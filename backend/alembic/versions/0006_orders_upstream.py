"""orders_upstream：orders.upstream_code 列（REQ-20261022-02 §1.4）。

订单归属上游的落库支撑：存量与新增订单统一落 'netshort'（当前唯一真实
上游，server_default 兜底，同步 upsert 不写此列即取默认）。mock 上游的
演示订单今后走**独立表**，绝不进 orders（用户定稿的隔离红线）。

Revision ID: 0006_orders_upstream
Revises: 0005_offers
Create Date: 2026-10-22
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_orders_upstream"
down_revision: str | None = "0005_offers"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("upstream_code", sa.String(length=32), nullable=False, server_default="netshort"),
    )


def downgrade() -> None:
    op.drop_column("orders", "upstream_code")
