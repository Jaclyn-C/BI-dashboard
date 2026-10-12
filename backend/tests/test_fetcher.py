"""窗口化拉取与时间窗二分单测（MockTransport；REQ AC-U2/U4）。

覆盖：非整页直返、整页二分补全（不丢行）、深度 6 封顶 → truncated、
最小窗口 120s 封顶 → truncated、adSummary 解析（×100 / 双键日聚合 /
坏行跳过 / 请求体形状）。
"""

import json
import threading
from datetime import date, datetime
from decimal import Decimal

import httpx

from app.config import Settings
from app.upstream.client import PATH_AD_SUMMARY, PATH_ORDER_LIST, UpstreamClient
from app.upstream.fetcher import fetch_ad_summary, fetch_day, fetch_window


def make_settings(**overrides) -> Settings:
    base = {"upstream_client_id": "id", "upstream_client_secret": "secret"}
    base.update(overrides)
    return Settings(**base)


class FakeOrdersUpstream:
    """假上游：按请求窗口从固定订单集（时间戳字符串）取交集、截断到 pageSize。"""

    def __init__(self, orders: list[tuple[str, str]]) -> None:
        #: (createTime, orderId) 列表
        self.orders = sorted(orders)
        self.requests: list[dict] = []
        self.lock = threading.Lock()

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(PATH_ORDER_LIST):
            body = json.loads(request.content.decode())
            with self.lock:
                self.requests.append(body)
            rows = [
                {"orderId": oid, "createTime": stamp}
                for stamp, oid in self.orders
                if body["startDate"] <= stamp <= body["endDate"]
            ][: body["pageSize"]]
            return httpx.Response(
                200, json={"code": 200, "msg": "ok", "data": {"list": rows}}
            )
        if path.endswith(PATH_AD_SUMMARY):
            return httpx.Response(200, json={"code": 200, "msg": "ok", "data": {"list": []}})
        return httpx.Response(
                200, json={"code": 200, "data": {"accessToken": "t", "expiresIn": 3600}}
            )

    def client(self) -> UpstreamClient:
        return UpstreamClient(transport=self.transport, settings=make_settings())


def test_fetch_window_partial_page_returns_directly():
    """行数 < pageSize：非截断，单请求直返（AC-U2）。"""
    fake = FakeOrdersUpstream(
        [
            ("2026-10-01 01:00:00", "A"),
            ("2026-10-01 05:00:00", "B"),
            ("2026-10-02 09:00:00", "C"),
        ],
    )
    with fake.client() as client:
        result = fetch_window(
            client,
            datetime(2026, 10, 1, 0, 0, 0),
            datetime(2026, 10, 2, 23, 59, 59),
        )
    assert [row["orderId"] for row in result.rows] == ["A", "B", "C"]
    assert result.truncated is False
    assert len(fake.requests) == 1


def test_fetch_window_bisects_and_collects_all_rows():
    """整页 → 二分补全：所有行恰好各取一次，无截断（HTML:968-983 语义）。"""
    fake = FakeOrdersUpstream(
        [
            ("2026-10-01 01:00:00", "A"),
            ("2026-10-01 02:00:00", "B"),
            ("2026-10-01 03:00:00", "C"),
            ("2026-10-01 04:00:00", "D"),  # 以上 4 行构成一整页（pageSize=4）
            ("2026-10-01 10:00:00", "E"),
            ("2026-10-01 20:00:00", "F"),
        ],
    )
    with fake.client() as client:
        result = fetch_day(client, date(2026, 10, 1), settings=make_settings(upstream_page_size=4))
    assert sorted(row["orderId"] for row in result.rows) == ["A", "B", "C", "D", "E", "F"]
    assert result.truncated is False
    # 首个请求就是全天窗口
    first = fake.requests[0]
    assert first["startDate"] == "2026-10-01 00:00:00"
    assert first["endDate"] == "2026-10-01 23:59:59"
    assert first["page"] == 1 and first["pageSize"] == 4


def test_fetch_window_depth_cap_marks_truncated():
    """深度 6 封顶：窗口内持续整页 → truncated=True 且仍返回已取行（AC-U2）。"""
    # 4 行挤在 40 秒内（pageSize=4）：二分到深度上限仍整页
    fake = FakeOrdersUpstream(
        [
            ("2026-10-01 00:00:10", "A"),
            ("2026-10-01 00:00:20", "B"),
            ("2026-10-01 00:00:30", "C"),
            ("2026-10-01 00:00:40", "D"),
        ],
    )
    with fake.client() as client:
        result = fetch_day(client, date(2026, 10, 1), settings=make_settings(upstream_page_size=4))
    assert result.truncated is True
    assert sorted(row["orderId"] for row in result.rows) == ["A", "B", "C", "D"]


def test_fetch_window_min_window_cap_marks_truncated():
    """最小窗口 120s 封顶：放宽深度后仍以窗口下界判 truncated（D10）。"""
    fake = FakeOrdersUpstream(
        [
            ("2026-10-01 00:00:10", "A"),
            ("2026-10-01 00:00:20", "B"),
            ("2026-10-01 00:00:30", "C"),
            ("2026-10-01 00:00:40", "D"),
        ],
    )
    settings = make_settings(
        upstream_page_size=4, upstream_max_split_depth=20, upstream_min_split_window_seconds=120
    )
    with fake.client() as client:
        result = fetch_window(
            client,
            datetime(2026, 10, 1, 0, 0, 0),
            datetime(2026, 10, 1, 23, 59, 59),
            settings=settings,
        )
    assert result.truncated is True
    assert sorted(row["orderId"] for row in result.rows) == ["A", "B", "C", "D"]


