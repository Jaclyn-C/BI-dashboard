"""Offer 入出参（REQ-20261022-02，DESIGN §2）。

``supplier_share`` 保真输出 Decimal 字符串；``supplier_share_pct`` 为后端
预格式百分比字符串（前端零运算，仅拼 '%'，金额纪律延伸）。
"""

from pydantic import BaseModel

from app.models.offer import Offer


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
        """ORM → 响应：比例转字符串并预格式百分比（去尾零，如 50 / 12.5）。"""
        share = offer.supplier_share  # Decimal
        pct = share * 100
        # 去尾零：50.00 → 50；12.50 → 12.5
        pct_str = f"{pct:f}".rstrip("0").rstrip(".")
        return cls(
            id=offer.id,
            code=offer.code,
            name=offer.name,
            description=offer.description,
            supplier_share=f"{share:f}",
            supplier_share_pct=pct_str,
            in_use=offer.in_use,
            sort_order=offer.sort_order,
        )


class OffersListResponse(BaseModel):
    """GET /offers 响应（in_use 优先 → sort_order → id，DESIGN §2）。"""

    offers: list[OfferItem]
