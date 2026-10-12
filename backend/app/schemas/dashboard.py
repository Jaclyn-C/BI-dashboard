"""看板入出参契约（DESIGN-20261012-02 §5，REQ-20261012-02）。

§5 是前后端并行的唯一真源：字段名、形状、金额字符串口径（主单位 2 位小数，
DESIGN §2.5）以此为准。B1 降级契约（§4.3）：分成相关键保留、值 null。
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


class Degraded(BaseModel):
    """B1 降级顶层标志（规则接入后置 false 并最终移除，§5.7）。"""

    share_rules_pending: bool = True


class KpisOut(BaseModel):
    total_revenue: str  # B1：毛额口径 = orders_gross_usd + ad_total（AC-K1）
    orders_gross_usd: str
    ad_total: str
    included_revenue: str | None = None  # B1 恒 null（AC-K2）
    excluded_revenue: str | None = None  # B1 恒 null（AC-K3）
    gross_usd: str  # AC-K5（B1 与 orders_gross_usd 同值）
    orders_completed: int
    orders_returned: int
    countries: int
    top_country: str | None
    ad_days_reported: int


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
    has_rate: bool
    rate: str | None
    orders: int
    native: str
    legacy_usd: str
    server_usd: str
    delta: str
    delta_pct: str | None
    flagged: bool


class ConvSlice(BaseModel):
    key: str
    legacy_usd: str
    server_usd: str


class ConvOut(BaseModel):
    empty: bool
    rows: list[ConvRow]
    slices: list[ConvSlice]
    legacy_total: str
    server_total: str
    delta_total: str
    delta_pct: str | None
    agree: bool
    no_rate_currencies: list[str]
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
    degraded: Degraded
    kpis: KpisOut
    daily: DailyOut
    conv: ConvOut
    countries: CountriesOut


class OrderRow(BaseModel):
    order_id: str
    create_time: str  # 上游原值（表头标注 UTC，AC-S8）
    create_date: str
    country_key: str
    language: str | None
    currency: str
    amount: str
    usd: str | None  # 缺失 → null（前端渲染 —）
    order_class: str | None = None  # B1 恒 null（AC-O1）
    status: Literal["completed", "returned"]


class OrdersResponse(BaseModel):
    rows: list[OrderRow]
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
