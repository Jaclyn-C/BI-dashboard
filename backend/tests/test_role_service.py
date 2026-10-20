"""角色服务单测：等级判定矩阵 + 启动提权（REQ-20261020-01 §1.3/§1.4）。"""

from app.models.user import (
    ROLE_ADMIN,
    ROLE_CUSTOMER,
    ROLE_PENDING,
    ROLE_SUPER_ADMIN,
    User,
)
from app.services import role_service


def _user(uid: int, role: str) -> User:
    """内存对象即可：can_assign_role 只读 id/role。"""
    u = User(email=f"u{uid}@example.com", nickname=f"u{uid}", password_hash="x", role=role)
    u.id = uid
    return u


class TestCanAssignRole:
    def test_super_admin_can_demote_admin(self):
        op, target = _user(1, ROLE_SUPER_ADMIN), _user(2, ROLE_ADMIN)
        assert role_service.can_assign_role(op, target, ROLE_CUSTOMER) is True

    def test_super_admin_can_touch_customer_and_pending(self):
        op = _user(1, ROLE_SUPER_ADMIN)
        assert role_service.can_assign_role(op, _user(2, ROLE_CUSTOMER), ROLE_ADMIN) is True
        assert role_service.can_assign_role(op, _user(3, ROLE_PENDING), ROLE_ADMIN) is True

    def test_admin_can_promote_customer_to_admin(self):
        op, target = _user(1, ROLE_ADMIN), _user(2, ROLE_CUSTOMER)
        assert role_service.can_assign_role(op, target, ROLE_ADMIN) is True

    def test_admin_can_revoke_customer_to_pending(self):
        op, target = _user(1, ROLE_ADMIN), _user(2, ROLE_CUSTOMER)
        assert role_service.can_assign_role(op, target, ROLE_PENDING) is True

    def test_admin_cannot_touch_peer_admin(self):
        op, target = _user(1, ROLE_ADMIN), _user(2, ROLE_ADMIN)
        assert role_service.can_assign_role(op, target, ROLE_CUSTOMER) is False

    def test_admin_cannot_touch_super_admin(self):
        op, target = _user(1, ROLE_ADMIN), _user(2, ROLE_SUPER_ADMIN)
        assert role_service.can_assign_role(op, target, ROLE_CUSTOMER) is False

    def test_admin_cannot_touch_self(self):
        op = _user(1, ROLE_ADMIN)
        assert role_service.can_assign_role(op, op, ROLE_CUSTOMER) is False

    def test_admin_cannot_assign_super_admin_role(self):
        op, target = _user(1, ROLE_ADMIN), _user(2, ROLE_CUSTOMER)
        assert role_service.can_assign_role(op, target, ROLE_SUPER_ADMIN) is False

    def test_customer_and_pending_cannot_assign(self):
        op = _user(1, ROLE_CUSTOMER)
        assert role_service.can_assign_role(op, _user(2, ROLE_PENDING), ROLE_CUSTOMER) is False
        op2 = _user(3, ROLE_PENDING)
        assert role_service.can_assign_role(op2, _user(4, ROLE_CUSTOMER), ROLE_CUSTOMER) is False


class TestEnsureSuperAdmin:
    def test_promotes_pending_user_idempotently(self, db_session):
        u = User(email="boss@example.com", nickname="boss", password_hash="x")
        db_session.add(u)
        db_session.commit()

        first = role_service.ensure_super_admin(db_session, "Boss@Example.com ")
        assert first is not None and first.role == ROLE_SUPER_ADMIN

        again = role_service.ensure_super_admin(db_session, "boss@example.com")
        assert again is not None and again.role == ROLE_SUPER_ADMIN  # 幂等，无异常

    def test_unknown_email_skipped(self, db_session):
        assert role_service.ensure_super_admin(db_session, "nobody@example.com") is None

    def test_empty_email_noop(self, db_session):
        assert role_service.ensure_super_admin(db_session, "  ") is None
