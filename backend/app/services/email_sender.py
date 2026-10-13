"""EmailSender：接口 + SMTP 实现 + 开发日志降级 + 工厂（DESIGN D5/§3.6/§6.4）。

- SMTP 用 aiosmtplib（异步原生，路由内直接 await）；
- 邮件文案为中英双语常量（Q9），不依赖触发时的界面语言、不走前端 i18n；
- LogEmailSender 仅当 SMTP_HOST 为空**且** ENVIRONMENT=development 时由工厂启用，
  验证码永不进生产日志（AC-S2）；生产未配 SMTP → UnconfiguredEmailSender，
  发送即 EmailSendError（路由层翻译为 502 EMAIL_SEND_FAILED）。
"""

import logging
from abc import ABC, abstractmethod
from email.message import EmailMessage
from typing import Literal

import aiosmtplib

from app.config import Settings, get_settings

logger = logging.getLogger("app.email")

CodePurpose = Literal["register", "reset"]

#: 用途标签（注册 / 重置），中英双语（DESIGN §3.6）
_PURPOSE_LABELS: dict[str, tuple[str, str]] = {
    "register": ("account registration", "账号注册"),
    "reset": ("password reset", "密码重置"),
}

_SUBJECT_TEMPLATE = "[Partner Dashboard] {purpose_en} verification code / {purpose_zh}验证码"

_BODY_TEMPLATE = (
    "[EN] Your verification code for {purpose_en} is: {code}\n"
    "It is valid for {ttl_minutes} minutes. "
    "If you did not request this, please ignore this email.\n"
    "\n"
    "[中文] 您的{purpose_zh}验证码是：{code}，{ttl_minutes} 分钟内有效。\n"
    "如非本人操作，请忽略此邮件。\n"
)


class EmailSendError(Exception):
    """投递失败（路由层翻译为 502 EMAIL_SEND_FAILED）。"""


class EmailSender(ABC):
    """验证码邮件发送接口（测试以 FakeEmailSender 替换）。"""

    @abstractmethod
    async def send_code(self, to: str, code: str, *, purpose: CodePurpose) -> None:
        """发送含验证码的双语邮件。失败抛 EmailSendError。"""


def build_code_email(
    to: str, code: str, purpose: CodePurpose, *, ttl_minutes: int, from_addr: str
) -> EmailMessage:
    """构造双语纯文本验证码邮件（Q9，文案常量在本模块）。"""
    purpose_en, purpose_zh = _PURPOSE_LABELS[purpose]
    msg = EmailMessage()
    msg["Subject"] = _SUBJECT_TEMPLATE.format(purpose_en=purpose_en, purpose_zh=purpose_zh)
    msg["From"] = from_addr
    msg["To"] = to
    msg.set_content(
        _BODY_TEMPLATE.format(
            purpose_en=purpose_en, purpose_zh=purpose_zh, code=code, ttl_minutes=ttl_minutes
        )
    )
    return msg


class SmtpEmailSender(EmailSender):
    """SMTP 实现（aiosmtplib，异步原生）。"""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_addr: str,
        use_tls: bool,
        ssl: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_addr = from_addr or username
        self._use_tls = use_tls
        self._ssl = ssl  # True=隐式 SSL(465)，False=STARTTLS(587)

    async def send_code(self, to: str, code: str, *, purpose: CodePurpose) -> None:
        settings = get_settings()
        message = build_code_email(
            to,
            code,
            purpose,
            ttl_minutes=settings.code_ttl_minutes,
            from_addr=self._from_addr,
        )
        smtp = aiosmtplib.SMTP(
            hostname=self._host, port=self._port, timeout=30, use_tls=self._ssl
        )
        try:
            await smtp.connect()
            if self._use_tls and not self._ssl:
                await smtp.starttls()
            if self._username:
                await smtp.login(self._username, self._password)
            await smtp.send_message(message)
        except EmailSendError:
            raise
        except Exception as exc:  # aiosmtplib.SMTP* / OSError 等，统一为域错误
            raise EmailSendError(f"smtp delivery failed: {type(exc).__name__}") from exc
        finally:
            try:
                await smtp.quit()
            except Exception:  # noqa: BLE001 - 关连接失败不影响结果
                pass


class LogEmailSender(EmailSender):
    """开发降级：验证码打印到后端日志（仅 development + SMTP 未配置时由工厂启用）。"""

    async def send_code(self, to: str, code: str, *, purpose: CodePurpose) -> None:
        settings = get_settings()
        purpose_en, _ = _PURPOSE_LABELS[purpose]
        # 单行可读输出（AC-S2：明文只允许出现在邮件与开发日志两个出口）
        logger.warning(
            "[DEV fallback] SMTP 未配置，验证码走日志降级：to=%s purpose=%s code=%s"
            "（%s 分钟内有效；仅限 development 环境，生产禁止）",
            to,
            purpose,
            code,
            settings.code_ttl_minutes,
        )


class UnconfiguredEmailSender(EmailSender):
    """生产未配 SMTP：不做日志降级，发送即失败（DESIGN §6.4 → 502）。"""

    async def send_code(self, to: str, code: str, *, purpose: CodePurpose) -> None:
        raise EmailSendError("SMTP is not configured")


def create_email_sender(settings: Settings | None = None) -> EmailSender:
    """工厂（DESIGN §6.4 规则）：
    SMTP_HOST 已配 → SMTP；未配且 development → 日志降级；未配且 production → 失败。
    """
    settings = settings or get_settings()
    if settings.smtp_host:
        return SmtpEmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            from_addr=settings.smtp_from,
            use_tls=settings.smtp_use_tls,
            ssl=settings.smtp_ssl,
        )
    if not settings.is_production:
        return LogEmailSender()
    return UnconfiguredEmailSender()
