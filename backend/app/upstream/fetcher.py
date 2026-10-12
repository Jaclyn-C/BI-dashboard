"""窗口化拉取与时间窗二分补全（DESIGN-20261012-02 §3.2，REQ AC-U2/U4）。

逐条移植 HTML:946-1036 语义到服务端：
- fetch_day：按日窗口（00:00:00 – 23:59:59，秒级端点）拉订单；
- fetch_window：返回行数 == 请求 pageSize 即判定可能截断（上游无 hasMore），
  时间窗二分（最大深度 6、最小窗口 120 秒，配置化 D10）；二分到底仍整页 →
  truncated=True（归属到当天记入 sync_runs.truncated_dates，AC-S7）；
- fetch_ad_summary：逐日调用 /open/order/adSummary（上游限制单次查询区间
  ≤ 1 天——2026-10-12 真实冒烟发现「查询时间范围不能超过1天」，D11 的
  「单请求拉全区间」设想作废），行内 date[:10] 为日、ad_revenue_dollars
  （美元单位）×100 入最小单位；单日失败记入 failed_days 不中断（AC-S9）。

窗口运算用 naive datetime（不引时区，D6）；窗口时间戳格式 `YYYY-MM-DD HH:mm:ss`
（HTML apiStamp 同款）。
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from app.config import Settings, get_settings
from app.upstream.client import PATH_AD_SUMMARY, PATH_ORDER_LIST, UpstreamClient, UpstreamError

logger = logging.getLogger("app.upstream")

#: 图表/表格共用的窗口时间戳格式（HTML apiStamp）
_STAMP_FMT = "%Y-%m-%d %H:%M:%S"


def api_stamp(moment: datetime) -> str:
    """datetime → 上游窗口时间戳字符串（HTML apiStamp 移植）。"""
    return moment.strftime(_STAMP_FMT)


def _parse_decimal(value: object) -> Decimal | None:
    """防御式数值解析（§8.1 风险表：字段契约缺失，坏值返回 None）。"""
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed


class FetchResult:
    """一个日窗的拉取结果：订单原始行 + 是否仍有截断。"""

    def __init__(self, rows: list[dict], truncated: bool) -> None:
        self.rows = rows
        self.truncated = truncated


def fetch_window(
    client: UpstreamClient,
    start: datetime,
    end: datetime,
    *,
    depth: int = 0,
    settings: Settings | None = None,
) -> FetchResult:
    """拉取 [start, end] 窗口订单；整页返回则二分补全（HTML:968-983）。"""
    cfg = settings or get_settings()
    payload = client.post(
        PATH_ORDER_LIST,
        {"startDate": api_stamp(start), "endDate": api_stamp(end), "page": 1,
         "pageSize": cfg.upstream_page_size},
    )
    data = payload.get("data") or {}
    rows = data.get("list") if isinstance(data, dict) else None
    rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    if len(rows) < cfg.upstream_page_size:
        return FetchResult(rows, truncated=False)
    if depth >= cfg.upstream_max_split_depth or (
        end - start
    ) < timedelta(seconds=cfg.upstream_min_split_window_seconds):
        return FetchResult(rows, truncated=True)

    # mid = floor((start+end)/2) 向下取整到秒（HTML: floor(…/2000)*1000）
    mid = start + timedelta(seconds=int((end - start).total_seconds() // 2))
    first = fetch_window(client, start, mid, depth=depth + 1, settings=cfg)
    second = fetch_window(client, mid + timedelta(seconds=1), end, depth=depth + 1, settings=cfg)
    return FetchResult(
        first.rows + second.rows, truncated=first.truncated or second.truncated
    )


def fetch_day(
    client: UpstreamClient, day: date, *, settings: Settings | None = None
) -> FetchResult:
    """拉取单个自然日（UTC 日界，即数据日界）的全部订单。"""
    start = datetime(day.year, day.month, day.day, 0, 0, 0)
    end = datetime(day.year, day.month, day.day, 23, 59, 59)
    return fetch_window(client, start, end, settings=settings)


def fetch_ad_summary_day(
    client: UpstreamClient, day: date, *, settings: Settings | None = None
) -> dict[date, Decimal]:
    """拉单日广告收益（窗口 = 当日 00:00:00 – 23:59:59，与订单日窗同语义）。

    返回 {日: 美元最小单位}；ad_revenue_dollars 为美元单位，×100 入 minor
    （HTML:1028-1032 同口径）。行数超过页大小时记 warning（不应发生）。
    """
    cfg = settings or get_settings()
    payload = client.post(
        PATH_AD_SUMMARY,
        {
            "startDate": api_stamp(datetime(day.year, day.month, day.day)),
            "endDate": api_stamp(datetime(day.year, day.month, day.day, 23, 59, 59)),
            "page": 1,
            "pageSize": cfg.upstream_page_size,
        },
    )
    data = payload.get("data") or {}
    rows = data.get("list") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return {}
    if len(rows) >= cfg.upstream_page_size:
        logger.warning("adSummary returned a full page (%d rows) — possible truncation", len(rows))

    summary: dict[date, Decimal] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        day_raw = str(row.get("date") or "")[:10]
        dollars = _parse_decimal(row.get("ad_revenue_dollars"))
        if not day_raw or dollars is None:
            continue
        try:
            row_day = date.fromisoformat(day_raw)
        except ValueError:
            continue
        summary[row_day] = summary.get(row_day, Decimal("0")) + dollars * 100
    return summary


class AdSummaryResult:
    """区间广告拉取结果：成功日聚合 + 失败日清单（逐日请求）。"""

    def __init__(self, summary: dict[date, Decimal], failed_days: list[date]) -> None:
        self.summary = summary
        self.failed_days = failed_days


def fetch_ad_summary(
    client: UpstreamClient, date_from: date, date_to: date, *, settings: Settings | None = None
) -> AdSummaryResult:
    """逐日拉取广告收益（顺序请求，不与订单拉取的线程池混用并发语义）。

    上游限制单次查询区间 ≤ 1 天（2026-10-12 真实冒烟发现），故按日拆分：
    92 天回填 = 92 个请求、3 天滚动 = 3 个。单日 UpstreamError 只记入
    failed_days 并继续（成功日照常聚合返回），由调用方把失败日翻译成
    ad_error / partial（AC-S9：广告失败不连坐订单；失败日留给下一轮
    lookback 自愈）。
    """
    summary: dict[date, Decimal] = {}
    failed_days: list[date] = []
    day = date_from
    while day <= date_to:
        try:
            summary.update(fetch_ad_summary_day(client, day, settings=settings))
        except UpstreamError as exc:
            logger.warning("adSummary %s failed: %s", day.isoformat(), exc)
            failed_days.append(day)
        day += timedelta(days=1)
    return AdSummaryResult(summary, failed_days)
