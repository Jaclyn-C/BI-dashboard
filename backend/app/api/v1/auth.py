"""认证路由六条（DESIGN §3.3，REQ-20261012-01）。

路由保持薄：参数解析 → 服务调用 → 组响应；业务事务边界在本层（commit/rollback）。
服务层见 ``app/services/``（password / token / code / email_sender）。
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_email_sender
from app.api.errors import ApiError
from app.models import User
from app.schemas.auth import (
    AuthTokenResponse,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SendCodeRequest,
    UserPublic,
)
from app.services import code_service, password_service, token_service
from app.services.code_service import CodeCooldownError, CodeHourlyLimitError, CodeInvalidError
from app.services.email_sender import EmailSender, EmailSendError

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def _rate_limit_or_429(db: Session, email: str) -> None:
    """发码限流只读检查（先于邮箱查重与写入，DESIGN §4.3 ①/评审 P1）。"""
    try:
        code_service.check_send_rate_limit(db, email)
    except CodeCooldownError as exc:
        raise ApiError(
            429,
            "CODE_SEND_COOLDOWN",
            "please wait before requesting another code",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except CodeHourlyLimitError as exc:
        raise ApiError(
            429,
            "CODE_SEND_HOURLY_LIMIT",
            "hourly code limit exceeded",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc


async def _issue_and_send(
    db: Session, email: str, purpose: code_service.CodePurpose, sender: EmailSender
) -> None:
    """落码 → 发信；发信失败整体回滚（冷却不被消耗，DESIGN §3.3(1)）。"""
    code = code_service.create_code(db, email, purpose)
    try:
        await sender.send_code(email, code, purpose=purpose)
    except EmailSendError as exc:
        db.rollback()
        raise ApiError(502, "EMAIL_SEND_FAILED", "failed to send verification email") from exc
    db.commit()


def _invalid_code_or_400(db: Session, exc: CodeInvalidError) -> ApiError:
    """验码失败：先提交尝试计数自增（防暴力猜解须持久化），再回 400。"""
    db.commit()
    return ApiError(400, "VERIFICATION_CODE_INVALID", "verification code is invalid or expired")


@router.post(
    "/register/code",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="发送注册验证码",
    description="限流检查先于邮箱查重：同邮箱 60s 冷却 / 每小时 5 封（注册与找回共用额度）。",
)
async def send_register_code(
    payload: SendCodeRequest,
    db: Session = Depends(get_db),
    sender: EmailSender = Depends(get_email_sender),
) -> None:
    """发注册验证码；邮箱已注册返回 409。"""
    _rate_limit_or_429(db, payload.email)
    if _get_user_by_email(db, payload.email) is not None:
        raise ApiError(409, "EMAIL_ALREADY_REGISTERED", "email is already registered")
    await _issue_and_send(db, payload.email, "register", sender)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=AuthTokenResponse,
    summary="注册（成功即自动登录）",
    description="先验码后建号：验证码无效时账号不创建；响应与登录同形（含 access_token）。",
)
async def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    """注册 + 自动登录（AC-R3）。"""
    if _get_user_by_email(db, payload.email) is not None:
        raise ApiError(409, "EMAIL_ALREADY_REGISTERED", "email is already registered")
    try:
        code_service.validate_code(db, payload.email, "register", payload.code)
    except CodeInvalidError as exc:
        raise _invalid_code_or_400(db, exc) from exc

    user = User(
        email=payload.email,
        nickname=payload.nickname,
        password_hash=password_service.hash_password(payload.password.get_secret_value()),
        last_login_at=datetime.now(UTC),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:  # 并发撞唯一约束的双保险（AC-S4）
        db.rollback()
        raise ApiError(409, "EMAIL_ALREADY_REGISTERED", "email is already registered") from exc

    token, expires_in = token_service.create_access_token(user.id, user.credential_version)
    return AuthTokenResponse(
        access_token=token, expires_in=expires_in, user=UserPublic.model_validate(user)
    )


@router.post(
    "/login",
    response_model=AuthTokenResponse,
    summary="登录",
    description="邮箱或密码错误统一返回模糊 401（不区分哪项错，AC-L2）。",
)
async def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    """登录（AC-L1/L2）。"""
    user = _get_user_by_email(db, payload.email)
    if user is None:
        password_service.dummy_verify()  # 账号不存在也跑一次校验，抹平时序差（§6.1）
        raise ApiError(401, "INVALID_CREDENTIALS", "invalid email or password")
    if not password_service.verify_password(
        payload.password.get_secret_value(), user.password_hash
    ):
        raise ApiError(401, "INVALID_CREDENTIALS", "invalid email or password")

    user.last_login_at = datetime.now(UTC)
    db.commit()

    token, expires_in = token_service.create_access_token(user.id, user.credential_version)
    return AuthTokenResponse(
        access_token=token, expires_in=expires_in, user=UserPublic.model_validate(user)
    )


@router.post(
    "/password/code",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="发送重置密码验证码",
    description="要求邮箱已注册（未注册 404，AC-P5 明确提示策略）；限流与注册共用。",
)
async def send_password_reset_code(
    payload: SendCodeRequest,
    db: Session = Depends(get_db),
    sender: EmailSender = Depends(get_email_sender),
) -> None:
    """发重置密码验证码。"""
    _rate_limit_or_429(db, payload.email)
    if _get_user_by_email(db, payload.email) is None:
        raise ApiError(404, "EMAIL_NOT_REGISTERED", "email is not registered")
    await _issue_and_send(db, payload.email, "reset", sender)


@router.post(
    "/password/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="重置密码",
    description="验码通过后同一事务更新密码并提升凭据版本，全部旧 token 立即失效（AC-P3/Q7）。",
)
async def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> None:
    """重置密码（AC-P1–P6）。"""
    user = _get_user_by_email(db, payload.email)
    if user is None:
        raise ApiError(404, "EMAIL_NOT_REGISTERED", "email is not registered")
    try:
        code_service.validate_code(db, payload.email, "reset", payload.code)
    except CodeInvalidError as exc:
        raise _invalid_code_or_400(db, exc) from exc

    user.password_hash = password_service.hash_password(
        payload.new_password.get_secret_value()
    )
    user.credential_version += 1  # 旧 token 因 pwd_ver 不匹配立即失效（Q7）
    db.commit()


@router.get(
    "/me",
    response_model=UserPublic,
    summary="获取当前用户",
    description="校验 token 存活与凭据版本；后续所有受保护接口复用同一 get_current_user 依赖。",
)
def me(current_user: User = Depends(get_current_user)) -> User:
    """会话恢复/存活探测（DESIGN §3.3(6)）。"""
    return current_user
