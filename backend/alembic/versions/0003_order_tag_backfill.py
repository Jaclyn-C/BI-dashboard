"""order_tag_backfill：存量订单哈希打标一次性回填（REQ-20261014-01，纯数据迁移）。

无 schema 变更（orders.order_class 列 + CHECK 在 0002 已就位）；本迁移用与
运行时同一实现（app.services.classifier.classify_order_no）对存量 NULL 行
打 tag，等价于「入库时就算过」（规则是 order_id 的纯确定性函数）。

盐值来源：app.config.get_settings()（backend/.env / 环境变量，与运行时同源，
alembic env.py 已用同一 Settings 配置连接）——**迁移文件内绝不出现盐字面量**。
空盐直接失败（回滚、无半写）：宁可不迁移，也不带歧义上线。

幂等：只更新 order_class IS NULL 的行，重跑零命中零改动。

Revision ID: 0003_order_tag_backfill
Revises: 0002_dashboard_ingest
Create Date: 2026-10-14
"""

import sqlalchemy as sa

from alembic import op
from app.config import get_settings
from app.services.classifier import classify_order_no

# revision identifiers, used by Alembic.
revision: str = "0003_order_tag_backfill"
down_revision: str | None = "0002_dashboard_ingest"
branch_labels: str | None = None
depends_on: str | None = None

#: 回填批量（executemany 每批行数）
_BATCH = 1000


def upgrade() -> None:
    """按哈希规则回填全部 order_class IS NULL 的存量订单。"""
    salt = get_settings().order_filter_salt.strip()
    if not salt:
        raise RuntimeError(
            "ORDER_FILTER_SALT 未配置：回填中止（配置 backend/.env 后重跑；"
            "盐值一经使用不可更换，见 REQ-20261014-01）"
        )
    keep_ratio = get_settings().order_keep_ratio

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, order_id FROM orders WHERE order_class IS NULL")
    ).mappings()
    tagged = {"included": 0, "excluded": 0}
    batch: list[dict] = []
    for row in rows:
        order_class = classify_order_no(salt, row["order_id"], keep_ratio)
        tagged[order_class] += 1
        batch.append({"cls": order_class, "rid": row["id"]})
        if len(batch) >= _BATCH:
            bind.execute(
                sa.text(
                    "UPDATE orders SET order_class = :cls, updated_at = now() "
                    "WHERE id = :rid AND order_class IS NULL"
                ),
                batch,
            )
            batch = []
    if batch:
        bind.execute(
            sa.text(
                "UPDATE orders SET order_class = :cls, updated_at = now() "
                "WHERE id = :rid AND order_class IS NULL"
            ),
            batch,
        )

    # 后置检查：不留 NULL（含回填窗口期间并发同步插入的行也应已被同步打标）
    remaining = bind.execute(
        sa.text("SELECT count(*) FROM orders WHERE order_class IS NULL")
    ).scalar_one()
    if remaining:
        raise RuntimeError(f"backfill post-check failed: {remaining} rows still NULL")

    total = tagged["included"] + tagged["excluded"]
    print(
        f"[0003] backfilled {total} orders: "
        f"included={tagged['included']} excluded={tagged['excluded']}"
    )


def downgrade() -> None:
    """数据迁移的诚实逆操作：tag 全部置回 NULL。

    注意：会连同清掉迁移之后由同步写入的 tag——仅限开发环境使用。
    """
    op.execute(sa.text("UPDATE orders SET order_class = NULL"))
