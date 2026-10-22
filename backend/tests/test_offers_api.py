"""Offer API 集成测试（REQ-20261022-02 验收 2/4/5/10）。

- 角色门禁：admin 可读；customer/pending 403（分成条款属内部商业数据）
- 形状与格式：supplier_share 保真字符串 + 预格式百分比（50 / 12.5）
- 排序：in_use 优先 → sort_order → id
- 收益：真实（orders）/mock（mock_orders）分表聚合、仅在用 offer、真值金额
"""

import datetime as dt
from decimal import Decimal

from app.models import MockOrder, Offer, Order, User
from app.services import token_service

API = "/api/v1/offers"


def make_user(db, email: str, role: str):
    """直插用户 + 签发 token（同 test_roles_api 模式）。"""
    u = User(email=email, nickname=email.split("@")[0], password_hash="x", role=role)
    db.add(u)
    db.commit()
    token, _ = token_service.create_access_token(u.id, u.credential_version)
    return u, {"Authorization": f"Bearer {token}"}


def make_offer(db, code: str, *, share="0.5", in_use=False, sort_order=0, description=None):
    o = Offer(
        code=code,
        name=f"{code} 上游",
        description=description,
        supplier_share=share,
        in_use=in_use,
        sort_order=sort_order,
    )
    db.add(o)
    db.commit()
    return o


def test_admin_sees_offers_shape_and_pct(client, db_session):
    _, headers = make_user(db_session, "a@example.com", "admin")
    make_offer(
        db_session,
        "netshort",
        share="0.5000",
        in_use=True,
        description="当前对接的上游",
    )
    body = client.get(API, headers=headers).json()
    assert len(body["offers"]) == 1
    row = body["offers"][0]
    assert row["code"] == "netshort"
    assert row["name"] == "netshort 上游"
    assert row["description"] == "当前对接的上游"
    assert row["supplier_share"] == "0.5000"
    assert row["supplier_share_pct"] == "50"  # 预格式：前端零运算
    assert row["in_use"] is True


def test_pct_fractional_share(client, db_session):
    """非整数百分比去尾零：0.125 → 12.5（不是 12.50 也不是 0.125*100 前端算）。"""
    _, headers = make_user(db_session, "a@example.com", "admin")
    make_offer(db_session, "frac", share="0.1250")
    row = client.get(API, headers=headers).json()["offers"][0]
    assert row["supplier_share"] == "0.1250"
    assert row["supplier_share_pct"] == "12.5"


def test_ordering_in_use_first_then_sort(client, db_session):
    _, headers = make_user(db_session, "a@example.com", "admin")
    make_offer(db_session, "b-idle-1", sort_order=1)
    make_offer(db_session, "a-idle-0", sort_order=0)
    make_offer(db_session, "used-9", in_use=True, sort_order=9)
    make_offer(db_session, "used-0", in_use=True, sort_order=0)
    codes = [row["code"] for row in client.get(API, headers=headers).json()["offers"]]
    assert codes == ["used-0", "used-9", "a-idle-0", "b-idle-1"]


def test_descriptionless_offer_omits_none_shape(client, db_session):
    """无说明：description 为 null（前端据此不渲染说明行，REQ AC-5）。"""
    _, headers = make_user(db_session, "a@example.com", "admin")
    make_offer(db_session, "bare")
    row = client.get(API, headers=headers).json()["offers"][0]
    assert row["description"] is None


def test_empty_offers_list(client, db_session):
    _, headers = make_user(db_session, "a@example.com", "admin")
    assert client.get(API, headers=headers).json() == {"offers": []}


def test_customer_and_pending_blocked(client, db_session):
    for email, role in [("c@example.com", "customer"), ("p@example.com", "pending")]:
        _, headers = make_user(db_session, email, role)
        assert client.get(API, headers=headers).status_code == 403, role


def test_unauthenticated_401(client):
    assert client.get(API).status_code == 401


# ---------- 供应商收益（REQ §1.5）----------


def make_real_order(db, order_id, *, usd_minor="100", order_class="included"):
    db.add(
        Order(
            order_id=order_id,
            upstream_code="netshort",
            create_time=f"2026-10-01 1{order_id}:00:00",
            create_date=dt.date(2026, 10, 1),
            theater_id="TH",
            chapter_id="CH",
            language="es-MX",
            currency_type="USD",
            amount_minor=Decimal("100"),
            usd_order_amount_minor=None if usd_minor is None else Decimal(usd_minor),
            is_returned=False,
            order_class=order_class,
        )
    )
    db.commit()


