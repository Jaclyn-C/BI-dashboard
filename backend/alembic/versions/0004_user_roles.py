"""user_roles：users.role 列（REQ-20261020-01）。

存量账号统一落 pending（server_default）；上线后由 SUPER_ADMIN_EMAIL
启动提权机制产生唯一超管，再由超管/管理员给其余账号赋权（上线顺序见
DESIGN-20261020-01 §5 风险清单）。

Revision ID: 0004_user_roles
Revises: 0003_order_tag_backfill
Create Date: 2026-10-20
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_user_roles"
down_revision: str | None = "0003_order_tag_backfill"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=16), nullable=False, server_default="pending"),
    )


def downgrade() -> None:
    op.drop_column("users", "role")
