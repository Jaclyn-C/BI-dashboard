"""验证码生成 / 发码限流 / 验码状态机（DESIGN §4.2/§4.3）。

纯数据库逻辑、无 HTTP 感知：函数只接收 Session、只 flush 不 commit，
事务边界在路由层。明文验证码只出现在返回值 → email_sender 一条通路，
不进任何日志（生产）/API 响应（AC-S2）。
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import VerificationCode

CodePurpose = Literal["register", "reset"]


class CodeServiceError(Exception):
    """验证码域错误基类（路由层翻译为对应错误码）。"""


class CodeCooldownError(CodeServiceError):
    """同邮箱 60s 冷却期内重复发码（→ 429 CODE_SEND_COOLDOWN）。"""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(f"cooldown, retry after {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds


class CodeHourlyLimitError(CodeServiceError):
    """同邮箱 1 小时超发码上限（→ 429 CODE_SEND_HOURLY_LIMIT）。"""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(f"hourly limit exceeded, retry after {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds


class CodeInvalidError(CodeServiceError):
    """验证码错误 / 过期 / 尝试耗尽 / 无有效记录（→ 400）。"""


def generate_code() -> str:
    """6 位数字验证码（Q3），加密学随机。"""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(code: str) -> str:
    """HMAC-SHA256 摘要（密钥由 SECRET_KEY 派生，DESIGN §4.2）。"""
    settings = get_settings()
    return hmac.new(
        settings.code_hmac_key.encode("utf-8"), code.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(UTC)


def check_send_rate_limit(db: Session, email: str) -> None:
    """发码限流**只读**检查（Q4）：60s 冷却 + 每小时 5 封，按 email 跨 purpose 计数。

    必须先于邮箱查重与任何写入调用（DESIGN §4.3 ①，评审 P1）。
    """
    settings = get_settings()
    now = _utcnow()
    cooldown = timedelta(seconds=settings.code_cooldown_seconds)
    window = timedelta(hours=1)

    last = db.scalar(
        select(func.max(VerificationCode.created_at)).where(
            VerificationCode.email == email,
            VerificationCode.created_at > now - cooldown,
        )
    )
    if last is not None:
        retry_after = max(1, int((last + cooldown - now).total_seconds()) + 1)
        raise CodeCooldownError(retry_after)

    hourly = db.scalar(
        select(func.count()).select_from(VerificationCode).where(
            VerificationCode.email == email,
            VerificationCode.created_at > now - window,
        )
    )
    if hourly is not None and hourly >= settings.code_hourly_limit:
        oldest = db.scalar(
            select(func.min(VerificationCode.created_at)).where(
                VerificationCode.email == email,
                VerificationCode.created_at > now - window,
            )
        )
        if oldest is not None:
            retry_after = max(1, int((oldest + window - now).total_seconds()) + 1)
        else:  # pragma: no cover - 计数≥上限时必存在窗口内记录，防御分支
            retry_after = settings.code_cooldown_seconds
        raise CodeHourlyLimitError(retry_after)


def create_code(db: Session, email: str, purpose: CodePurpose) -> str:
    """作废该 (email, purpose) 未消费码 → 落新码 → 机会式清理（DESIGN §4.3 ②③）。

    返回明文验证码：只交给 email_sender，绝不写日志 / 响应。
    只 flush 不 commit——发信失败由路由层整体回滚，冷却不被消耗。
    """
    settings = get_settings()
    now = _utcnow()

    db.execute(
        update(VerificationCode)
        .where(
            VerificationCode.email == email,
            VerificationCode.purpose == purpose,
            VerificationCode.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )

    code = generate_code()
    db.add(
        VerificationCode(
            email=email,
            purpose=purpose,
            code_hash=hash_code(code),
            expires_at=now + timedelta(minutes=settings.code_ttl_minutes),
            created_at=now,
        )
    )
    db.flush()

    # 机会式清理：删除该 email 24h 前的记录（DESIGN §4.3）
    db.execute(
        delete(VerificationCode).where(
            VerificationCode.email == email,
            VerificationCode.created_at < now - timedelta(hours=24),
        )
    )
    return code


def validate_code(db: Session, email: str, purpose: CodePurpose, code: str) -> None:
    """验码状态机（DESIGN §4.3 验码）：通过则打 consumed_at，交由路由层业务事务收尾。

    失败一律 CodeInvalidError（错误/过期/耗尽/无记录统一 400，DESIGN §3.3(2)）。
    """
    settings = get_settings()
    now = _utcnow()

    row = db.scalar(
        select(VerificationCode)
        .where(
            VerificationCode.email == email,
            VerificationCode.purpose == purpose,
            VerificationCode.consumed_at.is_(None),
        )
        .order_by(VerificationCode.created_at.desc(), VerificationCode.id.desc())
        .limit(1)
    )
    if row is None:
        raise CodeInvalidError("no active code")

    if row.expires_at <= now:
        raise CodeInvalidError("code expired")

    if row.attempts >= settings.code_max_attempts:
        raise CodeInvalidError("code exhausted")

    if not hmac.compare_digest(row.code_hash, hash_code(code)):
        # 行级 UPDATE 自增，防并发绕过尝试上限（DESIGN §4.3）
        db.execute(
            update(VerificationCode)
            .where(
                VerificationCode.id == row.id,
                VerificationCode.attempts < settings.code_max_attempts,
            )
            .values(attempts=VerificationCode.attempts + 1)
        )
        raise CodeInvalidError("code mismatch")

    row.consumed_at = now
    db.flush()
