"""dashboard ingest：orders + ad_revenue_daily + sync_runs（REQ-20261012-02，DESIGN §2）

由 ``alembic revision --autogenerate`` 生成后人工核对：
- orders：uq_orders_order_id 幂等键（AC-S3/U3）+ ix_orders_create_date 区间扫描；
  金额列 Numeric(18,4)（AC-U6）；order_class CHECK 为 B1 恢复预留（B1 恒 NULL）；
- ad_revenue_daily：date 主键幂等（AC-U4），金额 Numeric(14,2)（美元最小单位）；
- sync_runs：trigger/status CHECK、truncated_dates JSONB（默认 '[]'）、ix_sync_runs_started_at；
- 可升级可降级（downgrade 按逆序拆表）。

Revision ID: 0002_dashboard_ingest
Revises: 0001_auth_baseline
Create Date: 2026-10-12 17:40:43.656064

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_dashboard_ingest"
down_revision: str | None = "0001_auth_baseline"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ad_revenue_daily",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("amount_minor", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("date", name=op.f("pk_ad_revenue_daily")),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("create_time", sa.String(length=32), nullable=False),
        sa.Column("create_date", sa.Date(), nullable=False),
        sa.Column("theater_id", sa.String(length=64), nullable=False),
        sa.Column("chapter_id", sa.String(length=64), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("currency_type", sa.String(length=8), nullable=False),
        sa.Column("amount_minor", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("usd_order_amount_minor", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("refund_time", sa.String(length=32), nullable=True),
        sa.Column("is_returned", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("promotion_code", sa.String(length=64), nullable=True),
        sa.Column("order_class", sa.String(length=16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "order_class IN ('included', 'excluded')", name=op.f("ck_orders_order_class_values")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint("order_id", name=op.f("uq_orders_order_id")),
    )
    op.create_index("ix_orders_create_date", "orders", ["create_date"], unique=False)
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("orders_fetched", sa.Integer(), server_default="0", nullable=False),
        sa.Column("orders_upserted", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "truncated_dates",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("orders_error", sa.Text(), nullable=True),
        sa.Column("ad_error", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'success', 'partial', 'failed')",
            name=op.f("ck_sync_runs_status_values"),
        ),
        sa.CheckConstraint(
            "trigger IN ('scheduled', 'manual', 'backfill')",
            name=op.f("ck_sync_runs_trigger_values"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_runs")),
    )
    op.create_index("ix_sync_runs_started_at", "sync_runs", ["started_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_sync_runs_started_at", table_name="sync_runs")
    op.drop_table("sync_runs")
    op.drop_index("ix_orders_create_date", table_name="orders")
    op.drop_table("orders")
    op.drop_table("ad_revenue_daily")