# ---------- adSummary ----------


class FakeAdUpstream:
    """假上游：按请求日供给 adSummary 行；可对指定日返回 500（逐日语义）。"""

    def __init__(
        self,
        day_rows: dict[str, list[dict]] | None = None,
        *,
        fail_days: set[str] = frozenset(),
    ) -> None:
        self.day_rows = day_rows or {}
        self.fail_days = fail_days
        self.requests: list[dict] = []

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(PATH_AD_SUMMARY):
            body = json.loads(request.content.decode())
            self.requests.append(body)
            day = body["startDate"][:10]
            if day in self.fail_days:
                return httpx.Response(500, json={})
            return httpx.Response(
                200,
                json={"code": 200, "msg": "ok", "data": {"list": self.day_rows.get(day, [])}},
            )
        return httpx.Response(
            200, json={"code": 200, "data": {"accessToken": "t", "expiresIn": 3600}}
        )

    def client(self) -> UpstreamClient:
        return UpstreamClient(transport=self.transport, settings=make_settings())


def test_fetch_ad_summary_splits_range_into_daily_requests():
    """防回归：上游限制单次查询区间 ≤ 1 天（2026-10-12 冒烟发现）→ 逐日拆分。"""
    fake = FakeAdUpstream(
        {
            "2026-10-01": [{"date": "2026-10-01 00:00:00", "ad_revenue_dollars": "1.00"}],
            "2026-10-03": [{"date": "2026-10-03 00:00:00", "ad_revenue_dollars": "2.00"}],
        }
    )
    with fake.client() as client:
        result = fetch_ad_summary(client, date(2026, 10, 1), date(2026, 10, 3))
    # 3 天区间 = 恰好 3 个请求，每个都是当日 [00:00:00, 23:59:59] 窗口
    assert len(fake.requests) == 3
    for body in fake.requests:
        day = body["startDate"][:10]
        assert body["startDate"] == f"{day} 00:00:00"
        assert body["endDate"] == f"{day} 23:59:59"
        assert body["page"] == 1 and "pageSize" in body
    assert [body["startDate"][:10] for body in fake.requests] == [
        "2026-10-01", "2026-10-02", "2026-10-03"
    ]
    assert result.failed_days == []
    assert result.summary == {
        date(2026, 10, 1): Decimal("100"),
        date(2026, 10, 3): Decimal("200"),
    }


def test_fetch_ad_summary_parses_dollars_to_minor():
    """美元 → 最小单位（×100）；同日多行求和；坏行（缺日期/坏数值）跳过。"""
    fake = FakeAdUpstream(
        {
            "2026-10-01": [
                {"date": "2026-10-01 00:00:00", "ad_revenue_dollars": "123.4567"},
                {"date": "2026-10-01 12:00:00", "ad_revenue_dollars": "1.5433"},
            ],
            "2026-10-03": [
                {"date": "2026-10-03 00:00:00", "ad_revenue_dollars": "0.01"},
                {"date": "", "ad_revenue_dollars": "9.99"},
                {"date": "garbage", "ad_revenue_dollars": "9.99"},
                {"date": "2026-10-04 00:00:00", "wrongKey": "1.00"},  # 键名不符 → 跳过
                {"date": "2026-10-05 00:00:00"},
                "not-a-dict",
            ],
        }
    )
    with fake.client() as client:
        result = fetch_ad_summary(client, date(2026, 10, 1), date(2026, 10, 3))
    assert result.summary == {
        date(2026, 10, 1): Decimal("125.00") * 100,
        date(2026, 10, 3): Decimal("1"),
    }
    assert result.failed_days == []


def test_fetch_ad_summary_single_day_failure_isolates():
    """单日失败：记入 failed_days、其余日照常返回（不中断整轮）。"""
    fake = FakeAdUpstream(
        {
            "2026-10-01": [{"date": "2026-10-01 00:00:00", "ad_revenue_dollars": "1.00"}],
            "2026-10-03": [{"date": "2026-10-03 00:00:00", "ad_revenue_dollars": "3.00"}],
        },
        fail_days={"2026-10-02"},
    )
    with fake.client() as client:
        result = fetch_ad_summary(client, date(2026, 10, 1), date(2026, 10, 3))
    assert result.failed_days == [date(2026, 10, 2)]
    assert set(result.summary) == {date(2026, 10, 1), date(2026, 10, 3)}


def test_fetch_ad_summary_empty_list():
    fake = FakeAdUpstream({})
    with fake.client() as client:
        result = fetch_ad_summary(client, date(2026, 10, 1), date(2026, 10, 2))
    assert result.summary == {} and result.failed_days == []


def test_fetch_day_window_bounds():
    """日窗口 = [00:00:00, 23:59:59]（秒级端点含当日全天）。"""
    fake = FakeOrdersUpstream([("2026-10-01 23:59:59", "LATE")])
    with fake.client() as client:
        result = fetch_day(client, date(2026, 10, 1), settings=make_settings())
    assert [row["orderId"] for row in result.rows] == ["LATE"]
