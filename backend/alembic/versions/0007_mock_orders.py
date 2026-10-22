"""mock_orders：mock 上游演示订单表（REQ-20261022-02 §1.5）。

只建表结构，**不带数据**——mock 订单由开发种子脚本写入（tools/seed_mock_data.py），
生产环境此表恒为空，真实数据链路不读本表（隔离红线）。与 orders 分表是
用户定稿：mock 数据不得与真实订单同表。

Revision ID: 0007_mock_orders
Revises: 0006_orders_upstream
Create Date: 2026-10-22
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_mock_orders"
down_revision: str | None = "0006_orders_upstream"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "mock_orders",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False, primary_key=True
        ),
        sa.Column("upstream_code", sa.String(length=32), nullable=False),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("create_time", sa.String(length=32), nullable=False),
        sa.Column("create_date", sa.Date(), nullable=False),
        sa.Column("currency_type", sa.String(length=8), nullable=False),
        sa.Column("amount_minor", sa.Numeric(18, 4), nullable=False),
        sa.Column("usd_order_amount_minor", sa.Numeric(18, 4), nullable=True),
        sa.Column(
            "is_returned", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("order_class", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "order_class IN ('included', 'excluded')", name="mock_order_class_values"
        ),
        sa.UniqueConstraint("upstream_code", "order_id", name="uq_mock_orders_upstream_order"),
    )
    op.create_index("ix_mock_orders_upstream_code", "mock_orders", ["upstream_code"])


def downgrade() -> None:
    op.drop_index("ix_mock_orders_upstream_code", table_name="mock_orders")
    op.drop_table("mock_orders")
