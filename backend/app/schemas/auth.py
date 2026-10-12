"""认证入出参与校验规则（DESIGN §3.3/§5.2，REQ-20261012-01）。

校验规则与前端 ``frontend/src/utils/validation.js`` 同源（Q1/Q3/Q5 默认值）：
正则与长度限制改动必须双侧同步（DESIGN R7）。
"""

import re
from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    SecretStr,
    field_validator,
)

# 邮箱入参统一「去首尾空白 + 转小写」（DESIGN §3.1）


def _strip(value: str) -> str:
    return value.strip()


def _lower(value: str) -> str:
    return value.lower()


def _ensure_email_length(value: str) -> str:
    if len(value) > 254:
        raise ValueError("email must be at most 254 characters")
    return value


EmailField = Annotated[
    EmailStr, BeforeValidator(_strip), AfterValidator(_lower), AfterValidator(_ensure_email_length)
]

#: 昵称：2–30 字符，允许中文（U+4E00–U+9FFF）、字母、数字、下划线、连字符（Q5）
NICKNAME_PATTERN = r"^[A-Za-z0-9_\-一-鿿]{2,30}$"

#: 验证码：恰好 6 位数字（Q3）
CODE_PATTERN = r"^[0-9]{6}$"


def _validate_password(value: SecretStr) -> SecretStr:
    """密码：8–64 字符且同时包含字母与数字（Q1）。SecretStr 防 repr 泄漏（§6.5）。"""
    raw = value.get_secret_value()
    if not 8 <= len(raw) <= 64:
        raise ValueError("password must be 8-64 characters")
    if not re.search(r"[A-Za-z]", raw) or not re.search(r"[0-9]", raw):
        raise ValueError("password must contain both letters and digits")
    return value


def _validate_nickname(value: str) -> str:
    if not re.fullmatch(NICKNAME_PATTERN, value):
        raise ValueError("nickname must be 2-30 chars of letters, digits, _ - or CJK")
    return value


def _validate_code(value: str) -> str:
    if not re.fullmatch(CODE_PATTERN, value):
        raise ValueError("code must be exactly 6 digits")
    return value


class SendCodeRequest(BaseModel):
    """发送验证码入参（注册与找回共用形状）。"""

    email: EmailField


class RegisterRequest(BaseModel):
    """注册入参：四项全必填。"""

    email: EmailField
    nickname: str
    password: SecretStr
    code: str

    _nickname = field_validator("nickname")(_validate_nickname)
    _password = field_validator("password")(_validate_password)
    _code = field_validator("code")(_validate_code)


class LoginRequest(BaseModel):
    """登录入参。"""

    email: EmailField
    password: SecretStr

    _password = field_validator("password")(_validate_password)


class ResetPasswordRequest(BaseModel):
    """重置密码入参：三项缺一不可（AC-P1）。"""

    email: EmailField
    code: str
    new_password: SecretStr

    _code = field_validator("code")(_validate_code)
    _new_password = field_validator("new_password")(_validate_password)


class UserPublic(BaseModel):
    """用户载荷：注册/登录响应与 /me 完全同形（评审 P6 统一）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nickname: str
    created_at: datetime


class AuthTokenResponse(BaseModel):
    """登录/注册成功响应（保留 access_token 键名，DESIGN D9）。"""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: UserPublic
