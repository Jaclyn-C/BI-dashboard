"""ORM 模型汇总导入（Alembic autogenerate 需要全部模型在此可见）。"""

from app.models.user import User
from app.models.verification_code import VerificationCode

__all__ = ["User", "VerificationCode"]
