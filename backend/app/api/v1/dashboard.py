"""看板路由（DESIGN-20261012-02 §5，REQ AC-SEC2/X*；A8 后端侧）。

路由保持薄：参数解析 → 服务调用 → 组响应。全部挂 ``Depends(get_current_user)``
（登录墙，AC-SEC2）；错误信封复用既有 ApiError 机制（§5.6：本域不新增语义码，
单飞冲突走 202 accepted=false，不用 429）。

- GET  /dashboard/summary      一次装载全看板（§5.2）
- GET  /dashboard/orders       订单分页表（§5.3）
- GET  /dashboard/orders.csv   CSV 导出（§5.4，B-T8）
- GET  /dashboard/customer-orders     客户视图订单表（REQ-20261015-02）
- GET  /dashboard/customer-orders.csv 客户视图当前页 CSV（REQ-20261015-02）
- POST /dashboard/sync         手动刷新（202 + 进度轮询，§5.5）
- GET  /dashboard/sync/status

权限（REQ-20261020-01）：内部接口 admin+；customer-orders 三正式角色。
"""

import asyncio
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.api.errors import ApiError
from app.models.user import ROLE_ADMIN, ROLE_CUSTOMER, ROLE_SUPER_ADMIN
from app.schemas.dashboard import (
    MAX_RANGE_DAYS,
    TABLE_PAGE_SIZE,
    ClassFilter,
    CsvLang,
    CsvScope,
    CustomerOrderRow,
    CustomerOrdersResponse,
    OrderRow,
    OrdersResponse,
    SortDir,
    SortKey,
    StatusFilter,
    SummaryResponse,
    SyncAcceptedResponse,
    SyncRequest,
    SyncStatusResponse,
)
from app.services import aggregation, csv_export, orders_query, sync_service
from app.services.money import money_str

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],  # AC-SEC2
)


def parse_range(date_from: date, date_to: date) -> tuple[date, date]:
    """from/to 防御校验（§5.1）：from ≤ to、跨度 ≤ 92 天，否则 422 VALIDATION_ERROR。"""
    details: list[dict[str, str]] = []
    if date_from > date_to:
        details.append({"field": "to", "msg": "from must be on or before to"})
    if (date_to - date_from).days + 1 > MAX_RANGE_DAYS:
        details.append(
            {"field": "from", "msg": f"range must be at most {MAX_RANGE_DAYS} days"}
        )
    if details:
        raise ApiError(422, "VALIDATION_ERROR", "invalid date range", details=details)
    return date_from, date_to


RangeFrom = Annotated[date, Query(alias="from", description="区间起点 YYYY-MM-DD")]
RangeTo = Annotated[date, Query(alias="to", description="区间终点 YYYY-MM-DD（含）")]


@router.get(
    "/summary",
    response_model=SummaryResponse,
    dependencies=[Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN))],
    summary="看板总览（一次装载除订单表外全部区块）",
    description="KPI（REQ-20261014-01 分成口径）/ 每日双口径 / 广告 / 新旧美元对比 / 国家分布，"
    "聚合在后端以 Decimal 完成。class=included/excluded 为数据集切换："
    "全部内容只含该类订单，不适用卡片的值为 null。",
)
def summary(
    date_from: RangeFrom,
    date_to: RangeTo,
    order_class: ClassFilter = Query(default="all", alias="class"),
    db: Session = Depends(get_db),
) -> SummaryResponse:
    """GET /dashboard/summary（§5.2 契约）。"""
    date_from, date_to = parse_range(date_from, date_to)
    return aggregation.build_summary(db, date_from, date_to, order_class)


