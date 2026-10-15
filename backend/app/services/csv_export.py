"""CSV 导出（DESIGN-20261012-02 §5.4；class 列填值 REQ-20261014-01）。

流式生成（yield_per 服务端游标 + 分块拼接），行为逐条对齐 HTML
ordersToCsv()/csvCell()/downloadCsv()：
- UTF-8 **BOM** 首块（Excel 不乱码）；**CRLF** 行连接、无行尾 CRLF；
- 14 列表头 en/zh 逐字冻结（HTML csvHeaders，不得改动）；
- class 列填已计入/被剔除（REQ-20261014-01）；revShare/earningsUsd 两列空
  （旧 20%/70% 口径死列，新口径 per-order 分成未定义，宁空勿造）；
  文件名 orders_all_{from}_to_{to}.csv（两档同名，AC-X2，§4.6-4）；
- 防公式注入：值以 ``= + - @ \\t \\r`` 开头前置 ``'``；含 ``",\\n\\r``
  引号包裹并双写内部引号（HTML csvCell 逐条移植）；
- country：babel CLDR 按 lang 本地化（未知 → Unknown/未知，无条目回退原 key）；
- status：冻结小词表 Completed/Returned ↔ 已完成/已退款。
"""

import re
from collections.abc import Iterator
from datetime import date
from typing import Any

from babel import Locale

from app.models import Order
from app.schemas.dashboard import ClassFilter
from app.services.aggregation import UNKNOWN_COUNTRY_KEY, country_key
from app.services.money import money_str
from app.services.orders_query import apply_sort, orders_query

#: 14 列表头（HTML:556-558 / 634-636，逐字冻结）
CSV_HEADERS: dict[str, list[str]] = {
    "en": [
        "orderId", "createTime", "theaterId", "chapterId", "country", "language",
        "currency", "amount", "estUsd", "class", "revShare", "earningsUsd",
        "status", "promotionCode",
    ],
    "zh": [
        "订单编号", "创建时间", "短剧ID", "章节ID", "国家/地区", "语种",
        "币种", "金额", "预估美元", "类别", "分成比例", "分成收入(美元)",
        "状态", "推广码",
    ],
}

#: 状态冻结词表（HTML:533 / 611）
STATUS_WORDS: dict[str, dict[str, str]] = {
    "en": {"completed": "Completed", "returned": "Returned"},
    "zh": {"completed": "已完成", "returned": "已退款"},
}

#: 类别冻结词表（REQ-20261014-01；回填后 tag 恒有值，NULL 防御输出空串）
CLASS_WORDS: dict[str, dict[str, str]] = {
    "en": {"included": "Included", "excluded": "Excluded"},
    "zh": {"included": "已计入", "excluded": "被剔除"},
}

#: 未知国家文案（HTML unknownCountry）
UNKNOWN_COUNTRY_LABEL: dict[str, str] = {"en": "Unknown", "zh": "未知"}

#: CLDR territory 显示名（key = 两位国家码）
_TERRITORIES: dict[str, dict[str, str]] = {
    "en": Locale("en").territories,
    "zh": Locale("zh").territories,
}

#: 公式注入防护：首字符 ∈ {=, +, -, @, \t, \r}（HTML csvCell）
_INJECTION_RE = re.compile(r"^[=+\-@\t\r]")

#: 引号包裹触发：任意位置含 " , \n \r（HTML csvCell）
_QUOTE_RE = re.compile(r'[",\n\r]')

#: 流式分块行数（yield_per 之外再按行拼块，兼顾游标与响应粒度）
_CHUNK_ROWS = 500

#: yield_per 服务端游标批量（行）
_YIELD_PER = 1000


def csv_cell(value: Any) -> str:
    """单格编码（HTML csvCell 逐条移植）：注入前缀防护 + 引号双写。"""
    text = "" if value is None else str(value)
    safe = f"'{text}" if _INJECTION_RE.match(text) else text
    if _QUOTE_RE.search(safe):
        return f'"{safe.replace(chr(34), chr(34) * 2)}"'
    return safe


def country_display(key: str, lang: str) -> str:
    """country_key → 本地化国名（babel CLDR；未知/无条目回退原 key）。"""
    if key == UNKNOWN_COUNTRY_KEY:
        return UNKNOWN_COUNTRY_LABEL[lang]
    territories = _TERRITORIES.get(lang) or {}
    return territories.get(key, key)


def _row_values(order: Order, lang: str) -> list[str]:
    """一行 14 列原始值（class 列填值；revShare/earningsUsd 空列，REQ-20261014-01）。"""
    status = "returned" if order.is_returned else "completed"
    class_word = CLASS_WORDS[lang].get(order.order_class or "", "")
    return [
        order.order_id or "",
        order.create_time or "",
        order.theater_id or "",
        order.chapter_id or "",
        country_display(country_key(order.language), lang),
        order.language or "",
        order.currency_type or "",
        money_str(order.amount_minor),
        (
            money_str(order.usd_order_amount_minor)
            if order.usd_order_amount_minor is not None
            else ""
        ),
        class_word,
        "",  # revShare —— 旧口径死列（宁空勿造）
        "",  # earningsUsd —— 旧口径死列（宁空勿造）
        STATUS_WORDS[lang][status],
        order.promotion_code or "",
    ]


