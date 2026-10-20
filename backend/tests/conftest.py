"""pytest 公共夹具。

测试库策略（DESIGN §2.1 / deployment.md）：
- DB 相关测试一律走本地 PostgreSQL（TEST_DATABASE_URL，默认 compose.dev.yaml 的 pd_test），
  不用 SQLite 替代，避免方言漂移；
- PostgreSQL 不可达时 DB 夹具整体 skip（原因如实展示），纯逻辑单测照常运行。

同步隔离（DESIGN-20261012-02 §3.4 m7）：在任何 app 导入前**强制**
SYNC_ENABLED=false——不依赖 .env 凭据恰好为空（调度器另有凭据双保险）。
"""

import os

# 必须先于 app 导入：环境变量优先级高于 .env（pydantic-settings），见上
os.environ["SYNC_ENABLED"] = "false"
# 屏蔽超管提权（REQ-20261020-01）：本地 .env 若配了 SUPER_ADMIN_EMAIL，
# 测试 lifespan 会经 SessionLocal 对 dev 库产生提权副作用（同 SYNC_ENABLED 思路）
os.environ["SUPER_ADMIN_EMAIL"] = ""
# 测试专用打标盐值（REQ-20261014-01）：与本地 .env 解耦，黄金向量可复算
os.environ.setdefault("ORDER_FILTER_SALT", "unit-test-salt")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import app.models  # noqa: F401 — 触发全部模型注册，create_all 需要
from app.api.deps import get_db, get_email_sender
from app.db import Base
from app.main import app
from app.services.email_sender import EmailSender

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://pd:pd@localhost:5432/pd_test"
)


def _connect_test_engine():
    """尝试连接测试库；不可达返回 None（不抛错，交由夹具 skip）。"""
    try:
        engine = create_engine(TEST_DATABASE_URL, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception:
        return None


@pytest.fixture(scope="session")
def db_engine():
    """session 级测试库引擎：建表 → 用完拆表。库不可达时 skip 全部 DB 测试。"""
    engine = _connect_test_engine()
    if engine is None:
        pytest.skip(f"PostgreSQL 测试库不可达：{TEST_DATABASE_URL}（启动 dev 库后重跑）")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """每测试独立事务并回滚（join_transaction_mode=create_savepoint，路由内 commit 只落保存点）。"""
    conn = db_engine.connect()
    txn = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        txn.rollback()
        conn.close()


class FakeEmailSender(EmailSender):
    """捕获验证码的假发送器（AC-S2：验证码不进 API 响应，只进邮件通道）。"""

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send_code(self, to: str, code: str, *, purpose: str) -> None:
        self.sent.append({"to": to, "code": code, "purpose": purpose})

    def last_code(self, to: str, purpose: str) -> str | None:
        for item in reversed(self.sent):
            if item["to"] == to and item["purpose"] == purpose:
                return item["code"]
        return None


@pytest.fixture
def fake_sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
def client(db_session: Session, fake_sender: FakeEmailSender):
    """API 集成测试客户端：get_db/get_email_sender 覆写指向测试库事务与假发送器。"""
    def _override_db() -> Session:
        return db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_email_sender] = lambda: fake_sender
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
