"""Alembic 迁移环境：接 app.config 的 DATABASE_URL 与 Base.metadata（DESIGN §4.4）。

连接串以 pydantic-settings（backend/.env / 环境变量）为准，
alembic.ini 中的 sqlalchemy.url 仅是占位，不生效。
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401 — 全部模型注册进 Base.metadata
from alembic import context
from app.config import get_settings
from app.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# DATABASE_URL 唯一真源是 Settings（与运行时同源）
config.set_main_option("sqlalchemy.url", get_settings().database_url)


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连库。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：直连目标库执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
