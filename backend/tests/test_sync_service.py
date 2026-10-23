"""同步管道集成测试（真实 PostgreSQL 测试库 + MockTransport 假上游）。

覆盖（REQ AC-S3/S4/S7/S8/S9、AC-U3）：规范化映射防御、幂等 upsert、
两阶段独立提交（广告失败不连坐订单）、状态定稿（success/partial/failed）、
截断日期记录、覆盖自愈（首跑等价 92 天回填 D3）、手动区间钳制、
孤儿 running 行清理（m9）、单飞锁。
"""

import json
import threading
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select

from app.config import Settings
from app.models import AdRevenueDaily, Order, SyncRun
from app.services import sync_service
from app.services.classifier import HashClassifier, classify_order_no
from app.services.sync_service import (
    clamp_manual_window,
    normalize_order,
    scheduled_days,
    status_snapshot,
)
from app.upstream.client import PATH_AD_SUMMARY, PATH_ORDER_LIST, PATH_TOKEN, UpstreamClient

TODAY = date(2026, 10, 12)

#: 测试盐值（conftest 同款；黄金向量见 test_classifier_share）
TEST_SALT = "unit-test-salt"
TEST_CLASSIFIER = HashClassifier(
    salt=TEST_SALT, keep_ratio=Decimal("0.8")
)


def make_settings(**overrides) -> Settings:
    base = {
        "upstream_client_id": "id",
        "upstream_client_secret": "secret",
        "sync_lookback_days": 3,
        "sync_backfill_days": 92,
        "order_filter_salt": TEST_SALT,
    }
    base.update(overrides)
    return Settings(**base)


class FakeSyncUpstream:
    """同步管道假上游：按日供给订单行；ad 接口可编程成败。"""

    def __init__(
        self,
        day_rows: dict[str, list[dict]],
        *,
        ad_rows: list[dict] | None = None,
        ad_status: int = 200,
        ad_fail_days: set[str] = frozenset(),
        order_status: int = 200,
        page_size: int = 1000,
    ) -> None:
        self.day_rows = day_rows
        self.ad_rows = ad_rows or []
        self.ad_status = ad_status
        self.ad_fail_days = ad_fail_days
        self.order_status = order_status
        self.page_size = page_size
        self.settings = make_settings(upstream_page_size=page_size)
        self.lock = threading.Lock()
        self.order_requests = 0

    def client(self) -> UpstreamClient:
        return UpstreamClient(transport=self.transport, settings=self.settings)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(PATH_TOKEN):
            return httpx.Response(
                200, json={"code": 200, "data": {"accessToken": "t", "expiresIn": 3600}}
            )
        if path.endswith(PATH_ORDER_LIST):
            with self.lock:
                self.order_requests += 1
            if self.order_status != 200:
                return httpx.Response(self.order_status, json={})
            body = json.loads(request.content.decode())
            rows = self.day_rows.get(body["startDate"][:10], [])
            return httpx.Response(
                200, json={"code": 200, "msg": "ok", "data": {"list": rows[: self.page_size]}}
            )
        if path.endswith(PATH_AD_SUMMARY):
            # 逐日语义（上游限制单次区间 ≤ 1 天）：按请求日过滤行；指定日可失败
            body = json.loads(request.content.decode())
            day = body["startDate"][:10]
            if self.ad_status != 200 or day in self.ad_fail_days:
                return httpx.Response(500, json={})
            rows = [row for row in self.ad_rows if str(row.get("date", ""))[:10] == day]
            return httpx.Response(
                200, json={"code": 200, "msg": "ok", "data": {"list": rows}}
            )
        return httpx.Response(404, json={})


def sample_rows() -> list[dict]:
    return [
        {
            "orderId": "O1",
            "createTime": "2026-10-01 10:00:00",
            "theaterId": "TH1",
            "chapterId": "CH1",
            "language": "es-MX",
            "currencyType": "mxn",
            "amount": "5000",
            "orderAmount": "270",
        },
        {
            "orderId": "O2",
            "createTime": "2026-10-02 11:30:00",
            "theaterId": "TH2",
            "chapterId": "CH2",
            "language": "fr-FR",
            "currencyType": "EUR",
            "amount": "1000",
            "orderAmount": "1100",
            "refundTime": "2026-10-03 09:00:00 ",
            "promotionCode": "promo-1",
        },
    ]


