"""Offer 路由（REQ-20261022-02 §1.1/§1.2/§1.5，DESIGN §2/§4）。

- GET /offers          只读列表（admin+；分成条款属内部商业数据，客户/待分配 403）
- GET /offers/earnings 供应商收益（在用 offer；真实/mock 订单分表聚合，admin+）
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.offer import Offer
from app.models.user import ROLE_ADMIN, ROLE_SUPER_ADMIN, User
from app.schemas.offers import OfferEarningsResponse, OfferItem, OffersListResponse
from app.services import offers_service

router = APIRouter(prefix="/offers", tags=["offers"])


@router.get(
    "",
    response_model=OffersListResponse,
    summary="Offer 列表（管理员）",
    description="全部上游合作 offer：名称/标识/供应商分成比例/说明/在用标记。"
    "本系统自有配置数据（非上游接口数据，REQ-20261022-02）。仅 admin 与 super_admin 可访问。",
)
def list_offers(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN)),
) -> OffersListResponse:
    """GET /offers：in_use 优先 → sort_order → id（稳定排序）。"""
    offers = db.scalars(
        select(Offer).order_by(Offer.in_use.desc(), Offer.sort_order, Offer.id)
    ).all()
    return OffersListResponse(offers=[OfferItem.of(o) for o in offers])


@router.get(
    "/earnings",
    response_model=OfferEarningsResponse,
    summary="供应商收益（管理员）",
    description="在用 offer 的供应商收益：Σ已计入订单美元金额 × 分成比例"
    "（真值字符串，分以下尾数不取整）。真实上游取 orders、mock 上游取 mock_orders，"
    "两表分立聚合互不影响（REQ-20261022-02 §1.5）。仅 admin 与 super_admin 可访问。",
)
def get_offer_earnings(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN)),
) -> OfferEarningsResponse:
    """GET /offers/earnings。"""
    return offers_service.offer_earnings(db)
