"""数据库引擎与会话（SQLAlchemy 2，DESIGN §2.1）。

- Base 的 metadata 带约束命名约定，保证 Alembic autogenerate 迁移确定性、可回滚；
- 事务边界在路由/依赖层：服务层函数只接收 Session、只 flush 不 commit。
"""

from collections.abc import Generator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

#: 约束命名约定（ix/uq/ck/fk/pk），模型未显式命名时按此生成确定性名称
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(referred_table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """全项目 ORM 模型基类。"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：请求级 Session，请求结束关闭（事务边界在此层）。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
