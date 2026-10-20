"""用户管理接口测试（REQ-20261020-01 验收 3/4 与列表）。"""

from tests.test_roles_api import make_user

API = "/api/v1/users"


def patch_role(client, headers, user_id, role):
    return client.patch(f"{API}/{user_id}/role", json={"role": role}, headers=headers)


def test_list_requires_admin_plus(client, db_session):
    for role in ("customer", "pending"):
        _, headers = make_user(db_session, f"l-{role}@example.com", role)
        assert client.get(API, headers=headers).status_code == 403


def test_list_shape_and_order(client, db_session):
    _, headers = make_user(db_session, "op@example.com", "admin")
    older, _ = make_user(db_session, "old@example.com", "customer")
    newer, _ = make_user(db_session, "new@example.com", "pending")

    body = client.get(API, headers=headers).json()
    ids = [u["id"] for u in body["users"]]
    assert ids.index(newer.id) < ids.index(older.id)  # created_at 倒序
    row = next(u for u in body["users"] if u["id"] == older.id)
    assert row["email"] == "old@example.com"
    assert row["role"] == "customer"
    assert set(row) >= {"id", "email", "nickname", "role", "created_at", "last_login_at"}


def test_admin_assignment_matrix(client, db_session):
    _, op_headers = make_user(db_session, "op@example.com", "admin")
    peer, _ = make_user(db_session, "peer@example.com", "admin")
    boss, _ = make_user(db_session, "boss@example.com", "super_admin")
    cust, _ = make_user(db_session, "cust@example.com", "customer")
    pend, _ = make_user(db_session, "pend@example.com", "pending")

    # 顺序调整（适配等级规则）：先撤销再提升——cust 提为 admin 后即成平级，无法再被降级
    assert patch_role(client, op_headers, cust.id, "pending").status_code == 200  # 撤销 ✓
    assert patch_role(client, op_headers, pend.id, "customer").status_code == 200
    assert patch_role(client, op_headers, cust.id, "admin").status_code == 200  # 提为平级 ✓
    assert patch_role(client, op_headers, peer.id, "customer").status_code == 403  # 平级 ✗
    assert patch_role(client, op_headers, boss.id, "customer").status_code == 403  # 上级 ✗
    assert patch_role(client, op_headers, cust.id, "super_admin").status_code == 422  # 越级值 ✗
    assert patch_role(client, op_headers, 999999, "customer").status_code == 404


def test_admin_cannot_modify_self(client, db_session):
    op, op_headers = make_user(db_session, "op@example.com", "admin")
    assert patch_role(client, op_headers, op.id, "customer").status_code == 403


def test_super_admin_can_demote_admin(client, db_session):
    _, boss_headers = make_user(db_session, "boss@example.com", "super_admin")
    admin, _ = make_user(db_session, "adm@example.com", "admin")

    resp = patch_role(client, boss_headers, admin.id, "customer")
    assert resp.status_code == 200
    assert resp.json()["role"] == "customer"


def test_role_patch_keeps_session_alive(client, db_session):
    """改角色不 bump 凭据版本：目标用户旧 token 继续可用（按新角色判定）。"""
    _, op_headers = make_user(db_session, "op@example.com", "admin")
    target, target_headers = make_user(db_session, "t@example.com", "pending")

    assert patch_role(client, op_headers, target.id, "customer").status_code == 200
    me = client.get("/api/v1/auth/me", headers=target_headers)
    assert me.status_code == 200 and me.json()["role"] == "customer"
