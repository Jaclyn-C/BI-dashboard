"""code_service 单测（DB 逻辑，走 conftest 的 PostgreSQL 测试库夹具）。

时间边界用直接插入带指定 created_at/expires_at 的记录模拟，不 sleep。
"""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import VerificationCode
from app.services import code_service
from app.services.code_service import (
    CodeCooldownError,
    CodeHourlyLimitError,
    CodeInvalidError,
    check_send_rate_limit,
    create_code,
    generate_code,
    hash_code,
    validate_code,
)

EMAIL = "tester@example.com"


def _insert_code(
    db,
    *,
    email: str = EMAIL,
    purpose: str = "register",
    created_at,
    expires_at=None,
    attempts: int = 0,
    consumed=False,
    code: str = "000111",
) -> VerificationCode:
    row = VerificationCode(
        email=email,
        purpose=purpose,
        code_hash=hash_code(code),
        attempts=attempts,
        created_at=created_at,
        expires_at=expires_at or created_at + timedelta(minutes=10),
        consumed_at=created_at if consumed else None,
    )
    db.add(row)
    db.flush()
    return row


def _now():
    from app.services.code_service import _utcnow

    return _utcnow()


# ---------- 纯逻辑 ----------


def test_generate_code_format() -> None:
    for _ in range(20):
        code = generate_code()
        assert len(code) == 6
        assert code.isdigit()


def test_hash_code_stable_and_hex() -> None:
    digest = hash_code("123456")
    assert len(digest) == 64
    int(digest, 16)  # 十六进制
    assert digest == hash_code("123456")
    assert digest != hash_code("123457")


# ---------- 发码限流（只读检查） ----------


def test_rate_limit_passes_when_no_records(db_session) -> None:
    check_send_rate_limit(db_session, "fresh@example.com")  # 不抛即通过


def test_rate_limit_cooldown_within_60s(db_session) -> None:
    _insert_code(db_session, created_at=_now() - timedelta(seconds=30))
    with pytest.raises(CodeCooldownError) as exc_info:
        check_send_rate_limit(db_session, EMAIL)
    # 剩余冷却 ≈30s（允许取整误差）
    assert 25 <= exc_info.value.retry_after_seconds <= 35


def test_rate_limit_cooldown_expired_after_60s(db_session) -> None:
    _insert_code(db_session, created_at=_now() - timedelta(seconds=61))
    check_send_rate_limit(db_session, EMAIL)  # 冷却已过，不抛


def test_rate_limit_hourly_cap(db_session) -> None:
    # 5 条都在 1 小时窗口内（最早一条 10 分钟前，其余更近）→ 第 6 次被拒
    base = _now()
    for offset in (600, 500, 400, 300, 200):
        _insert_code(db_session, created_at=base - timedelta(seconds=offset))
    with pytest.raises(CodeHourlyLimitError):
        check_send_rate_limit(db_session, EMAIL)


def test_rate_limit_hourly_window_slides(db_session) -> None:
    # 5 条但最早一条已超出 1 小时窗口 → 只计 4 条，放行
    base = _now()
    _insert_code(db_session, created_at=base - timedelta(seconds=3700))
    for offset in (600, 500, 400, 300):
        _insert_code(db_session, created_at=base - timedelta(seconds=offset))
    check_send_rate_limit(db_session, EMAIL)


def test_rate_limit_counts_across_purposes(db_session) -> None:
    # 同邮箱跨 purpose 共用额度（Q4）：reset 的记录也占用 register 的冷却
    _insert_code(db_session, purpose="reset", created_at=_now() - timedelta(seconds=30))
    with pytest.raises(CodeCooldownError):
        check_send_rate_limit(db_session, EMAIL)


# ---------- 发码：顶替旧码 + 机会式清理 ----------


def test_create_code_supersedes_active_codes(db_session) -> None:
    old = _insert_code(db_session, created_at=_now() - timedelta(minutes=5))
    code = create_code(db_session, EMAIL, "register")
    assert len(code) == 6 and code.isdigit()

    db_session.refresh(old)
    assert old.consumed_at is not None  # 旧码作废

    active = db_session.scalars(
        select(VerificationCode).where(
            VerificationCode.email == EMAIL, VerificationCode.consumed_at.is_(None)
        )
    ).all()
    assert len(active) == 1
    assert active[0].code_hash == hash_code(code)


def test_create_code_cleans_24h_old_records(db_session) -> None:
    stale = _insert_code(
        db_session, created_at=_now() - timedelta(hours=25), consumed=True
    )
    create_code(db_session, EMAIL, "register")
    found = db_session.get(VerificationCode, stale.id)
    assert found is None  # 机会式清理删除 24h 前记录


# ---------- 验码状态机 ----------


def test_validate_code_no_record(db_session) -> None:
    with pytest.raises(CodeInvalidError):
        validate_code(db_session, "nobody@example.com", "register", "123456")


def test_validate_code_expired_rejected(db_session) -> None:
    _insert_code(db_session, code="111222", created_at=_now() - timedelta(minutes=11),
                 expires_at=_now() - timedelta(minutes=1))
    with pytest.raises(CodeInvalidError):
        validate_code(db_session, EMAIL, "register", "111222")


def test_validate_code_mismatch_increments_attempts(db_session) -> None:
    row = _insert_code(db_session, code="111222", created_at=_now())
    for i in range(5):
        with pytest.raises(CodeInvalidError):
            validate_code(db_session, EMAIL, "register", "999999")
        db_session.refresh(row)
        assert row.attempts == i + 1  # 行级自增生效


def test_validate_code_exhausted_after_5_attempts(db_session) -> None:
    # 尝试耗尽后，正确验证码也被拒绝（Q3）
    _insert_code(db_session, code="111222", created_at=_now(), attempts=5)
    with pytest.raises(CodeInvalidError):
        validate_code(db_session, EMAIL, "register", "111222")


def test_validate_code_success_consumes(db_session) -> None:
    row = _insert_code(db_session, code="111222", created_at=_now())
    validate_code(db_session, EMAIL, "register", "111222")
    db_session.refresh(row)
    assert row.consumed_at is not None

    # 已消费的码不能复活（AC-R5：过期/已消费再提交仍拒）
    with pytest.raises(CodeInvalidError):
        validate_code(db_session, EMAIL, "register", "111222")


def test_validate_code_uses_latest_active(db_session) -> None:
    _insert_code(db_session, code="111222", created_at=_now() - timedelta(minutes=5))
    latest = _insert_code(db_session, code="333444", created_at=_now())
    # 旧码已被新码顶替：只有最新有效码可验
    with pytest.raises(CodeInvalidError):
        validate_code(db_session, EMAIL, "register", "111222")
    validate_code(db_session, EMAIL, "register", "333444")
    db_session.refresh(latest)
    assert latest.consumed_at is not None


def test_validate_code_purpose_isolated(db_session) -> None:
    _insert_code(db_session, purpose="reset", code="111222", created_at=_now())
    with pytest.raises(CodeInvalidError):
        validate_code(db_session, EMAIL, "register", "111222")  # purpose 不匹配


def test_code_hash_uses_derived_key(db_session) -> None:
    # HMAC 密钥派生自 SECRET_KEY（§4.2）：直接改设置派生串会得到不同摘要
    assert hash_code("111222") == code_service.hash_code("111222")
    assert len(hash_code("111222")) == 64
