"""供应商收益计算（REQ-20261022-02 §1.5）。

口径：每个**在用** offer 的收益 = Σ(已计入 included 订单的上游自报美元
usd_order_amount_minor) × supplier_share；全程 Decimal（金额纪律），
输出走 money_exact 真值字符串（×比例产生分以下尾数不取整，与看板分成卡同规则）。

数据源隔离：真实上游从 orders 取，mock 上游从 mock_orders 取——两表
分别聚合后按 upstream_code 合并，互不影响（用户定稿隔离红线）。
usd 缺失的订单不计入金额、计入订单数（与看板新口径一致）。
仅内部管理页使用（admin+），不对外输出（红线 12 不涉：非下游接口）。
"""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MockOrder, Offer, Order
from app.schemas.offers import OfferEarningItem, OfferEarningsResponse, share_pct
from app.services.money import money_exact

_ZERO = Decimal(0)


def _source_sums(db: Session) -> dict[str, tuple[int, Decimal]]:
    """orders ∪ mock_orders 各自 included 聚合后合并：{code: (count, Σusd_minor)}。"""

    def agg(model):
        return db.execute(
            select(
                model.upstream_code,
                func.count(),
                func.coalesce(func.sum(model.usd_order_amount_minor), _ZERO),
            )
            .where(model.order_class == "included", model.revoked_at.is_(None))
            .group_by(model.upstream_code)
        ).all()

    merged: dict[str, tuple[int, Decimal]] = {}
    for code, cnt, total in [*agg(Order), *agg(MockOrder)]:
        if code in merged:
            prev_cnt, prev_total = merged[code]
            merged[code] = (prev_cnt + cnt, prev_total + total)
        else:
            merged[code] = (cnt, total)
    return merged


def offer_earnings(db: Session) -> OfferEarningsResponse:
    """在用 offer 的供应商收益（排序同 offers 列表：sort_order → id）。"""
    offers = db.scalars(
        select(Offer).where(Offer.in_use.is_(True)).order_by(Offer.sort_order, Offer.id)
    ).all()
    sums = _source_sums(db)

    items: list[OfferEarningItem] = []
    total_earn = _ZERO
    total_usd = _ZERO
    total_count = 0
    for offer in offers:
        count, usd_minor = sums.get(offer.code, (0, _ZERO))
        earnings_minor = usd_minor * offer.supplier_share
        total_earn += earnings_minor
        total_usd += usd_minor
        total_count += count
        items.append(
            OfferEarningItem(
                code=offer.code,
                name=offer.name,
                supplier_share=f"{offer.supplier_share:f}",
                supplier_share_pct=share_pct(offer.supplier_share),
                order_count=count,
                order_total_usd=money_exact(usd_minor),
                supplier_earnings_usd=money_exact(earnings_minor),
            )
        )
    return OfferEarningsResponse(
        total_supplier_earnings_usd=money_exact(total_earn),
        total_order_usd=money_exact(total_usd),
        total_order_count=total_count,
        earnings=items,
    )
