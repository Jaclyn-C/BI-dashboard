"""CSV 导出（DESIGN-20261012-02 §5.4；REQ AC-X1–X4）。

流式生成（yield_per 服务端游标 + 分块拼接），行为逐条对齐 HTML
ordersToCsv()/csvCell()/downloadCsv()：
- UTF-8 **BOM** 首块（Excel 不乱码）；**CRLF** 行连接、无行尾 CRLF；
- 14 列表头 en/zh 逐字冻结（HTML csvHeaders，不得改动）；
- B1：class/revShare/earningsUsd 三列空值（AC-X3）；dataset 恒 all →
  文件名 orders_all_{from}_to_{to}.csv（两档同名，AC-X2，§4.6-4）；
- 防公式注入：值以 ``= + - @ \\t \\r`` 开头前置 ``'``；含 ``",\\n\\r``
  引号包裹并双写内部引号（HTML csvCell 逐条移植）；
- country：babel CLDR 按 lang 本地化（未知 → Unknown/未知，无条目回退原 key）；
- status：冻结小词表 Completed/Returned ↔ 已完成/已退款。

⚠️ 本模块禁止 import share_service（B1 红线，B-T4/B-T9 grep 断言）。
"""

import re
from collections.abc import Iterator
from datetime import date
from typing import Any

from babel import Locale

from app.models import Order
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
    """一行 14 列原始值（class/revShare/earningsUsd 三列空，AC-X3）。"""
    status = "returned" if order.is_returned else "completed"
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
        "",  # class —— B1 空列（规则未确认，宁空勿猜）
        "",  # revShare —— B1 空列
        "",  # earningsUsd —— B1 空列
        STATUS_WORDS[lang][status],
        order.promotion_code or "",
    ]


def csv_filename(date_from: date, date_to: date) -> str:
    """两档同名：orders_all_{from}_to_{to}.csv（AC-X2，§4.6-4）。"""
    return f"orders_all_{date_from.isoformat()}_to_{date_to.isoformat()}.csv"


def iter_csv_chunks(
    db,
    date_from: date,
    date_to: date,
    *,
    scope: str = "view",
    currency: str = "all",
    status: str = "all",
    sort: str = "date",
    direction: str = "desc",
    lang: str = "en",
) -> Iterator[str]:
    """流式产出 CSV 文本块（BOM 首块；CRLF 连接；无行尾 CRLF）。

    scope=view 套用表格筛选+排序；scope=all 区间全量、忽略筛选、
    create_time desc 固定序（AC-X1）。
    """
    if scope == "all":
        stmt = apply_sort(orders_query(date_from, date_to), "date", "desc")
    else:
        stmt = apply_sort(
            orders_query(date_from, date_to, currency=currency, status=status),
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
