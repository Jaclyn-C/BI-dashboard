"""统一错误信封（DESIGN §3.2 / §3.4）。

所有错误响应形状：``{"error": {"code", "message", ["details"]}}``。
- ``code`` 机器码（前端映射 i18n key ``auth.error.<code>``）；
- ``message`` 英文兜底文案（不含任何敏感信息）；
- ``details`` 仅 VALIDATION_ERROR 出现（字段级，绝不携带用户原始输入）。

``ApiError`` 由路由层抛出（服务层异常在此翻译）；三个处理器在 main.py 注册，
保证 FastAPI 原生 404/422 也走同一信封。
"""

from typing import Any

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

#: Starlette 原生 HTTPException 状态码 → 机器码（非本应用 ApiError 的兜底映射）
_STATUS_CODE_MAP: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    502: "EMAIL_SEND_FAILED",
}


class ApiError(Exception):
    """业务错误：路由层抛出，携带机器码与 HTTP 状态码。"""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        details: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    details: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """构造统一错误信封响应。"""
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body, headers=headers)


async def api_error_handler(_: Any, exc: ApiError) -> JSONResponse:
    """ApiError → 错误信封（保留 Retry-After 等附加头）。"""
    return error_response(
        exc.status_code, exc.code, exc.message, details=exc.details, headers=exc.headers
    )


async def http_exception_handler(_: Any, exc: StarletteHTTPException) -> JSONResponse:
    """FastAPI/Starlette 原生 HTTPException（如路由不存在 404）→ 错误信封。"""
    code = _STATUS_CODE_MAP.get(exc.status_code, "HTTP_ERROR")
    message = str(exc.detail) if exc.detail else "request failed"
    headers = dict(exc.headers) if exc.headers else None
    return error_response(exc.status_code, code, message, headers=headers)


async def validation_exception_handler(_: Any, exc: RequestValidationError) -> JSONResponse:
    """请求体校验失败 → 422 VALIDATION_ERROR，details 字段级（剥离原始输入，防密码泄漏）。"""
    details = []
    for err in exc.errors():
        loc = [str(item) for item in err["loc"][1:]]  # 跳过首位的 "body"
        details.append({"field": ".".join(loc), "msg": err["msg"]})
    return error_response(
        422,
        "VALIDATION_ERROR",
        "request validation failed",
        details=details,
    )


async def uncaught_exception_handler(_: Any, exc: Exception) -> JSONResponse:
    """未捕获异常 → 500 INTERNAL_ERROR，不泄漏内部细节（堆栈只进服务端日志）。"""
    import logging

    logging.getLogger("app").exception("unhandled exception: %s", type(exc).__name__)
    return error_response(500, "INTERNAL_ERROR", "internal server error")