@router.get(
    "/orders",
    response_model=OrdersResponse,
    dependencies=[Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN))],
    summary="订单明细分页表",
    description="筛选（类别/币种/状态）+ 排序（时间/币种/金额/美元）+ 25 行/页分页。"
    "class 筛选仅作用于列表展示（REQ-20261014-01 §六）。",
)
def orders(
    date_from: RangeFrom,
    date_to: RangeTo,
    currency: str = Query(default="all", description="币种筛选：all 或币种码"),
    status: StatusFilter = Query(default="all"),
    order_class: ClassFilter = Query(default="all", alias="class"),
    sort: SortKey = Query(default="date"),
    direction: SortDir = Query(default="desc", alias="dir"),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
) -> OrdersResponse:
    """GET /dashboard/orders（§5.3 契约）。"""
    date_from, date_to = parse_range(date_from, date_to)
    base = orders_query.orders_query(
        date_from, date_to, currency=currency, status=status, order_class=order_class
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    base_all = orders_query.orders_query(date_from, date_to)
    total_in_range = db.scalar(select(func.count()).select_from(base_all.subquery())) or 0

    stmt = orders_query.apply_sort(base, sort, direction).offset(
        (page - 1) * TABLE_PAGE_SIZE
    ).limit(TABLE_PAGE_SIZE)
    rows = db.scalars(stmt).all()
    pages, _ = orders_query.paginate(total, page)

    return OrdersResponse(
        rows=[
            OrderRow(
                order_id=row.order_id,
                upstream=row.upstream_code,
                create_time=row.create_time,
                create_date=row.create_date.isoformat(),
                country_key=aggregation.country_key(row.language),
                language=row.language,
                currency=row.currency_type,
                amount=money_str(row.amount_minor),
                usd=(
                    money_str(row.usd_order_amount_minor)
                    if row.usd_order_amount_minor is not None
                    else None
                ),
                order_class=row.order_class,  # tag 真值（REQ-20261014-01）
                status="returned" if row.is_returned else "completed",
            )
            for row in rows
        ],
        page=page,
        page_size=TABLE_PAGE_SIZE,
        pages=pages,
        total=total,
        total_in_range=total_in_range,
        currencies=orders_query.range_currencies(db, date_from, date_to),
    )


@router.get(
    "/customer-orders",
    response_model=CustomerOrdersResponse,
    dependencies=[Depends(require_role(ROLE_CUSTOMER, ROLE_ADMIN, ROLE_SUPER_ADMIN))],
    summary="客户视图订单表（下游可见数据预览，REQ-20261015-02）",
    description="仅返回已计入（included）订单的纯订单信息——不含 order_class/tag 等"
    "任何内部分类字段（字段裁剪在后端完成）。未来供应商接口以此字段集为契约起点。",
)
def customer_orders(
    date_from: RangeFrom,
    date_to: RangeTo,
    currency: str = Query(default="all", description="币种筛选：all 或币种码"),
    status: StatusFilter = Query(default="all"),
    sort: SortKey = Query(default="date"),
    direction: SortDir = Query(default="desc", alias="dir"),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
) -> CustomerOrdersResponse:
    """GET /dashboard/customer-orders：included-only + 内部字段后端裁剪。"""
    date_from, date_to = parse_range(date_from, date_to)
    base = orders_query.orders_query(
        date_from, date_to, currency=currency, status=status, order_class="included"
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    base_all = orders_query.orders_query(date_from, date_to, order_class="included")
    total_in_range = db.scalar(select(func.count()).select_from(base_all.subquery())) or 0

    stmt = orders_query.apply_sort(base, sort, direction).offset(
        (page - 1) * TABLE_PAGE_SIZE
    ).limit(TABLE_PAGE_SIZE)
    rows = db.scalars(stmt).all()
    pages, _ = orders_query.paginate(total, page)

    return CustomerOrdersResponse(
        rows=[
            CustomerOrderRow(
                order_id=row.order_id,
                upstream=row.upstream_code,
                create_time=row.create_time,
                country_key=aggregation.country_key(row.language),
                language=row.language,
                currency=row.currency_type,
                amount=money_str(row.amount_minor),
                usd=(
                    money_str(row.usd_order_amount_minor)
                    if row.usd_order_amount_minor is not None
                    else None
                ),
                status="returned" if row.is_returned else "completed",
            )
            for row in rows
        ],
        page=page,
        page_size=TABLE_PAGE_SIZE,
        pages=pages,
        total=total,
        total_in_range=total_in_range,
        currencies=orders_query.range_currencies(db, date_from, date_to),
    )


@router.get(
    "/customer-orders.csv",
    dependencies=[Depends(require_role(ROLE_CUSTOMER, ROLE_ADMIN, ROLE_SUPER_ADMIN))],
    summary="客户视图订单 CSV（当前筛选全量）",
    description="与 /customer-orders 同参同序，导出当前筛选**全部行**（跨页）的 7 列纯订单信息"
    "（included-only，不含任何分类字段）。UTF-8 BOM + CRLF；"
    "文件名 customer_orders_{from}_to_{to}.csv。",
)
def customer_orders_csv(
    date_from: RangeFrom,
    date_to: RangeTo,
    currency: str = Query(default="all", description="币种筛选：all 或币种码"),
    status: StatusFilter = Query(default="all"),
    sort: SortKey = Query(default="date"),
    direction: SortDir = Query(default="desc", alias="dir"),
    lang: CsvLang = Query(default="en"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """GET /dashboard/customer-orders.csv：included-only + 当前筛选全量 + 字段后端裁剪。"""
    date_from, date_to = parse_range(date_from, date_to)
    return StreamingResponse(
        csv_export.iter_customer_csv_chunks(
            db,
            date_from,
            date_to,
            currency=currency,
            status=status,
            sort=sort,
            direction=direction,
            lang=lang,
        ),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                'attachment; filename="'
                f'{csv_export.customer_csv_filename(date_from, date_to)}"'
            )
        },
    )


@router.get(
    "/orders.csv",
    dependencies=[Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN))],
    summary="订单 CSV 导出（流式）",
    description="scope=view 套用表格筛选+排序全量行；scope=all 区间全量"
    "（create_time desc 固定序）。UTF-8 BOM + CRLF；class 列填已计入/被剔除，"
    "revShare/earningsUsd 两列空（旧口径死列，REQ-20261014-01）；"
    "文件名两档同名 orders_all_{from}_to_{to}.csv（AC-X2 差异登记 §4.6-4）。",
)
def orders_csv(
    date_from: RangeFrom,
    date_to: RangeTo,
    scope: CsvScope = Query(default="view"),
    currency: str = Query(default="all"),
    status: StatusFilter = Query(default="all"),
    order_class: ClassFilter = Query(default="all", alias="class"),
    sort: SortKey = Query(default="date"),
    direction: SortDir = Query(default="desc", alias="dir"),
    lang: CsvLang = Query(default="en"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """GET /dashboard/orders.csv（§5.4 契约，AC-X1–X4）。"""
    date_from, date_to = parse_range(date_from, date_to)
    return StreamingResponse(
        csv_export.iter_csv_chunks(
            db,
            date_from,
            date_to,
            scope=scope,
            currency=currency,
            status=status,
            order_class=order_class,
            sort=sort,
            direction=direction,
            lang=lang,
        ),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{csv_export.csv_filename(date_from, date_to)}"'
            )
        },
    )