# ---------- 规范化（AC-U3） ----------


def test_normalize_order_mapping():
    o1, o2 = (
        normalize_order(row, TEST_CLASSIFIER) for row in sample_rows()
    )
    assert o1.order_id == "O1"
    assert o1.create_time == "2026-10-01 10:00:00"  # 原值零换算（AC-S8）
    assert o1.create_date == date(2026, 10, 1)
    assert o1.currency_type == "MXN"  # 大小写归一
    assert o1.amount_minor == Decimal("5000")
    assert o1.usd_order_amount_minor == Decimal("270")
    assert o1.is_returned is False
    # 哈希打标（REQ-20261014-01 黄金向量：O1 → included）
    assert o1.order_class == classify_order_no(TEST_SALT, "O1", Decimal("0.8"))
    assert o1.order_class == "included"
    # 退款单：refundTime 非空白 → is_returned；首尾空白剥离；tag 照常计算
    assert o2.refund_time == "2026-10-03 09:00:00"
    assert o2.is_returned is True
    assert o2.promotion_code == "promo-1"


def test_normalize_order_defensive_skips():
    assert normalize_order({"createTime": "2026-10-01 00:00:00"}) is None  # 缺 orderId
    assert normalize_order({"orderId": "X"}) is None  # 缺 createTime
    assert normalize_order(
        {"orderId": "X" * 65, "createTime": "2026-10-01 00:00:00"}
    ) is None  # 超长 id
    assert normalize_order(
        {"orderId": "X", "createTime": "not-a-date"}
    ) is None  # 日期不可解析
    # 坏金额 → 0 兜底入库；坏 usd → None（新口径排除+计数）
    order = normalize_order(
        {"orderId": "Y", "createTime": "2026-10-01 00:00:00", "amount": "abc", "orderAmount": "???"}
    )
    assert order.amount_minor == Decimal("0")
    assert order.usd_order_amount_minor is None


# ---------- upsert 幂等（AC-S3） ----------


def test_upsert_orders_idempotent_rerun(db_session):
    rows = sample_rows()
    orders = [normalize_order(row) for row in rows]
    assert sync_service.upsert_orders(db_session, orders) == 2
    db_session.commit()
    # 重跑同一批（全区间重拉语义）：不产生重复，金额以后写为准
    changed = [normalize_order({**rows[0], "amount": "6000", "orderAmount": "310"})]
    assert sync_service.upsert_orders(db_session, changed) == 1
    db_session.commit()
    stored = {
        o.order_id: o for o in db_session.scalars(select(Order)).all()
    }
    assert set(stored) == {"O1", "O2"}
    assert stored["O1"].amount_minor == Decimal("6000")  # 更新集生效
    assert stored["O1"].usd_order_amount_minor == Decimal("310")
    assert stored["O1"].create_time == "2026-10-01 10:00:00"  # 不可变列不动


def test_upsert_never_overwrites_order_class(db_session):
    """REQ-20261014-01 §3.5：tag 入库算一次、永不改变（更新集不含 order_class）。"""
    rows = sample_rows()
    first = normalize_order(rows[0], TEST_CLASSIFIER)
    sync_service.upsert_orders(db_session, [first])
    db_session.commit()
    original = db_session.scalar(select(Order).where(Order.order_id == "O1"))
    assert original.order_class == "included"  # 黄金向量

    # 换一个「判定结果相反」的分类器重拉同一订单
    flipped_ratio = Decimal("0.01") if first.order_class == "included" else Decimal("0.8")
    flipped = normalize_order(rows[0], HashClassifier(salt=TEST_SALT, keep_ratio=flipped_ratio))
    assert flipped.order_class == "excluded"  # 前置：确实相反
    sync_service.upsert_orders(db_session, [flipped])
    db_session.commit()
    after = db_session.scalar(select(Order).where(Order.order_id == "O1"))
    assert after.amount_minor == first.amount_minor  # 金额列正常 upsert
    assert after.order_class == "included"  # tag 不被覆盖


