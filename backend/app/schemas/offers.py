"""Offer 入出参（REQ-20261022-02，DESIGN §2/§4）。

``supplier_share`` 保真输出 Decimal 字符串；``supplier_share_pct`` 为后端
预格式百分比字符串（前端零运算，仅拼 '%'，金额纪律延伸）。
"""

from decimal import Decimal

from pydantic import BaseModel

from app.models.offer import Offer


def share_pct(share: Decimal) -> str:
    """比例 → 百分比字符串（去尾零：50.00 → 50；12.50 → 12.5）。"""
    pct = share * 100
    return f"{pct:f}".rstrip("0").rstrip(".")


class OfferItem(BaseModel):
    """GET /offers 响应行。"""

    id: int
    code: str
    name: str
    description: str | None
    supplier_share: str
    supplier_share_pct: str
    in_use: bool
    sort_order: int

    @classmethod
    def of(cls, offer: Offer) -> "OfferItem":
        """ORM → 响应：比例转字符串并预格式百分比。"""
        return cls(
            id=offer.id,
            code=offer.code,
            name=offer.name,
            description=offer.description,
            supplier_share=f"{offer.supplier_share:f}",
            supplier_share_pct=share_pct(offer.supplier_share),
            in_use=offer.in_use,
            sort_order=offer.sort_order,
        )


class OffersListResponse(BaseModel):
    """GET /offers 响应（in_use 优先 → sort_order → id，DESIGN §2）。"""

    offers: list[OfferItem]


class OfferEarningItem(BaseModel):
    """GET /offers/earnings 响应行（在用 offer，REQ §1.5）。"""

    code: str
    name: str
    supplier_share: str
    supplier_share_pct: str
    order_count: int  # 已计入订单数
    order_total_usd: str  # 已计入订单美元金额（真值字符串）
    supplier_earnings_usd: str  # 供应商收益（真值字符串，×比例不取整）


class OfferEarningsResponse(BaseModel):
    """GET /offers/earnings 响应：在用 offer 合计 + 逐 offer 明细。"""

    total_supplier_earnings_usd: str
    total_order_usd: str
    total_order_count: int
    earnings: list[OfferEarningItem]
