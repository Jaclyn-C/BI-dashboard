"""password_service 单测（纯逻辑，无 DB）。"""

from app.services.password_service import dummy_verify, hash_password, verify_password


def test_hash_roundtrip() -> None:
    password = "correct-horse-1"
    assert verify_password(password, hash_password(password))


def test_wrong_password_fails() -> None:
    password_hash = hash_password("correct-horse-1")
    assert not verify_password("correct-horse-2", password_hash)
    assert not verify_password("", password_hash)


def test_hash_is_argon2id_phc() -> None:
    password_hash = hash_password("correct-horse-1")
    # PHC 字符串含算法 id（argon2id）与参数盐，绝不存明文
    assert password_hash.startswith("$argon2id$")
    assert "correct-horse-1" not in password_hash


def test_hash_salts_each_call() -> None:
    assert hash_password("same-password-1") != hash_password("same-password-1")


def test_long_unicode_password_supported() -> None:
    # DESIGN D1：中文密码 64 字符（192 字节）不被截断，可往返
    password = "密码" * 32 + "9"
    assert verify_password(password, hash_password(password))


def test_dummy_verify_never_raises() -> None:
    dummy_verify()  # 账号不存在时的时序抹平调用，不应抛异常