def csv_filename(date_from: date, date_to: date) -> str:
    """两档同名：orders_all_{from}_to_{to}.csv（AC-X2，§4.6-4）。"""
    return f"orders_all_{date_from.isoformat()}_to_{date_to.isoformat()}.csv"


#: 客户视图 CSV 表头（7 列 = 客户视图表格可见列，REQ-20261015-02）
CUSTOMER_CSV_HEADERS: dict[str, list[str]] = {
    "en": ["orderId", "createTime", "country", "currency", "amount", "estUsd", "status"],
    "zh": ["订单编号", "创建时间", "国家/地区", "币种", "金额", "预估美元", "状态"],
}


def _customer_row_values(order: Order, lang: str) -> list[str]:
    """客户视图一行 7 列：纯订单信息，不含 order_class 等任何分类字段（红线 §9-12）。"""
    status = "returned" if order.is_returned else "completed"
    return [
        order.order_id or "",
        order.create_time or "",
        country_display(country_key(order.language), lang),
        order.currency_type or "",
        money_str(order.amount_minor),
        (
            money_str(order.usd_order_amount_minor)
            if order.usd_order_amount_minor is not None
            else ""
        ),
        STATUS_WORDS[lang][status],
    ]


def customer_csv_filename(date_from: date, date_to: date) -> str:
    """customer_orders_{from}_to_{to}.csv（当前筛选全量行，不分页）。"""
    return f"customer_orders_{date_from.isoformat()}_to_{date_to.isoformat()}.csv"


def iter_customer_csv_chunks(
    db,
    date_from: date,
    date_to: date,
    *,
    currency: str = "all",
    status: str = "all",
    sort: str = "date",
    direction: str = "desc",
    lang: str = "en",
) -> Iterator[str]:
    """客户视图 CSV：与 /customer-orders 同参同序，导出当前筛选**全部行**（跨页）。

    included-only（order_class 固定 included）+ 表格级筛选/排序，无分页；
    流式产出（yield_per + 分块拼接），策略同 iter_csv_chunks。
    """
    stmt = apply_sort(
        orders_query(
            date_from,
            date_to,
            currency=currency,
            status=status,  # type: ignore[arg-type]
            order_class="included",
        ),
        sort,  # type: ignore[arg-type]
        direction,  # type: ignore[arg-type]
    )
    result = db.execute(stmt.execution_options(yield_per=_YIELD_PER)).scalars()

    buffer: list[str] = ["\ufeff" + ",".join(csv_cell(h) for h in CUSTOMER_CSV_HEADERS[lang])]
    for order in result:
        buffer.append(",".join(csv_cell(v) for v in _customer_row_values(order, lang)))
        if len(buffer) > _CHUNK_ROWS:
            yield "\r\n".join(buffer)
            buffer = []
    if buffer:
        yield "\r\n".join(buffer)


def iter_csv_chunks(
    db,
    date_from: date,
    date_to: date,
    *,
    scope: str = "view",
    currency: str = "all",
    status: str = "all",
    order_class: ClassFilter = "all",
    sort: str = "date",
    direction: str = "desc",
    lang: str = "en",
) -> Iterator[str]:
    """流式产出 CSV 文本块（BOM 首块；CRLF 连接；无行尾 CRLF）。

    scope=view 套用表格筛选+排序；scope=all 区间全量、忽略筛选、
    create_time desc 固定序（AC-X1）。
    """
    if scope == "all":
        # 数据集 class 仍是外层范围（REQ §3.4：CSV 两档都只含当前数据集）；
        # scope=all 只忽略表格级筛选（币种/状态/排序），create_time desc 固定序
        stmt = apply_sort(
            orders_query(date_from, date_to, order_class=order_class), "date", "desc"
        )
    else:
        stmt = apply_sort(
            orders_query(
                date_from,
                date_to,
                currency=currency,
                status=status,  # type: ignore[arg-type]
                order_class=order_class,
            ),
            sort,  # type: ignore[arg-type]
            direction,  # type: ignore[arg-type]
        )
    result = db.execute(stmt.execution_options(yield_per=_YIELD_PER)).scalars()

    buffer: list[str] = ["\ufeff" + ",".join(csv_cell(h) for h in CSV_HEADERS[lang])]
    for order in result:
        buffer.append(",".join(csv_cell(v) for v in _row_values(order, lang)))
        if len(buffer) > _CHUNK_ROWS:
            yield "\r\n".join(buffer)
            buffer = []
    if buffer:
        yield "\r\n".join(buffer)
