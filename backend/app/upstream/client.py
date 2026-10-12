"""上游 netshort CPS OAuth2 客户端（DESIGN-20261012-02 §3.1，REQ AC-U1/U5/U6/U7）。

- TokenProvider：client-credentials 换票（HTTP Basic，文档建议方式），token 缓存
  复用、到期前 60 秒主动刷新（HTML:878-908 移植）；
- post()：双层 401（HTTP 层 401 或 HTTP 200 信封 code=401）→ 丢缓存重换票 →
  重放一次原请求，绝不循环（HTML:926-939 移植）；
- 出站白名单：模块内只出现 3 个路径常量（AC-U5），代码审查断言见 B-T9；
- 超时/429 记 warning 日志并按窗口失败处理，不重试风暴（AC-U7）。

线程安全：同步管道以日窗并发 4 复用同一实例（httpx.Client 线程安全，
token 缓存以锁保护）。任何日志不得出现凭据或 token（凭据零入库红线）。
"""

import logging
import threading
import time
from typing import Any

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger("app.upstream")

#: 出站路径白名单（AC-U5：运行时仅此 3 个上游接口；新上游路径必须先登记于此）
PATH_TOKEN = "/open/oauth2/token"
PATH_ORDER_LIST = "/open/order/list"
PATH_AD_SUMMARY = "/open/order/adSummary"

#: 到期前提前刷新的秒数（AC-U1，文档「刷新 Token」建议）
_TOKEN_REFRESH_MARGIN_SECONDS = 60.0

#: token 默认有效期（响应缺 expiresIn 时的兜底，文档默认 3600）
_TOKEN_DEFAULT_TTL_SECONDS = 3600


class UpstreamError(Exception):
    """上游调用失败（网络/超时/限流/信封错误）。消息不含凭据。"""


def _envelope_msg(payload: Any) -> str:
    """从统一信封 {code, msg, traceId} 取可记录的错误描述（不含敏感值）。"""
    if isinstance(payload, dict):
        msg = payload.get("msg") or f"code {payload.get('code')}"
        trace_id = payload.get("traceId")
        return f"{msg} (traceId={trace_id})" if trace_id else str(msg)
    return "unreadable upstream body"


class UpstreamClient:
    """OAuth2 client-credentials 上游客户端（同步 httpx）。

    ``transport`` 参数供测试注入 httpx.MockTransport（真实凭据已失效，
    禁止真实出站；DESIGN §8.1 m10）。
    """

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = httpx.Client(
            base_url=self._settings.upstream_base,
            timeout=self._settings.upstream_timeout_seconds,
            transport=transport,
        )
        self._token_lock = threading.Lock()
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    # ---------- token ----------

    def _fetch_token(self) -> str:
        """换票（调用方须持锁）。响应取值路径双键名兼容（HTML:900-904 实测）。"""
        settings = self._settings
        try:
            resp = self._client.post(
                PATH_TOKEN,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                auth=(settings.upstream_client_id, settings.upstream_client_secret),
                data={"grant_type": "client_credentials"},
            )
        except httpx.HTTPError as exc:
            raise UpstreamError(f"token request failed: {type(exc).__name__}") from exc
        if resp.status_code == 401:
            raise UpstreamError("token request rejected: invalid credentials (HTTP 401)")
        if resp.status_code != 200:
            raise UpstreamError(f"token request failed: HTTP {resp.status_code}")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise UpstreamError("token response is not JSON") from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        token = (
            data.get("accessToken") or data.get("access_token")
            if isinstance(data, dict)
            else None
        )
        if not isinstance(payload, dict) or payload.get("code") != 200 or not token:
            raise UpstreamError(f"token envelope error: {_envelope_msg(payload)}")
        try:
            ttl = float(
                data.get("expiresIn")
                if data.get("expiresIn") is not None
                else data.get("expires_in")
            )
        except (TypeError, ValueError):
            ttl = _TOKEN_DEFAULT_TTL_SECONDS
        if ttl <= 0 or ttl != ttl:  # 防御性：非正数 / NaN 一律回退默认
            ttl = _TOKEN_DEFAULT_TTL_SECONDS
        self._token = str(token)
        self._token_expires_at = time.time() + ttl
        return self._token

    def get_token(self, *, force_refresh: bool = False) -> str:
        """取缓存 token；到期前 60 秒内（或强制）重换（AC-U1）。"""
        with self._token_lock:
            if (
                not force_refresh
                and self._token is not None
                and time.time() < self._token_expires_at - _TOKEN_REFRESH_MARGIN_SECONDS
            ):
                return self._token
            return self._fetch_token()

    def _drop_token(self) -> None:
        with self._token_lock:
            self._token = None
            self._token_expires_at = 0.0

    # ---------- 业务请求 ----------

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST 业务接口（Bearer），双层 401 单次重试（AC-U1，不循环）。"""
        token = self.get_token()
        payload, status = self._post_once(path, body, token)
        if status == 401 or (
            status == 200 and isinstance(payload, dict) and payload.get("code") == 401
        ):
            # 丢弃缓存 → 重换票 → 重放一次原请求；再失败由下方统一抛错
            self._drop_token()
            token = self.get_token(force_refresh=True)
            logger.info("upstream 401 on %s: token refreshed once, replaying", path)
            payload, status = self._post_once(path, body, token)
        if status != 200:
            raise UpstreamError(f"upstream {path} failed: HTTP {status}")
        if not isinstance(payload, dict) or payload.get("code") != 200:
            raise UpstreamError(f"upstream {path} envelope error: {_envelope_msg(payload)}")
        return payload

    def _post_once(self, path: str, body: dict[str, Any], token: str) -> tuple[Any, int]:
        """单次请求（不重试）。网络异常/超时翻译为 UpstreamError（AC-U7）。"""
        try:
            resp = self._client.post(
                path,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                json=body,
            )
        except httpx.HTTPError as exc:
            logger.warning("upstream %s transport error: %s", path, type(exc).__name__)
            raise UpstreamError(f"upstream {path} request failed: {type(exc).__name__}") from exc
        if resp.status_code == 429:
            # 上游限流：记日志、按失败处理，不做重试风暴（AC-U7 / §8.1 风险表）
            logger.warning("upstream %s rate limited (429)", path)
            raise UpstreamError(f"upstream {path} rate limited (HTTP 429)")
        if resp.status_code != 200:
            return None, resp.status_code
        try:
            return resp.json(), 200
        except ValueError as exc:
            raise UpstreamError(f"upstream {path} response is not JSON") from exc

    # ---------- 生命周期 ----------

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "UpstreamClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
