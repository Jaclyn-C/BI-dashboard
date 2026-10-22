"""Offer API 集成测试（REQ-20261022-02 验收 2/4/5）。

- 角色门禁：admin 可读；customer/pending 403（分成条款属内部商业数据）
- 形状与格式：supplier_share 保真字符串 + 预格式百分比（50 / 12.5）
- 排序：in_use 优先 → sort_order → id
"""

from app.models import Offer, User
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