def test_execute_run_empty_salt_fails_loudly(db_session):
    """空盐：run=failed、零拉取、零写入（宁可失败，不落 NULL tag）。"""
    fake = FakeSyncUpstream({"2026-10-01": sample_rows()})
    settings = make_settings(order_filter_salt="")
    run = sync_service.execute_run(
        "scheduled", [date(2026, 10, 1)], db=db_session, client_factory=fake.client,
        settings=settings,
    )
    assert run.status == "failed"
    assert run.orders_error and "ORDER_FILTER_SALT" in run.orders_error
    assert fake.order_requests == 0  # 未发起任何订单拉取
    assert db_session.scalars(select(Order)).all() == []


# ---------- execute_run 生命周期 ----------


def test_execute_run_success(db_session):
    fake = FakeSyncUpstream(
        {"2026-10-01": sample_rows()[:1], "2026-10-02": sample_rows()[1:]},
        ad_rows=[
            {"date": "2026-10-01 00:00:00", "ad_revenue_dollars": "171.44"},
            {"date": "2026-10-02 00:00:00", "ad_revenue_dollars": "5.00"},
        ],
    )
    run = sync_service.execute_run(
        "manual",
        [date(2026, 10, 1), date(2026, 10, 2)],
        db=db_session,
        client_factory=fake.client,
        settings=fake.settings,
    )
    assert run.status == "success"
    assert run.orders_fetched == 2
    assert run.orders_upserted == 2
    assert run.truncated_dates == []
    assert run.orders_error is None and run.ad_error is None
    assert run.finished_at is not None
    orders = db_session.scalars(select(Order).order_by(Order.order_id)).all()
    assert [o.order_id for o in orders] == ["O1", "O2"]
    assert orders[1].is_returned is True
    ad = {row.date: row.amount_minor for row in db_session.scalars(select(AdRevenueDaily))}
    assert ad == {date(2026, 10, 1): Decimal("17144.00"), date(2026, 10, 2): Decimal("500")}


def test_execute_run_orders_failure_marks_failed(db_session):
    fake = FakeSyncUpstream({}, order_status=500)
    run = sync_service.execute_run(
        "scheduled", [date(2026, 10, 1)], db=db_session, client_factory=fake.client,
        settings=fake.settings,
    )
    assert run.status == "failed"
    assert run.orders_error and "2026-10-01" in run.orders_error
    assert run.orders_upserted == 0
    assert db_session.scalars(select(Order)).all() == []


def test_execute_run_ad_failure_partial_keeps_orders(db_session):
    """AC-S9：广告阶段失败 → partial，订单阶段成果不回滚。"""
    fake = FakeSyncUpstream(
        {"2026-10-01": sample_rows()}, ad_status=500
    )
    run = sync_service.execute_run(
        "manual", [date(2026, 10, 1)], db=db_session, client_factory=fake.client,
        settings=fake.settings,
    )
    assert run.status == "partial"
    assert run.ad_error and "ad sync failed" in run.ad_error
    assert run.orders_error is None
    assert len(db_session.scalars(select(Order)).all()) == 2  # 订单已独立提交


def test_execute_run_partial_ad_day_failure(db_session):
    """逐日广告拉取的单日失败：partial + ad_error 带失败日期，成功日仍落库。"""
    fake = FakeSyncUpstream(
        {"2026-10-01": sample_rows()[:1], "2026-10-02": sample_rows()[1:]},
        ad_rows=[
            {"date": "2026-10-01 00:00:00", "ad_revenue_dollars": "10.00"},
            {"date": "2026-10-02 00:00:00", "ad_revenue_dollars": "20.00"},
        ],
        ad_fail_days={"2026-10-02"},
    )
    run = sync_service.execute_run(
        "manual",
        [date(2026, 10, 1), date(2026, 10, 2)],
        db=db_session,
        client_factory=fake.client,
        settings=fake.settings,
    )
    assert run.status == "partial"
    assert run.ad_error == "ad sync failed on 1 day(s): 2026-10-02"
    assert run.orders_error is None
    ad = {row.date: row.amount_minor for row in db_session.scalars(select(AdRevenueDaily))}
    assert ad == {date(2026, 10, 1): Decimal("1000.00")}  # 失败日之外照常入库


