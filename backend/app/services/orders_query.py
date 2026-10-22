"""订单明细查询构造（DESIGN-20261012-02 §5.3；订单表与 CSV 共用）。

筛选（类别/币种/状态）+ 排序（时间/币种/金额/美元）在 SQL 完成：
- date → create_time（字符串字典序 = 时间序，AC-S8）；
- usd → coalesce(usd, -1)（HTML null→-1 语义，AC-O3）；
- 末位统一追加 order_id 决定性 tiebreak。
"""

from datetime import date

from sqlalchemy import Select, func, select

from app.models import Order
from app.schemas.dashboard import TABLE_PAGE_SIZE, ClassFilter, SortDir, SortKey, StatusFilter

#: 排序键 → 表达式（DESIGN §5.3）
_SORT_COLUMNS = {
    "date": Order.create_time,
    "currency": Order.currency_type,
    "amount": Order.amount_minor,
    "usd": func.coalesce(Order.usd_order_amount_minor, -1),
}


def orders_query(
    date_from: date,
    date_to: date,
    *,
    currency: str = "all",
    status: StatusFilter = "all",
    order_class: ClassFilter = "all",
    upstream: str = "all",
) -> Select:
    """区间 + 筛选的基础查询（未排序未分页）。class 筛选 REQ-20261014-01 §六；
    upstream 筛选 REQ-20261022-02 §1.4。
    """
    stmt = select(Order).where(Order.create_date >= date_from, Order.create_date <= date_to)
    if currency and currency != "all":
        stmt = stmt.where(Order.currency_type == currency)
    if status == "completed":
        stmt = stmt.where(Order.is_returned.is_(False))
    elif status == "returned":
        stmt = stmt.where(Order.is_returned.is_(True))
    if order_class != "all":
        stmt = stmt.where(Order.order_class == order_class)
    if upstream and upstream != "all":
        stmt = stmt.where(Order.upstream_code == upstream)
    return stmt


def apply_sort(stmt: Select, sort: SortKey, direction: SortDir) -> Select:
    """应用排序：主键 + order_id 决定性 tiebreak。"""
    column = _SORT_COLUMNS[sort]
    if direction == "asc":
        return stmt.order_by(column.asc(), Order.order_id.asc())
    return stmt.order_by(column.desc(), Order.order_id.desc())


def range_currencies(db, date_from: date, date_to: date) -> list[str]:
    """区间内动态币种选项（升序去重，AC-O2）。"""
    rows = db.execute(
        select(Order.currency_type)
        .where(Order.create_date >= date_from, Order.create_date <= date_to)
        .distinct()
        .order_by(Order.currency_type)
    ).scalars()
    return list(rows)


def range_upstreams(db, date_from: date, date_to: date) -> list[str]:
    """区间内动态上游选项（升序去重，REQ-20261022-02 §1.4 筛选框选项）。"""
    rows = db.execute(
        select(Order.upstream_code)
        .where(Order.create_date >= date_from, Order.create_date <= date_to)
        .distinct()
        .order_by(Order.upstream_code)
    ).scalars()
    return list(rows)


def paginate(total: int, page: int) -> tuple[int, int]:
    """(pages, 安全页码)：pages = max(1, ceil(total/25))；越界页原样返回空页。"""
    pages = max(1, -(-total // TABLE_PAGE_SIZE))
    return pages, max(1, page)
