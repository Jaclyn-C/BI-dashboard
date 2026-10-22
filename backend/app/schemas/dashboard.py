"""看板入出参契约（DESIGN-20261012-02 §5；KPI 口径 REQ-20261014-01）。

§5 是前后端并行的唯一真源：字段名、形状、金额字符串口径（主单位 2 位小数，
DESIGN §2.5）以此为准。KPI 新口径：金额卡基数 = 上游自报美元、退款单照常
参与；数据集切换（summary/orders 的 class 参数）下不适用卡片的值为 null
（前端不渲染该卡）。
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: 时间范围跨度上限（HTML CONFIG.MAX_RANGE_DAYS；from/to 校验与手动钳制共用）
MAX_RANGE_DAYS = 92

#: 订单表页大小（AC-O4，不开放参数）
TABLE_PAGE_SIZE = 25

SortKey = Literal["date", "currency", "amount", "usd"]
SortDir = Literal["asc", "desc"]
StatusFilter = Literal["all", "completed", "returned"]
ClassFilter = Literal["all", "included", "excluded"]
CsvScope = Literal["view", "all"]
CsvLang = Literal["en", "zh"]


class RangeOut(BaseModel):
    """响应顶层的区间回显（from 为 Python 关键字，用别名序列化）。"""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    from_: date = Field(alias="from")
    to: date


class SummaryMeta(BaseModel):
    orders_total: int
    latest_orders_sync_at: str | None
    sync_status: Literal["ok", "failed", "running", "never"]
    latest_covered_date: str | None
    incomplete_tail: bool
    truncated_days: list[str]
    ad_available: bool
    ad_error: str | None


class ClassCountAmount(BaseModel):
    """合并卡的半边：某类订单的数量与原金额（USD）合计。"""

    count: int
    usd: str


class KpisOut(BaseModel):
    """REQ-20261014-01 新口径 KPI（金额=上游自报美元主单位字符串；退款单参与）。

    数据集切换（summary?class=）下不适用卡片的值为 None（前端不渲染）：
    included 视图 → supplier_payable/hidden_saving/net_expected/included/excluded
    为 None；excluded 视图再增 supplier_paid/net_actual 为 None。
    """

    orders_total: int
    orders_completed: int
    orders_returned: int
    total_usd: str
    my_share_usd: str
    supplier_payable_usd: str | None
    supplier_paid_usd: str | None
    hidden_saving_usd: str | None
    net_expected_usd: str | None
    net_actual_usd: str | None
    total_net_actual_usd: str | None  # 总实际净利润 = 实际净利润 + 广告收入
    refunded_usd: str
    included: ClassCountAmount | None
    excluded: ClassCountAmount | None
    ad_total: str
    ad_days_reported: int
    countries: int
    top_country: str | None
    no_usd_order_count: int


class CurrencyAmount(BaseModel):
    """按币种金额对（daily 为该口径美元额；countries 为原币金额，§5.2-③）。"""

    currency: str
    amount: str


class SeriesAmount(BaseModel):
    """图表预折叠序列（前 6 + __other，后端求和，前端零金额运算）。"""

    key: str
    amount: str


class DailyEntry(BaseModel):
    date: str
    orders: int
    total: str
    by_currency: list[CurrencyAmount]
    series: list[SeriesAmount]


class AdEntry(BaseModel):
    date: str
    amount: str


class DailyOut(BaseModel):
    days: list[str]
    currency_rank: list[str]
    est: list[DailyEntry]
    usd: list[DailyEntry]
    ad: list[AdEntry]


class ConvRow(BaseModel):
    currency: str
    orders: int
    native: str
    server_usd: str


class ConvSlice(BaseModel):
    key: str
    server_usd: str


class ConvOut(BaseModel):
    empty: bool
    rows: list[ConvRow]
    slices: list[ConvSlice]
    #: 旧固定汇率口径合计：卡片不再展示，仅供每日「估算」卡 aria total 引用（AC-V4）
    legacy_total: str
    server_total: str
    no_usd_order_count: int
    no_usd_currencies: list[str]


class CountryRow(BaseModel):
    key: str  # 区域码 / 原语种串 / __unknown（m12 哨兵）
    usd: str
    orders: int
    share: str | None
    by_currency: list[CurrencyAmount]


class CountriesOut(BaseModel):
    table: list[CountryRow]
    bars: list[CountryRow]


class SummaryResponse(BaseModel):
    range: RangeOut
    meta: SummaryMeta
    kpis: KpisOut
    daily: DailyOut
    conv: ConvOut
    countries: CountriesOut


class OrderRow(BaseModel):
    order_id: str
    upstream: str  # 订单归属上游 code（REQ-20261022-02 §1.4），如 'netshort'
    create_time: str  # 上游原值（表头标注 UTC，AC-S8）
    create_date: str
    country_key: str
    language: str | None
    currency: str
    amount: str
    usd: str | None  # 缺失 → null（前端渲染 —）
    order_class: str | None = None  # tag 真值（REQ-20261014-01）；NULL 仅存量未回填防御
    status: Literal["completed", "returned"]


class OrdersResponse(BaseModel):
    rows: list[OrderRow]
    page: int
    page_size: int
    pages: int
    total: int
    total_in_range: int
    currencies: list[str]


class CustomerOrderRow(BaseModel):
    """客户视图行（REQ-20261015-02）：纯订单信息，不含 order_class 等任何内部分类字段。

    upstream（REQ-20261022-02 §1.4）：订单归属上游 code，属订单自身信息、
    非内部分类，客户可见（用户定稿）。
    """

    order_id: str
    upstream: str
    create_time: str
    country_key: str
    language: str | None
    currency: str
    amount: str
    usd: str | None
    status: Literal["completed", "returned"]


class CustomerOrdersResponse(BaseModel):
    rows: list[CustomerOrderRow]
    page: int
    page_size: int
    pages: int
    total: int
    total_in_range: int
    currencies: list[str]


class SyncRequest(BaseModel):
    """POST /dashboard/sync 入参（当前视图区间；服务端按 §3.3.2 钳制）。"""

    model_config = ConfigDict(populate_by_name=True)

    date_from: date = Field(alias="from")
    date_to: date = Field(alias="to")


class SyncCurrent(BaseModel):
    id: int
    trigger: str
    window_start: str
    window_end: str
    days_done: int
    days_total: int
    phase: str


class SyncLastRun(BaseModel):
    id: int
    trigger: str
    window_start: str
    window_end: str
    status: str
    started_at: str | None
    finished_at: str | None
    truncated_days: list[str]
    orders_upserted: int
    orders_error: str | None
    ad_error: str | None


class SyncStatusResponse(BaseModel):
    state: Literal["running", "idle"]
    current: SyncCurrent | None
    last_run: SyncLastRun | None


class SyncAcceptedResponse(BaseModel):
    accepted: bool
    status: SyncStatusResponse
