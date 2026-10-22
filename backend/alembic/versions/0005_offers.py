"""offers：上游合作 offer 表 + netshort 种子（REQ-20261022-02）。

本系统自有配置数据（上游接口不提供，REQ §1.2 选定库表方案）。
当前唯一真实 offer：netshort（供应商分成 50%，在用）；不虚构其他 offer。

Revision ID: 0005_offers
Revises: 0004_user_roles
Create Date: 2026-10-22
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_offers"
down_revision: str | None = "0004_user_roles"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "offers",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), nullable=False, primary_key=True
        ),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column(
            "supplier_share", sa.Numeric(5, 4), nullable=False, server_default="0.5"
        ),
        sa.Column("in_use", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("code", name="uq_offers_code"),
    )
    # 种子：netshort（唯一真实上游，飞书接口文档 v1.2.0 对接方）
    op.execute(
        """
        INSERT INTO offers (code, name, description, supplier_share, in_use, sort_order)
        VALUES (
            'netshort',
            'netshort 短剧 CPS',
            '当前对接的上游（飞书接口文档 v1.2.0 的 8 个接口）。'
            '此条目为本系统自有配置，非上游接口数据。',
            0.5000,
            TRUE,
            0
        )
        """
    )


def downgrade() -> None:
    op.drop_table("offers")
