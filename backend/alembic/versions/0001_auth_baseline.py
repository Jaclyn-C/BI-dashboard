"""auth baseline：users + verification_codes（REQ-20261012-01，DESIGN §4.1/§4.2）

首个基线迁移，由 ``alembic revision --autogenerate`` 生成后人工核对：
- 两表（users / verification_codes）；
- 唯一约束 uq_users_email（邮箱全局唯一，AC-S4）；
- CHECK ck_verification_codes_purpose_values（VARCHAR+CHECK，迁移可逆性优先）；
- 两个普通索引 + 一个 partial index（取最新有效码）；
- 主键 BIGINT IDENTITY；可升级可降级。

Revision ID: 0001_auth_baseline
Revises:
Create Date: 2026-10-12 11:46:04.698982

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_auth_baseline"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("nickname", sa.String(length=30), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("credential_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "verification_codes",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "purpose IN ('register', 'reset')", name=op.f("ck_verification_codes_purpose_values")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_verification_codes")),
    )
    op.create_index(
        "ix_verification_codes_email_created",
        "verification_codes",
        ["email", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_verification_codes_email_purpose_active",
        "verification_codes",
        ["email", "purpose"],
        unique=False,
        postgresql_where=sa.text("consumed_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_verification_codes_email_purpose_active",
        table_name="verification_codes",
        postgresql_where=sa.text("consumed_at IS NULL"),
    )
    op.drop_index("ix_verification_codes_email_created", table_name="verification_codes")
    op.drop_table("verification_codes")
    op.drop_table("users")
