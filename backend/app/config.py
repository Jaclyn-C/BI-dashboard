"""应用配置：pydantic-settings 读取 backend/.env 与环境变量（DESIGN-20261012-01 §2.2）。

凭据一律走 .env / 环境变量，代码与日志中不出现真实值（AC-S3）。
"""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
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
    smtp_ssl: bool = False  # True = 隐式 SSL（465 端口，如 163/QQ 邮箱）；False = STARTTLS（587）

    # ===== 验证码（Q2/Q3/Q4 默认值）=====
    code_ttl_minutes: int = 10
    code_max_attempts: int = 5
    code_cooldown_seconds: int = 60
    code_hourly_limit: int = 5

    # ===== CORS（dev 白名单；生产同源后收紧为空，§6.10）=====
    cors_origins: str = "http://localhost:5173"

    # ===== 上游 CPS（REQ-20261012-02 DESIGN §3.6；凭据只进 .env，AC-SEC1）=====
    upstream_base: str = "https://adminapi.netshort.com/prod-api/cps"
    upstream_client_id: str = ""
    upstream_client_secret: str = ""
    #: 拉取参数照搬参考 HTML CONFIG 并配置化（D10）
    upstream_page_size: int = 1000
    upstream_max_split_depth: int = 6
    upstream_min_split_window_seconds: int = 120
    upstream_concurrency: int = 4  # AC-U7
    upstream_timeout_seconds: int = 30  # AC-U7

    # ===== 同步调度（D1/D2/D3）=====
    #: 调度总开关（测试/本地关；测试由 tests/conftest.py 强制 false，DESIGN §3.4 m7）
    sync_enabled: bool = True
    sync_interval_minutes: int = 30  # D1
    sync_lookback_days: int = 3  # D2：每次滚动重拉最近 N 天（含当日）
    sync_backfill_days: int = 92  # D3：期望覆盖域（首次部署自动回填）

    # ===== 订单过滤与分成（REQ-20261014-01，B1 已由业务重定义解除）=====
    #: 私密盐值：sha256(salt:order_no) 稳定判定 included/excluded（需求 §3）。
    #: 只存 .env，绝不入库/入代码/泄露给下游；一经使用不可更换
    #: （更换后新订单判定与存量 tag 不一致，tag 永不改变的语义被破坏）。
    order_filter_salt: str = ""
    #: 保留比例：< keep_ratio → included（已计入/下发），默认 80%
    order_keep_ratio: Decimal = Decimal("0.8")
    #: 你的上游分成比例：全部订单原金额（上游自报美元）× 70%
    upstream_share_ratio: Decimal = Decimal("0.70")
    #: 供应商分成比例：已计入订单原金额 × 50%
    supplier_share_ratio: Decimal = Decimal("0.50")

    @field_validator("order_keep_ratio", "upstream_share_ratio", "supplier_share_ratio")
    @classmethod
    def _check_share_ratio(cls, value: Decimal) -> Decimal:
        """比例必须是 (0, 1] 内的 Decimal（防手滑配出 20 倍）。"""
        if not Decimal("0") < value <= Decimal("1"):
            raise ValueError("share ratio must be in (0, 1]")
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def upstream_credentials_configured(self) -> bool:
        """上游凭据是否已配置（调度器启动的第二道保险，DESIGN §3.4/m7）。"""
        return bool(self.upstream_client_id and self.upstream_client_secret)

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
        """生产环境启动即校验 SECRET_KEY 与过滤盐值，不合格直接失败（不允许带弱密钥上线）。"""
        if self.is_production:
            if len(self.secret_key) < 32 or self.secret_key in _INSECURE_SECRET_KEYS:
                raise ValueError("生产环境 SECRET_KEY 必须是 >=32 字符的随机值（不能是占位符）")
            if not self.order_filter_salt.strip():
                raise ValueError("生产环境 ORDER_FILTER_SALT 必须配置（盐值一经使用不可更换）")
        return self


@lru_cache
def get_settings() -> Settings:
    """进程级单例的 Settings。"""
    return Settings()
