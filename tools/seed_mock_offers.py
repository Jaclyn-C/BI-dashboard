#!/usr/bin/env python3
"""开发库演示 offer 种子（REQ-20261022-02 §1.4）：mock1 / mock2 演示上游。

- 只写**本地/开发**数据库（读 backend/.env 的 DATABASE_URL）；
- mock 是演示数据：**绝不进 Alembic 迁移**（迁移会随部署进生产），
  可重复执行（按 code upsert），DB 重建后重跑即可；
- mock 上游的演示订单今后走独立表（如 mock_orders），**绝不进 orders**
  （用户定稿的隔离红线：mock 数据不得影响真实数据）。

用法（项目根目录）：
    cd backend && .venv/bin/python ../tools/seed_mock_offers.py
"""

import sys
from pathlib import Path

# 以 backend 为导入根（脚本自身在 tools/，不依赖 cwd）
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models.offer import Offer  # noqa: E402

MOCK_OFFERS = [
    {
        "code": "mock1",
        "name": "mock1 演示上游",
        "supplier_share": "0.3000",
        "in_use": False,
        "sort_order": 1,
        "description": "演示数据（mock）：仅用于界面开发预览，无真实订单与结算。",
    },
    {
        "code": "mock2",
        "name": "mock2 演示上游",
        "supplier_share": "0.6500",
        "in_use": False,
        "sort_order": 2,
        "description": "演示数据（mock）：仅用于界面开发预览，无真实订单与结算。",
    },
]


def main() -> None:
    with SessionLocal() as db:
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
            print(f"{action}: {item['code']}（分成 {item['supplier_share']}，在用={item['in_use']}）")
        db.commit()
    print("完成：mock 演示 offer 已就位（真实上游 netshort 由迁移 0005 提供）")


if __name__ == "__main__":
    main()
