#!/usr/bin/env python3
"""开发库 mock 演示数据种子（REQ-20261022-02 §1.4/§1.5）：mock 上游 offer + mock 订单。

- 只写**本地/开发**数据库（读 backend/.env 的 DATABASE_URL）；
- mock 是演示数据：**绝不进 Alembic 迁移**（迁移会随部署进生产），
  可重复执行（幂等 upsert），DB 重建后重跑即可；
- **隔离红线（用户定稿）**：mock 订单只进 mock_orders 独立表，绝不进 orders；
  真实数据链路（同步/看板/客户订单/CSV）不读 mock_orders；
- mock1 = 在用演示上游（收益板块参与合计）；mock2 = 仅展示（不在用）；
- 每个mock 上游 10 笔订单（单号 1..10，金额 $1.00），order_class 用与生产
  同一分类器规则打标（sha256(salt:order_id) < 0.8 → included，"按现有规律"）。

用法（项目根目录）：
    cd backend && .venv/bin/python ../tools/seed_mock_data.py
"""

import datetime as dt
import sys
from decimal import Decimal
from pathlib import Path

# 以 backend 为导入根（脚本自身在 tools/，不依赖 cwd）
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models.mock_order import MockOrder  # noqa: E402
from app.models.offer import Offer  # noqa: E402
from app.services.classifier import classify_order_no  # noqa: E402

MOCK_OFFERS = [
    {
        "code": "mock1",
        "name": "mock1 演示上游",
        "supplier_share": "0.3000",
        "in_use": True,  # 用户定稿（REQ §1.5）：在用演示 offer，参与收益合计
        "sort_order": 1,
        "description": "演示数据（mock）：在用演示上游，收益按 mock 订单（独立表）计算。",
    },
    {
        "code": "mock2",
        "name": "mock2 演示上游",
        "supplier_share": "0.6500",
        "in_use": False,  # 仅展示，不参与收益
        "sort_order": 2,
        "description": "演示数据（mock）：仅展示的可选上游，不在用。",
    },
]

#: 每个上游 10 笔演示订单：单号 1..10，$1.00（USD，minor=100）
MOCK_ORDER_COUNT = 10
MOCK_USD_MINOR = Decimal("100")


def seed_offers(db) -> None:
    for item in MOCK_OFFERS:
        offer = db.scalar(select(Offer).where(Offer.code == item["code"]))
        if offer is None:
            offer = Offer(code=item["code"])
            db.add(offer)
            action = "新增"
        else:
            action = "更新"
        offer.name = item["name"]
        offer.supplier_share = item["supplier_share"]
        offer.in_use = item["in_use"]
        offer.sort_order = item["sort_order"]
        offer.description = item["description"]
        print(f"{action} offer {item['code']}（分成 {item['supplier_share']}，在用={item['in_use']}）")


def seed_orders(db) -> None:
    settings = get_settings()
    for item in MOCK_OFFERS:
        code = item["code"]
        included = 0
        for i in range(1, MOCK_ORDER_COUNT + 1):
            order_id = str(i)
            create_time = f"2026-10-{i:02d} 12:00:00"
            order_class = classify_order_no(
                settings.order_filter_salt, order_id, settings.order_keep_ratio
            )
            included += order_class == "included"
            row = db.scalar(
                select(MockOrder).where(
                    MockOrder.upstream_code == code, MockOrder.order_id == order_id
                )
            )
            if row is None:
                row = MockOrder(upstream_code=code, order_id=order_id)
                db.add(row)
            row.create_time = create_time
            row.create_date = dt.date.fromisoformat(create_time[:10])
            row.currency_type = "USD"
            row.amount_minor = MOCK_USD_MINOR
            row.usd_order_amount_minor = MOCK_USD_MINOR
            row.is_returned = False
            row.order_class = order_class
        print(f"{code}：{MOCK_ORDER_COUNT} 笔订单（included {included} / excluded "
              f"{MOCK_ORDER_COUNT - included}，同一分类器规则打标）")


def main() -> None:
    with SessionLocal() as db:
        seed_offers(db)
        seed_orders(db)
        db.commit()
    print("完成：mock 演示数据已就位（真实上游 netshort 由迁移 0005 提供，不受影响）")


if __name__ == "__main__":
    main()
