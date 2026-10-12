"""argon2id 密码哈希与校验（DESIGN D1/§6.5，RQ-2 定稿）。

使用 argon2-cffi 的 ``PasswordHasher`` 库默认参数（t=3/m=64MiB/p=4，
argon2id），无 bcrypt 的 72 字节截断问题。密码明文只作为入参出现，
不写入任何日志（AC-S1）。
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

#: 哑哈希：账号不存在时对它跑一次校验，抹平登录响应时序差（DESIGN §3.3(3)）
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing-flattening")


def hash_password(password: str) -> str:
    """密码 → argon2id PHC 字符串（含算法参数与随机盐）。"""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码；任何不匹配/坏哈希都只返回 False，不让异常穿透路由。"""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def dummy_verify() -> None:
    """跑一次注定失败的校验，用于账号不存在时抹平时序（§6.1）。"""
    try:
        _hasher.verify(_DUMMY_HASH, "definitely-wrong")
    except (VerificationError, InvalidHashError):
        pass