def test_execute_run_truncated_day_recorded(db_session):
    """二分到底仍整页 → truncated_dates 记录该日、状态 partial（AC-S7）。"""
    dense = [
        {"orderId": f"D{i}", "createTime": f"2026-10-01 00:00:{10 * (i + 1):02d}", "amount": "1"}
        for i in range(4)
    ]
    fake = FakeSyncUpstream({"2026-10-01": dense}, page_size=4)
    run = sync_service.execute_run(
        "scheduled", [date(2026, 10, 1)], db=db_session, client_factory=fake.client,
        settings=fake.settings,
    )
    assert run.status == "partial"
    assert run.truncated_dates == ["2026-10-01"]


def test_execute_run_releases_current_state(db_session):
    fake = FakeSyncUpstream({"2026-10-01": sample_rows()[:1]})
    sync_service.execute_run(
        "manual", [date(2026, 10, 1)], db=db_session, client_factory=fake.client,
        settings=fake.settings,
    )
    assert sync_service.is_running() is False
    snapshot = status_snapshot(db_session)
    assert snapshot.state == "idle"
    assert snapshot.current is None
    assert snapshot.last_run is not None and snapshot.last_run.status == "success"


# ---------- 覆盖自愈（§3.3.3 / D3） ----------


def test_scheduled_days_first_run_backfills_92_days(db_session):
    days, trigger = scheduled_days(db_session, TODAY, settings=make_settings())
    assert trigger == "backfill"
    assert len(days) == 92
    assert days[0] == TODAY - timedelta(days=91)
    assert days[-1] == TODAY


