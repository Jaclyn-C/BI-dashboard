"""认证 API 集成测试（DESIGN B4 清单，走真实 PostgreSQL 测试库）。

覆盖：注册 happy path（自动登录 payload 形状）、重复邮箱、码错/过期/5 次耗尽、
双限流 429、登录成功/模糊 401、me 200/401、重置后旧 token 失效（AC-P3）、
422 规则矩阵。验证码经 FakeEmailSender 捕获（不进任何 API 响应，AC-S2）。
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select, update

from app.api.deps import get_email_sender
from app.main import app
from app.models import User, VerificationCode
from app.services import code_service
from app.services.code_service import hash_code
from app.services.email_sender import EmailSender, EmailSendError

API = "/api/v1/auth"


def _register_user(
    client, fake_sender, email: str, *, nickname: str = "测试员", password: str = "goodpass1"
):
    resp = client.post(f"{API}/register/code", json={"email": email})
    assert resp.status_code == 204
    code = fake_sender.last_code(email, "register")
    assert code
    return client.post(
        f"{API}/register",
        json={"email": email, "nickname": nickname, "password": password, "code": code},
    )


# ---------- 注册 ----------


def test_register_happy_path_auto_login(client, fake_sender):
    email = "happy@example.com"
    resp = _register_user(client, fake_sender, email)
    assert resp.status_code == 201
    body = resp.json()
    # 自动登录 payload 形状（DESIGN §3.3(2)）
    assert set(body) == {"access_token", "token_type", "expires_in", "user"}
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 28800  # 8h（Q6）
    assert set(body["user"]) == {"id", "email", "nickname", "created_at"}
    assert body["user"]["email"] == email

    # 自动登录成立：token 直接可用
    me = client.get(f"{API}/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == email


def test_register_duplicate_email_409(client, fake_sender, db_session):
    email = "dup@example.com"
    assert _register_user(client, fake_sender, email).status_code == 201
    # 第二次注册：直接经 code_service 发新码（绕过发码限流），聚焦 409 路径
    code = code_service.create_code(db_session, email, "register")
    resp = client.post(
        f"{API}/register",
        json={"email": email, "nickname": "另一个", "password": "goodpass2", "code": code},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


def test_register_wrong_code_400_and_no_user(client, fake_sender, db_session):
    email = "wrongcode@example.com"
    client.post(f"{API}/register/code", json={"email": email})
    code = fake_sender.last_code(email, "register")
    resp = client.post(
        f"{API}/register",
        json={"email": email, "nickname": "测试员", "password": "goodpass1", "code": "000000"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VERIFICATION_CODE_INVALID"
    # 先验码后建号：验码失败不产生 user 行（AC-R5）
    assert db_session.scalar(select(User).where(User.email == email)) is None
    assert code  # （真码存在，确保 400 确因码错而非没发）


def test_register_expired_code_400(client, fake_sender, db_session):
    email = "expired@example.com"
    client.post(f"{API}/register/code", json={"email": email})
    # 把最新码改成已过期（时间边界用 DB 直改模拟）
    db_session.execute(
        update(VerificationCode)
        .where(VerificationCode.email == email)
        .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    db_session.commit()
    code = fake_sender.last_code(email, "register")
    resp = client.post(
        f"{API}/register",
        json={"email": email, "nickname": "测试员", "password": "goodpass1", "code": code},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VERIFICATION_CODE_INVALID"


def test_register_code_exhausted_after_5_attempts(client, fake_sender):
    email = "exhaust@example.com"
    client.post(f"{API}/register/code", json={"email": email})
    real_code = fake_sender.last_code(email, "register")
    payload = {"email": email, "nickname": "测试员", "password": "goodpass1", "code": "000000"}
    for _ in range(5):
        resp = client.post(f"{API}/register", json=payload)
        assert resp.status_code == 400
    # 尝试耗尽后，正确码也被拒（Q3）
    payload["code"] = real_code
    resp = client.post(f"{API}/register", json=payload)
    assert resp.status_code == 400


def test_register_email_normalized(client, fake_sender, db_session):
    # 大小写与空白视为同一邮箱（DESIGN §3.1）
    _register_user(client, fake_sender, "norm@example.com")
    code = code_service.create_code(db_session, "norm@example.com", "register")
    resp = client.post(
        f"{API}/register",
        json={
            "email": "  Norm@Example.COM ",
            "nickname": "再来",
            "password": "goodpass2",
            "code": code,
        },
    )
    assert resp.status_code == 409  # 规范化后与既有账号冲突


# ---------- 发码限流 ----------


def test_send_code_cooldown_429(client, fake_sender):
    email = "cool@example.com"
    assert client.post(f"{API}/register/code", json={"email": email}).status_code == 204
    resp = client.post(f"{API}/register/code", json={"email": email})
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "CODE_SEND_COOLDOWN"
    retry_after = int(resp.headers["Retry-After"])
    assert 50 <= retry_after <= 60


def test_send_code_hourly_limit_429(client, db_session):
    email = "hourly@example.com"
    now = datetime.now(UTC)
    for offset in (120, 240, 360, 480, 600):  # 窗口内 5 条、都不在 60s 冷却内
        db_session.add(
            VerificationCode(
                email=email,
                purpose="register",
                code_hash=hash_code("111111"),
                created_at=now - timedelta(seconds=offset),
                expires_at=now + timedelta(minutes=9),
            )
        )
    db_session.commit()
    resp = client.post(f"{API}/register/code", json={"email": email})
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "CODE_SEND_HOURLY_LIMIT"
    # 最早一条在 600s 前 → Retry-After ≈ 3600-600=3000s（允许执行耗时的少量偏差）
    assert 2900 <= int(resp.headers["Retry-After"]) <= 3010


def test_rate_limit_shared_across_purposes(client, fake_sender):
    # Q4：注册与找回共用发码额度（按 email 计数）
    email = "shared@example.com"
    _register_user(client, fake_sender, email)
    resp = client.post(f"{API}/password/code", json={"email": email})
    assert resp.status_code == 429  # 注册发码后 60s 内，重置发码也进冷却
    assert resp.json()["error"]["code"] == "CODE_SEND_COOLDOWN"


class _FailingEmailSender(EmailSender):
    """永远投递失败的发送器（模拟 SMTP 故障）。"""

    async def send_code(self, to: str, code: str, *, purpose: str) -> None:
        raise EmailSendError("smtp unavailable in test")


def test_send_code_email_failure_502_and_cooldown_not_consumed(client, fake_sender, db_session):
    """发信失败 → 502 EMAIL_SEND_FAILED，且落码整体回滚（冷却不被消耗，DESIGN §3.3(1)）。"""
    email = "smtpdown@example.com"
    app.dependency_overrides[get_email_sender] = lambda: _FailingEmailSender()
    resp = client.post(f"{API}/register/code", json={"email": email})
    app.dependency_overrides[get_email_sender] = lambda: fake_sender  # 恢复正常发送器
    assert resp.status_code == 502
    body = resp.json()["error"]
    assert body["code"] == "EMAIL_SEND_FAILED"
    assert "details" not in body
    # 回滚生效：验证码行未落库
    assert (
        db_session.scalar(select(VerificationCode).where(VerificationCode.email == email)) is None
    )
    # 冷却未被消耗：立刻重发 → 204 而非 429
    assert client.post(f"{API}/register/code", json={"email": email}).status_code == 204
    assert fake_sender.last_code(email, "register")


# ---------- 登录 ----------


def test_login_success(client, fake_sender):
    email = "login@example.com"
    _register_user(client, fake_sender, email, password="goodpass1")
    resp = client.post(f"{API}/login", json={"email": email, "password": "goodpass1"})
    assert resp.status_code == 200
    assert set(resp.json()) == {"access_token", "token_type", "expires_in", "user"}


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("ghost@example.com", "goodpass1"),  # 账号不存在
        ("login2@example.com", "wrongpass1"),  # 密码错误
    ],
)
def test_login_blur_401(client, fake_sender, email, password):
    if email != "ghost@example.com":
        _register_user(client, fake_sender, email, password="goodpass1")
    resp = client.post(f"{API}/login", json={"email": email, "password": password})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "INVALID_CREDENTIALS"
    assert "details" not in body["error"]  # 模糊提示不泄露哪项错


# ---------- /me ----------


def test_me_ok_and_unauthorized(client, fake_sender):
    email = "me@example.com"
    token = _register_user(client, fake_sender, email).json()["access_token"]

    ok = client.get(f"{API}/me", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert ok.json()["email"] == email

    for headers in ({}, {"Authorization": "Bearer not.a.jwt"}, {"Authorization": "Bearer "}):
        resp = client.get(f"{API}/me", headers=headers)
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHORIZED"


# ---------- 找回密码 ----------


def _clear_code_records(db_session, email: str) -> None:
    """清掉该 email 的发码记录以绕开 60s 冷却（限流语义另有上方专项用例）。"""
    db_session.execute(delete(VerificationCode).where(VerificationCode.email == email))
    db_session.commit()


def test_password_reset_invalidates_old_token(client, fake_sender, db_session):
    """AC-P3 关键断言：重置后旧 token 立即 401，旧密码失效，新密码可登录。"""
    email = "reset@example.com"
    token = _register_user(client, fake_sender, email, password="oldpass99").json()["access_token"]
    assert client.get(f"{API}/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    _clear_code_records(db_session, email)
    assert client.post(f"{API}/password/code", json={"email": email}).status_code == 204
    code = fake_sender.last_code(email, "reset")
    resp = client.post(
        f"{API}/password/reset",
        json={"email": email, "code": code, "new_password": "newpass77"},
    )
    assert resp.status_code == 204

    # 旧 token 立即失效（AC-P3）
    assert client.get(f"{API}/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    # 旧密码失效、新密码可登录
    old_login = client.post(f"{API}/login", json={"email": email, "password": "oldpass99"})
    new_login = client.post(f"{API}/login", json={"email": email, "password": "newpass77"})
    assert old_login.status_code == 401
    assert new_login.status_code == 200


def test_password_reset_unregistered_404(client):
    resp = client.post(f"{API}/password/code", json={"email": "nobody@example.com"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "EMAIL_NOT_REGISTERED"


def test_password_reset_wrong_code_keeps_password(client, fake_sender, db_session):
    email = "reset2@example.com"
    _register_user(client, fake_sender, email, password="oldpass88")
    _clear_code_records(db_session, email)

    assert client.post(f"{API}/password/code", json={"email": email}).status_code == 204
    code = fake_sender.last_code(email, "reset")
    assert code
    resp = client.post(
        f"{API}/password/reset",
        json={"email": email, "code": "000000", "new_password": "hacked99a"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VERIFICATION_CODE_INVALID"
    # 密码未发生任何变更（AC-P4）
    login = client.post(f"{API}/login", json={"email": email, "password": "oldpass88"})
    assert login.status_code == 200


# ---------- 422 规则矩阵 ----------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("email", "not-an-email"),
        ("email", "a" * 250 + "@x.com"),
        ("nickname", "一"),
        ("nickname", "n" * 31),
        ("nickname", "非法!昵称"),
        ("password", "short1"),
        ("password", "x" * 65 + "1"),
        ("password", "nodigitshere"),
        ("password", "12345678"),
        ("code", "12a456"),
        ("code", "12345"),
    ],
)
def test_register_422_matrix(client, field, value):
    payload = {
        "email": "matrix@example.com",
        "nickname": "合法昵称",
        "password": "goodpass1",
        "code": "123456",
    }
    payload[field] = value
    resp = client.post(f"{API}/register", json=payload)
    assert resp.status_code == 422
    body = resp.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    assert body["details"]


def test_register_missing_fields_422(client):
    resp = client.post(f"{API}/register", json={})
    assert resp.status_code == 422
    fields = {item["field"] for item in resp.json()["error"]["details"]}
    assert fields == {"email", "nickname", "password", "code"}


def test_no_secret_echoed_in_responses(client, fake_sender):
    """密码/验证码不出现在任何响应体（AC-S1/S2）。"""
    email = "secret@example.com"
    client.post(f"{API}/register/code", json={"email": email})
    code = fake_sender.last_code(email, "register")
    resp = client.post(
        f"{API}/register",
        json={"email": email, "nickname": "测试员", "password": "secret99pass", "code": code},
    )
    assert resp.status_code == 201
    assert "secret99pass" not in resp.text
    assert code not in resp.text
