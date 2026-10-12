"""FastAPI 应用装配：CORS、统一错误信封处理器、路由挂载、/healthz（DESIGN §2.1/§3.2）。"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.errors import (
    ApiError,
    api_error_handler,
    http_exception_handler,
    uncaught_exception_handler,
    validation_exception_handler,
)
from app.api.v1 import api_router
from app.config import get_settings
from app.services.email_sender import LogEmailSender, create_email_sender

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """启动装配：邮件发送器（SMTP / 开发日志降级，DESIGN §6.4）。"""
    settings = get_settings()
    app.state.email_sender = create_email_sender(settings)
    if isinstance(app.state.email_sender, LogEmailSender):
        logger.warning("SMTP_HOST 未配置且为开发环境：验证码走日志降级（生产禁止）")
    yield


def create_app() -> FastAPI:
    """装配应用（工厂便于测试时按需覆写依赖）。"""
    settings = get_settings()
    app = FastAPI(
        title="Partner Dashboard API",
        version="0.1.0",
        description="合作伙伴收益数据平台后端。认证契约见 DESIGN-20261012-01（REQ-20261012-01）。",
        lifespan=lifespan,
    )

    if settings.cors_origin_list:
        # dev 白名单（§6.10）；生产同源部署后 CORS_ORIGINS 收紧为空即整体跳过
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # 三类异常 → 统一错误信封（含 FastAPI 原生 404/422，DESIGN §3.2）
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, uncaught_exception_handler)

    app.include_router(api_router)

    @app.get("/healthz", tags=["meta"], summary="存活探测")
    def healthz() -> dict[str, str]:
        """无副作用的存活探测（不触库）。"""
        return {"status": "ok"}

    return app


app = create_app()