def test_scheduled_days_full_coverage_falls_back_to_lookback(db_session):
    db_session.add(
        SyncRun(
            trigger="manual",
            window_start=TODAY - timedelta(days=91),
            window_end=TODAY,
            status="success",
            finished_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    days, trigger = scheduled_days(db_session, TODAY, settings=make_settings())
    assert trigger == "scheduled"
    assert days == [TODAY - timedelta(days=i) for i in (2, 1, 0)]


def test_scheduled_days_partial_coverage_backfills_gap(db_session):
    db_session.add(
        SyncRun(
            trigger="scheduled",
            window_start=TODAY,
            window_end=TODAY,
            status="success",
            finished_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    days, trigger = scheduled_days(db_session, TODAY, settings=make_settings())
    assert trigger == "backfill"
    assert len(days) == 92  # 缺口 91 天 ∪ lookback 3 天
    assert days[0] == TODAY - timedelta(days=91)


def test_scheduled_days_ignores_failed_runs(db_session):
    db_session.add(
        SyncRun(
            trigger="manual",
            window_start=TODAY - timedelta(days=91),
            window_end=TODAY,
            status="failed",
            orders_error="boom",
            finished_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    _, trigger = scheduled_days(db_session, TODAY, settings=make_settings())
    assert trigger == "backfill"  # 失败运行不算覆盖


# ---------- 手动同步钳制与入口 ----------


def test_clamp_manual_window():
    assert clamp_manual_window(date(2026, 10, 1), date(2026, 10, 5), today=TODAY) == (
        date(2026, 10, 1),
        date(2026, 10, 5),
    )
    # to 超过今天 → 压到今天；from 联动钳制
    assert clamp_manual_window(date(2026, 10, 1), date(2026, 12, 31), today=TODAY) == (
        date(2026, 10, 1),
        TODAY,
    )
    # 跨度 200 天 → 压到 92 天窗（贴 to）
    assert clamp_manual_window(date(2026, 1, 1), date(2026, 10, 12), today=TODAY) == (
        TODAY - timedelta(days=91),
        TODAY,
    )


def test_run_manual_blocking_full_rerun_idempotent(db_session):
    fake = FakeSyncUpstream({"2026-10-01": sample_rows()})
    run1 = sync_service.run_manual_blocking(
        date(2026, 10, 1),
        date(2026, 10, 1),
        db=db_session,
        client_factory=fake.client,
        today=TODAY,
        settings=fake.settings,
    )
    run2 = sync_service.run_manual_blocking(
        date(2026, 10, 1),
        date(2026, 10, 1),
        db=db_session,
        client_factory=fake.client,
        today=TODAY,
        settings=fake.settings,
    )
    assert run1.status == "success" and run2.status == "success"
    assert len(db_session.scalars(select(Order)).all()) == 2  # 重拉零重复（AC-S3）


def test_run_scheduled_skips_when_lock_held(db_session):
    assert sync_service._sync_lock.acquire(blocking=False)
    try:
        result = sync_service.run_scheduled(db=db_session, today=TODAY)
        assert result is None  # 单飞冲突：跳过本轮
    finally:
        sync_service._sync_lock.release()


# ---------- 孤儿清理（m9） ----------


def test_cleanup_orphan_runs(db_session):
    orphan = SyncRun(trigger="scheduled", window_start=TODAY, window_end=TODAY, status="running")
    finished = SyncRun(
        trigger="manual",
        window_start=TODAY,
        window_end=TODAY,
        status="success",
        finished_at=datetime.now(UTC),
    )
    db_session.add_all([orphan, finished])
    db_session.commit()
    assert sync_service.cleanup_orphan_runs(db=db_session) == 1
    db_session.commit()
    statuses = {r.id: r.status for r in db_session.scalars(select(SyncRun))}
    assert statuses[orphan.id] == "failed"
    assert orphan.orders_error == "orphaned: process restarted"
    assert statuses[finished.id] == "success"


# ---------- 状态查询 ----------


def test_orders_sync_state_never_then_ok(db_session):
    assert sync_service.orders_sync_state(db_session) == ("never", None, None)
    db_session.add(
        SyncRun(
            trigger="manual",
            window_start=date(2026, 10, 1),
            window_end=date(2026, 10, 2),
            status="success",
            finished_at=datetime(2026, 10, 12, 8, 0, tzinfo=UTC),
        )
    )
    db_session.commit()
    status, latest_at, covered = sync_service.orders_sync_state(db_session)
    assert status == "ok"
    assert covered == date(2026, 10, 2)
    assert latest_at is not None


def test_truncated_days_in_range_filters_by_window(db_session):
    db_session.add(
        SyncRun(
            trigger="manual",
            window_start=date(2026, 10, 1),
            window_end=date(2026, 10, 2),
            status="partial",
            truncated_dates=["2026-10-01", "2026-10-02"],
        )
    )
    db_session.commit()
    in_range = sync_service.truncated_days_in_range(
        db_session, date(2026, 10, 1), date(2026, 10, 1)
    )
    assert in_range == ["2026-10-01"]
    assert sync_service.truncated_days_in_range(
        db_session, date(2026, 10, 5), date(2026, 10, 6)
    ) == []


# ---------- 撤单比对（REQ-20261022-02 §1.7）----------


def _same_day_rows():
    """O1/O2 同日（10-01）两条上游行，便于单日全量比对。"""
    return [
        dict(sample_rows()[0]),
        {**sample_rows()[1], "createTime": "2026-10-01 11:30:00"},
    ]


def _run(db_session, day_rows, page_size=1000):
    fake = FakeSyncUpstream({"2026-10-01": day_rows}, page_size=page_size)
    return sync_service.execute_run(
        "manual", [date(2026, 10, 1)], db=db_session,
        client_factory=fake.client, settings=fake.settings,
    )


def test_execute_run_revokes_and_revives_on_full_day_diff(db_session):
    """完整日 diff：本地有上游无 → 标撤单；重新出现 → 恢复。"""
    rows = _same_day_rows()
    _run(db_session, rows)  # 全量入库
    _run(db_session, [rows[0]])  # 上游只剩 O1 → O2 撤单
    o1, o2 = db_session.scalars(select(Order).order_by(Order.order_id)).all()
    assert o1.revoked_at is None
    assert o2.revoked_at is not None
    _run(db_session, rows)  # O2 重新出现 → 恢复
    o1, o2 = db_session.scalars(select(Order).order_by(Order.order_id)).all()
    assert o1.revoked_at is None and o2.revoked_at is None


def test_execute_run_truncated_day_skips_revocation(db_session):
    """截断日不做撤单比对（窗口数据不完整，防误撤）。"""
    rows = _same_day_rows()
    _run(db_session, rows)  # 全量入库
    # 上游只回 O1，但 page_size=1 → 每窗整页 → truncated → 不比对
    run = _run(db_session, [rows[0]], page_size=1)
    assert run.truncated_dates == ["2026-10-01"]
    o1, o2 = db_session.scalars(select(Order).order_by(Order.order_id)).all()
    assert o1.revoked_at is None and o2.revoked_at is None  # O2 未被误撤