@router.post(
    "/sync",
    response_model=SyncAcceptedResponse,
    status_code=202,
    dependencies=[Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN))],
    summary="手动刷新（触发当前区间同步）",
    description="↻ 按钮：对当前筛选区间触发一次即时同步（全区间重拉，服务端钳制跨度与上界）。"
    "已有同步在跑时 accepted=false（不报错，前端继续轮询进度）。",
)
async def trigger_sync(
    payload: SyncRequest, db: Session = Depends(get_db)
) -> SyncAcceptedResponse:
    """POST /dashboard/sync（§5.5 契约）。"""
    accepted = await asyncio.to_thread(
        sync_service.start_manual, payload.date_from, payload.date_to
    )
    return SyncAcceptedResponse(accepted=accepted, status=sync_service.status_snapshot(db))


@router.get(
    "/sync/status",
    response_model=SyncStatusResponse,
    dependencies=[Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN))],
    summary="同步进度与最近一次运行",
    description="state=running 时 current 含「{a}/{b} 天」进度（AC-S1 loadingDays）；"
    "last_run 持久于 sync_runs（重启后仍可查最近结果）。",
)
def sync_status(db: Session = Depends(get_db)) -> SyncStatusResponse:
    """GET /dashboard/sync/status（§5.5 契约）。"""
    return sync_service.status_snapshot(db)
