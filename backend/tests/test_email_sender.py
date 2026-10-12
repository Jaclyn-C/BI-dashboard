"""email_sender 单测（工厂规则 / 日志降级 / 双语模板；不触真实 SMTP）。"""

import asyncio
import logging

import pytest

from app.config import Settings
from app.services.email_sender import (
    EmailSendError,
    LogEmailSender,
    SmtpEmailSender,
    UnconfiguredEmailSender,
    build_code_email,
    create_email_sender,
)


def _settings(**overrides) -> Settings:
    base = {
        "environment": "development",
        "secret_key": "unit-test-secret-key-0123456789abcdef",
        "database_url": "postgresql+psycopg://pd:pd@localhost:5432/pd",
    }
    base.update(overrides)
    return Settings(**base)


def test_factory_dev_without_smtp_uses_log_fallback() -> None:
    assert isinstance(create_email_sender(_settings(smtp_host="")), LogEmailSender)


def test_factory_with_smtp_uses_smtp_sender() -> None:
    sender = create_email_sender(_settings(smtp_host="smtp.example.com"))
    assert isinstance(sender, SmtpEmailSender)


def test_factory_production_without_smtp_fails_send() -> None:
    sender = create_email_sender(_settings(environment="production", smtp_host=""))
    assert isinstance(sender, UnconfiguredEmailSender)
    with pytest.raises(EmailSendError):
        asyncio.run(sender.send_code("a@example.com", "123456", purpose="register"))


def test_production_rejects_placeholder_secret_key() -> None:
    with pytest.raises(ValueError, match="SECRET_KEY"):
        _settings(environment="production", secret_key="change-me")


def test_log_fallback_logs_code(caplog) -> None:
    sender = LogEmailSender()
    with caplog.at_level(logging.WARNING, logger="app.email"):
        asyncio.run(sender.send_code("a@example.com", "654321", purpose="reset"))
    assert "654321" in caplog.text
    assert "a@example.com" in caplog.text
    assert "reset" in caplog.text


def test_build_code_email_is_bilingual_with_code_and_ttl() -> None:
    msg = build_code_email(
        "a@example.com", "123456", "register", ttl_minutes=10, from_addr="no-reply@example.com"
    )
    subject = str(msg["Subject"])
    body = msg.get_content()
    assert "verification code" in subject and "验证码" in subject
    assert "123456" in body  # EN 段
    assert "123456" in body  # 中文段
    assert "10 分钟内有效" in body
    assert "valid for 10 minutes" in body
    assert str(msg["To"]) == "a@example.com"
