"""应用配置：pydantic-settings 读取 backend/.env 与环境变量（DESIGN-20261012-01 §2.2）。

凭据一律走 .env / 环境变量，代码与日志中不出现真实值（AC-S3）。
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

#: 生产环境不允许的 SECRET_KEY 占位值（开发默认值，见 §6.8）
_INSECURE_SECRET_KEYS = frozenset(
    {
        "change-me",
        "dev-only-secret-key-change-me-0123456789",
    }
)


class Settings(BaseSettings):
    """全局配置。字段名与根目录 .env.example 一一对应。"""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        # .env 从根 .env.example 复制而来，含上游等无关键，忽略之
        extra="ignore",
    )

    # ===== 应用（§2.2）=====
    environment: Literal["development", "production"] = "development"
    database_url: str = "postgresql+psycopg://pd:pd@localhost:5432/pd"
    secret_key: str = "dev-only-secret-key-change-me-0123456789"
    access_token_ttl_minutes: int = 480  # Q6：8 小时

    # ===== SMTP（空 host + development → 日志降级，§6.4）=====
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    # ===== 验证码（Q2/Q3/Q4 默认值）=====
    code_ttl_minutes: int = 10
    code_max_attempts: int = 5
    code_cooldown_seconds: int = 60
    code_hourly_limit: int = 5

    # ===== CORS（dev 白名单；生产同源后收紧为空，§6.10）=====
    cors_origins: str = "http://localhost:5173"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        """逗号分隔的来源白名单（.env 里写逗号分隔字符串）。"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def code_hmac_key(self) -> str:
        """验证码 HMAC 密钥由 SECRET_KEY 派生（DESIGN §2.2 / §4.2）。"""
        return f"{self.secret_key}:code-hmac"

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        """生产环境启动即校验 SECRET_KEY，不合格直接失败（不允许带弱密钥上线）。"""
        if self.is_production:
            if len(self.secret_key) < 32 or self.secret_key in _INSECURE_SECRET_KEYS:
                raise ValueError("生产环境 SECRET_KEY 必须是 >=32 字符的随机值（不能是占位符）")
        return self


@lru_cache
def get_settings() -> Settings:
    """进程级单例的 Settings。"""
    return Settings()