def make_mock_order(db, code, order_id, *, usd_minor="100", order_class="included"):
    db.add(
        MockOrder(
            upstream_code=code,
            order_id=order_id,
            create_time=f"2026-10-01 1{order_id}:00:00",
            create_date=dt.date(2026, 10, 1),
            currency_type="USD",
            amount_minor=Decimal("100"),
            usd_order_amount_minor=Decimal(usd_minor),
            is_returned=False,
            order_class=order_class,
        )
    )
    db.commit()


def seed_earnings_fixture(db):
    """netshort 在用 50%；mockx 在用 30%；idle 不在用 90%（有数据也不得出现）。"""
    make_offer(db, "netshort", share="0.5000", in_use=True, sort_order=0)
    make_offer(db, "mockx", share="0.3000", in_use=True, sort_order=1)
    make_offer(db, "idle", share="0.9000", in_use=False, sort_order=2)
    # 真实订单（orders）：included Σusd=350 分（含一笔 usd 缺失只计数）；excluded 不算
    make_real_order(db, "1", usd_minor="100", order_class="included")
    make_real_order(db, "2", usd_minor="250", order_class="included")
    make_real_order(db, "3", usd_minor=None, order_class="included")
    make_real_order(db, "4", usd_minor="1000", order_class="excluded")
    # mock 订单（mock_orders）：mockx included Σ=300 分；idle 的有数据也不参与
    for i in range(3):
        make_mock_order(db, "mockx", str(i))
    make_mock_order(db, "idle", "1")


def test_earnings_admin_sees_per_offer_and_total(client, db_session):
    _, headers = make_user(db_session, "a@example.com", "admin")
    seed_earnings_fixture(db_session)
    body = client.get(f"{API}/earnings", headers=headers).json()
    # 仅在用 offer，排序 sort_order
    assert [row["code"] for row in body["earnings"]] == ["netshort", "mockx"]
    netshort, mockx = body["earnings"]
    # netshort：Σusd=3.50 → 收益 1.75；usd 缺失计入订单数不计金额；excluded 不算
    assert netshort["order_count"] == 3
    assert netshort["order_total_usd"] == "3.50"
    assert netshort["supplier_earnings_usd"] == "1.75"
    assert netshort["supplier_share_pct"] == "50"
    # mockx：mock 表 Σusd=3.00 → 收益 0.90（×30% 尾数不取整，真值字符串）
    assert mockx["order_count"] == 3
    assert mockx["order_total_usd"] == "3.00"
    assert mockx["supplier_earnings_usd"] == "0.90"
    # 合计 = 两个在用 offer 之和；idle（不在用，有数据）不进任何数
    assert body["total_order_usd"] == "6.50"
    assert body["total_supplier_earnings_usd"] == "2.65"
    assert body["total_order_count"] == 6


def test_earnings_in_use_offer_without_orders_shows_zero(client, db_session):
    _, headers = make_user(db_session, "a@example.com", "admin")
    make_offer(db_session, "lonely", share="0.5", in_use=True)
    body = client.get(f"{API}/earnings", headers=headers).json()
    row = body["earnings"][0]
    assert row["order_count"] == 0
    assert row["order_total_usd"] == "0.00"
    assert row["supplier_earnings_usd"] == "0.00"


def test_earnings_empty_when_no_in_use_offers(client, db_session):
    _, headers = make_user(db_session, "a@example.com", "admin")
    make_offer(db_session, "idle", in_use=False)
    body = client.get(f"{API}/earnings", headers=headers).json()
    assert body["earnings"] == []
    assert body["total_supplier_earnings_usd"] == "0.00"


def test_earnings_customer_and_pending_blocked(client, db_session):
    for email, role in [("c@example.com", "customer"), ("p@example.com", "pending")]:
        _, headers = make_user(db_session, email, role)
        assert client.get(f"{API}/earnings", headers=headers).status_code == 403, role


def test_earnings_unauthenticated_401(client):
    assert client.get(f"{API}/earnings").status_code == 401
