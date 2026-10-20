"""角色权限 API 集成测试（REQ-20261020-01 验收 1/2/5 与 /me role）。"""

from app.models import User
from app.services import token_service

API = "/api/v1"

#: (path, method, body) —— 内部接口全集；客户视图接口全集
INTERNAL = [
    (f"{API}/dashboard/summary?from=2026-10-01&to=2026-10-02", "GET", None),
    (f"{API}/dashboard/orders?from=2026-10-01&to=2026-10-02", "GET", None),
    (f"{API}/dashboard/orders.csv?from=2026-10-01&to=2026-10-02&scope=all", "GET", None),
    (f"{API}/dashboard/sync", "POST", {"date_from": "2026-10-01", "date_to": "2026-10-01"}),
    (f"{API}/dashboard/sync/status", "GET", None),
]
CUSTOMER_VIEW = [
    (f"{API}/dashboard/customer-orders?from=2026-10-01&to=2026-10-02", "GET", None),
    (f"{API}/dashboard/customer-orders.csv?from=2026-10-01&to=2026-10-02", "GET", None),
]


def make_user(db, email: str, role: str):
    """直插用户 + 签发 token（同 test_dashboard_api.auth 模式）。"""
    u = User(email=email, nickname=email.split("@")[0], password_hash="x", role=role)
    db.add(u)
    db.commit()
    token, _ = token_service.create_access_token(u.id, u.credential_version)
    return u, {"Authorization": f"Bearer {token}"}


def call(client, path, method, body, headers):
    if method == "GET":
        return client.get(path, headers=headers)
    return client.post(path, json=body, headers=headers)


def test_pending_user_blocked_everywhere(client, db_session):
    _, headers = make_user(db_session, "p@example.com", "pending")
    for path, method, body in INTERNAL + CUSTOMER_VIEW + [(f"{API}/users", "GET", None)]:
        assert call(client, path, method, body, headers).status_code == 403, path


def test_customer_blocked_from_internal_but_sees_customer_view(client, db_session):
    _, headers = make_user(db_session, "c@example.com", "customer")
    for path, method, body in INTERNAL + [(f"{API}/users", "GET", None)]:
        assert call(client, path, method, body, headers).status_code == 403, path
    for path, method, body in CUSTOMER_VIEW:
        assert call(client, path, method, body, headers).status_code == 200, path


def test_admin_sees_internal(client, db_session, monkeypatch):
    _, headers = make_user(db_session, "a@example.com", "admin")
    # 同 test_dashboard_api 的隔离：不真拉起后台同步线程（全局 _current_run 会污染后续测试）
    monkeypatch.setattr("app.services.sync_service.start_manual", lambda f, t: True)
    for path, method, body in INTERNAL:
        assert call(client, path, method, body, headers).status_code != 403, path


def test_me_returns_role(client, db_session):
    user, headers = make_user(db_session, "m@example.com", "customer")
    body = client.get(f"{API}/auth/me", headers=headers).json()
    assert body["role"] == "customer"


def test_role_change_effective_immediately_without_relogin(client, db_session):
    """验收 5：旧 token 在角色变更后下一请求即按新角色判定。"""
    user, headers = make_user(db_session, "d@example.com", "admin")
    assert client.get(
        f"{API}/dashboard/summary?from=2026-10-01&to=2026-10-02", headers=headers
    ).status_code == 200

    user.role = "customer"  # 模拟另一管理员操作（不走接口，聚焦 token 语义）
    db_session.commit()

    assert client.get(
        f"{API}/dashboard/summary?from=2026-10-01&to=2026-10-02", headers=headers
    ).status_code == 403
    assert client.get(
        f"{API}/dashboard/customer-orders?from=2026-10-01&to=2026-10-02", headers=headers
    ).status_code == 200


def test_register_creates_pending_user(client, fake_sender, db_session):
    """注册即待分配（REQ §1.2）。"""
    from tests.test_auth_api import _register_user  # 复用既有注册助手

    # 实际签名 keyword-only 且返回 Response（tests/test_auth_api.py:23），按现状适配
    resp = _register_user(
        client, fake_sender, "new@example.com", nickname="新用户", password="Passw0rd123"
    )
    body = resp.json()
    assert body["user"]["role"] == "pending"
    assert client.get(
        f"{API}/dashboard/customer-orders?from=2026-10-01&to=2026-10-02",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    ).status_code == 403
