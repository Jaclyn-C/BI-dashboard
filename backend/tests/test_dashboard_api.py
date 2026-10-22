"""看板 API 集成测试（登录墙 / 参数校验 / 订单表 / 手动同步；REQ AC-SEC2、AC-O*、AC-S4）。"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.models import AdRevenueDaily, Order, SyncRun, User
from app.services import sync_service, token_service

API = "/api/v1/dashboard"


@pytest.fixture
def auth(db_session):
    """直插用户 + 签发 token（绕开注册流程，聚焦看板行为）。内部接口需 admin。"""
    user = User(email="dash@example.com", nickname="dash", password_hash="x", role="admin")
    db_session.add(user)
    db_session.commit()
    token, _ = token_service.create_access_token(user.id, user.credential_version)
    return {"Authorization": f"Bearer {token}"}


def add_order(
    db,
    order_id: str,
    stamp: str,
    currency: str,
    amount_minor: str,
    *,
    language: str | None = "es-MX",
    usd_minor: str | None = "100",
    refund_time: str | None = None,
    theater_id: str = "TH",
    promotion_code: str | None = None,
    order_class: str | None = None,
    upstream: str = "netshort",
) -> None:
    db.add(
        Order(
            order_id=order_id,
            upstream_code=upstream,
            create_time=stamp,
            create_date=date.fromisoformat(stamp[:10]),
            theater_id=theater_id,
            chapter_id="CH",
            language=language,
            currency_type=currency,
            amount_minor=Decimal(amount_minor),
            usd_order_amount_minor=None if usd_minor is None else Decimal(usd_minor),
            refund_time=refund_time,
            is_returned=refund_time is not None,
            promotion_code=promotion_code,
            order_class=order_class,
        )
    )


def seed_orders(db) -> None:
    add_order(db, "A", "2026-10-01 10:00:00", "MXN", "5000", usd_minor="270",
              order_class="included")
    add_order(db, "B", "2026-10-01 11:00:00", "EUR", "1000", usd_minor="1100",
              language="fr-FR", order_class="excluded")
    add_order(db, "C", "2026-10-02 09:00:00", "KRW", "200000", usd_minor="144",
              language="ko-KR", order_class="included")
    add_order(db, "D", "2026-10-02 10:00:00", "MXN", "800", usd_minor=None,
              order_class="excluded")  # 缺 usd
    add_order(db, "E", "2026-10-02 11:00:00", "EUR", "200", usd_minor="220",
              language="fr-FR", refund_time="2026-10-03 09:00:00",
              order_class="excluded")
    db.commit()


RANGE = {"from": "2026-10-01", "to": "2026-10-02"}


# ---------- 登录墙（AC-SEC2） ----------


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/summary"),
        ("get", "/orders"),
        ("get", "/orders.csv"),
        ("get", "/customer-orders"),
        ("get", "/customer-orders.csv"),
        ("post", "/sync"),
        ("get", "/sync/status"),
    ],
)
def test_all_dashboard_routes_require_auth(client, method, path):
    resp = getattr(client, method)(f"{API}{path}", **({"params": RANGE} if method == "get" else {}))
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


# ---------- 区间校验（§5.1 → 422 VALIDATION_ERROR） ----------


def test_summary_rejects_from_after_to(client, auth):
    resp = client.get(
        f"{API}/summary", params={"from": "2026-10-05", "to": "2026-10-01"},
        headers=auth,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_summary_rejects_span_over_92_days(client, auth):
    resp = client.get(
        f"{API}/summary",
        params={"from": "2026-07-01", "to": "2026-10-01"},  # 93 天
        headers=auth,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_summary_smoke_new_kpis(client, auth, db_session):
    seed_orders(db_session)
    db_session.add(AdRevenueDaily(date=date(2026, 10, 1), amount_minor=Decimal("17144")))
    db_session.commit()
    body = client.get(f"{API}/summary", params=RANGE, headers=auth).json()
    assert set(body) == {"range", "meta", "kpis", "daily", "conv", "countries"}
    assert body["range"] == {"from": "2026-10-01", "to": "2026-10-02"}
    k = body["kpis"]
    # 新口径（REQ-20261014-01）：含退款 E(220)；D 缺 usd 不计金额
    # total = 270+1100+144+220 = 1734
    assert k["total_usd"] == "17.34"
    assert k["my_share_usd"] == "12.138"  # 1734 × 0.7 = 1213.8
    assert k["supplier_payable_usd"] == "8.67"  # × 0.5 = 867
    assert k["supplier_paid_usd"] == "2.07"  # (270+144) × 0.5 = 207
    assert k["hidden_saving_usd"] == "6.60"  # 867 − 207 = 660
    assert k["refunded_usd"] == "2.20"
    # 总实际净利润 = 实际净利(1213.8−207=1006.8) + 广告 17144 = 18150.8
    assert k["total_net_actual_usd"] == "181.508"
    assert (k["included"]["count"], k["included"]["usd"]) == (2, "4.14")
    assert (k["excluded"]["count"], k["excluded"]["usd"]) == (3, "13.20")
    assert k["orders_total"] == 5 and k["orders_returned"] == 1
    assert body["meta"]["sync_status"] == "never"


def test_summary_class_param_scopes_dataset(client, auth, db_session):
    """summary?class=included：行集收窄 + 不适用卡片 null（REQ-20261014-01）。"""
    seed_orders(db_session)
    body = client.get(
        f"{API}/summary", params={**RANGE, "class": "included"}, headers=auth
    ).json()
    k = body["kpis"]
    assert k["orders_total"] == 2  # A + C
    assert k["total_usd"] == "4.14"
    assert k["supplier_paid_usd"] == "2.07"
    assert k["supplier_payable_usd"] is None
    assert k["hidden_saving_usd"] is None
    assert k["included"] is None and k["excluded"] is None


# ---------- 订单表（§5.3） ----------


def test_orders_default_sort_and_shape(client, auth, db_session):
    seed_orders(db_session)
    body = client.get(f"{API}/orders", params=RANGE, headers=auth).json()
    assert set(body) == {
        "rows", "page", "page_size", "pages", "total", "total_in_range",
        "currencies", "upstreams",
    }
    assert body["page_size"] == 25
    assert body["total"] == body["total_in_range"] == 5
    assert body["pages"] == 1
    assert body["currencies"] == ["EUR", "KRW", "MXN"]  # 区间动态选项升序（AC-O2）
    # 默认 date desc；createTime 原值直出（AC-S8）；usd 缺失 → null
    assert [row["order_id"] for row in body["rows"]] == ["E", "D", "C", "B", "A"]
    # 上游列（REQ-20261022-02 §1.4）：存量订单统一 netshort
    assert all(row["upstream"] == "netshort" for row in body["rows"])
    row_d = body["rows"][1]
    assert row_d["usd"] is None and row_d["amount"] == "8.00"
    assert row_d["country_key"] == "MX"
    assert row_d["order_class"] == "excluded"  # tag 出真值（REQ-20261014-01）
    assert body["rows"][0]["status"] == "returned"


def test_orders_currency_and_status_filters(client, auth, db_session):
    seed_orders(db_session)
    body = client.get(
        f"{API}/orders",
        params={**RANGE, "currency": "MXN", "status": "completed"},
        headers=auth,
    ).json()
    assert [row["order_id"] for row in body["rows"]] == ["D", "A"]
    assert body["total"] == 2 and body["total_in_range"] == 5


def test_orders_class_filter(client, auth, db_session):
    """class 筛选（REQ-20261014-01 §六）：仅作用于列表行集。"""
    seed_orders(db_session)
    included = client.get(
        f"{API}/orders", params={**RANGE, "class": "included"}, headers=auth
    ).json()
    assert [row["order_id"] for row in included["rows"]] == ["C", "A"]
    assert included["total"] == 2 and included["total_in_range"] == 5
    excluded = client.get(
        f"{API}/orders", params={**RANGE, "class": "excluded"}, headers=auth
    ).json()
    assert [row["order_id"] for row in excluded["rows"]] == ["E", "D", "B"]


def test_orders_upstream_filter_and_dynamic_options(client, auth, db_session):
    """上游筛选（REQ-20261022-02 §1.4）：过滤行集与 total；选项区间动态升序去重。"""
    seed_orders(db_session)
    add_order(db_session, "M1", "2026-10-02 12:00:00", "MXN", "100", usd_minor="6",
              order_class="included", upstream="mock1")
    body = client.get(f"{API}/orders", params=RANGE, headers=auth).json()
    assert body["upstreams"] == ["mock1", "netshort"]  # 升序去重
    assert body["total"] == 6
    filtered = client.get(
        f"{API}/orders", params={**RANGE, "upstream": "mock1"}, headers=auth
    ).json()
    assert [r["order_id"] for r in filtered["rows"]] == ["M1"]
    assert filtered["total"] == 1 and filtered["total_in_range"] == 6  # 区间总数不受筛选影响
    # 客户视图同样支持（included 内过滤）
    cust = client.get(
        f"{API}/customer-orders", params={**RANGE, "upstream": "mock1"}, headers=auth
    ).json()
    assert [r["order_id"] for r in cust["rows"]] == ["M1"]
    assert cust["upstreams"] == ["mock1", "netshort"]


def test_orders_usd_sort_null_semantics(client, auth, db_session):
    """usd 排序：null → -1（HTML 语义，AC-O3）：desc 时缺 usd 行垫底、asc 时居首。"""
    seed_orders(db_session)
    desc = client.get(
        f"{API}/orders", params={**RANGE, "sort": "usd", "dir": "desc"}, headers=auth
    ).json()
    assert [row["order_id"] for row in desc["rows"]] == ["B", "A", "E", "C", "D"]
    asc = client.get(
        f"{API}/orders", params={**RANGE, "sort": "usd", "dir": "asc"}, headers=auth
    ).json()
    assert [row["order_id"] for row in asc["rows"]] == ["D", "C", "E", "A", "B"]


def test_orders_sort_amount_asc_and_pagination(client, auth, db_session):
    seed_orders(db_session)
    body = client.get(
        f"{API}/orders", params={**RANGE, "sort": "amount", "dir": "asc"}, headers=auth
    ).json()
    assert [row["order_id"] for row in body["rows"]] == ["E", "D", "B", "A", "C"]
    # 越界页：空页不 404
    empty = client.get(f"{API}/orders", params={**RANGE, "page": 9}, headers=auth).json()
    assert empty["rows"] == [] and empty["page"] == 9


def test_orders_currency_sort_tiebreak_deterministic(client, auth, db_session):
    seed_orders(db_session)
    body = client.get(
        f"{API}/orders", params={**RANGE, "sort": "currency", "dir": "asc"}, headers=auth
    ).json()
    assert [row["order_id"] for row in body["rows"]] == ["B", "E", "C", "A", "D"]


# ---------- 手动同步（§5.5：202 + accepted，不用 429） ----------


def test_sync_post_accepted_true(client, auth, monkeypatch):
    monkeypatch.setattr(sync_service, "start_manual", lambda f, t: True)
    resp = client.post(
        f"{API}/sync", json={"from": "2026-10-01", "to": "2026-10-02"}, headers=auth
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["accepted"] is True
    assert body["status"]["state"] == "idle"


def test_sync_post_busy_accepted_false(client, auth, monkeypatch):
    """单飞冲突 → 202 accepted=false（不报错，前端继续轮询）。"""
    monkeypatch.setattr(sync_service, "start_manual", lambda f, t: False)
    resp = client.post(
        f"{API}/sync", json={"from": "2026-10-01", "to": "2026-10-02"}, headers=auth
    )
    assert resp.status_code == 202
    assert resp.json()["accepted"] is False


def test_sync_status_reports_last_run(client, auth, db_session):
    db_session.add(
        SyncRun(
            trigger="manual",
            window_start=date(2026, 10, 1),
            window_end=date(2026, 10, 2),
            status="partial",
            truncated_dates=["2026-10-01"],
            orders_upserted=5,
            finished_at=datetime(2026, 10, 12, 8, 0, tzinfo=UTC),
        )
    )
    db_session.commit()
    body = client.get(f"{API}/sync/status", headers=auth).json()
    assert body["state"] == "idle"
    assert body["current"] is None
    assert body["last_run"]["status"] == "partial"
    assert body["last_run"]["truncated_days"] == ["2026-10-01"]
    assert body["last_run"]["orders_error"] is None


# ---------- 客户视图（REQ-20261015-02：included-only + 无分类字段） ----------


def test_customer_orders_included_only_and_no_class_fields(client, auth, db_session):
    seed_orders(db_session)
    resp = client.get(f"{API}/customer-orders", params=RANGE, headers=auth)
    assert resp.status_code == 200
    body = resp.json()
    # 仅已计入订单（seed 中 A/C included；B/D/E excluded 不出现）
    assert [r["order_id"] for r in body["rows"]] == ["C", "A"]  # 默认 date desc
    assert body["total"] == 2 and body["total_in_range"] == 2
    # 红线：响应中不存在任何分类字段/键名
    assert "order_class" not in resp.text
    assert "class" not in resp.text.replace("country_key", "")
    # 行字段集（纯订单信息 + 上游归属，REQ-20261022-02 §1.4）
    assert set(body["rows"][0]) == {
        "order_id", "upstream", "create_time", "country_key", "language",
        "currency", "amount", "usd", "status",
    }
    assert body["rows"][0]["upstream"] == "netshort"


def test_customer_orders_currency_filter_and_paging(client, auth, db_session):
    seed_orders(db_session)
    resp = client.get(
        f"{API}/customer-orders",
        params={**RANGE, "currency": "MXN"},
        headers=auth,
    )
    body = resp.json()
    assert [r["order_id"] for r in body["rows"]] == ["A"]
    # 分页元数据齐备（page_size=25 > total → 单页）
    assert (body["page"], body["page_size"], body["pages"]) == (1, 25, 1)
