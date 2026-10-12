"""上游 OAuth2 客户端单测（全走 httpx.MockTransport，零真实出站，DESIGN §8.1 m10）。

覆盖（REQ AC-U1/U5/U7）：token 缓存复用、到期前 60s 主动刷新、HTTP 层 401 /
信封 code=401 双层判定各重放一次且绝不循环、信封非 200 抛错、429 不重试、
token 请求本身 401（凭据无效）。
"""

import json
import threading

import httpx
import pytest

from app.config import Settings
from app.upstream.client import (
    PATH_AD_SUMMARY,
    PATH_ORDER_LIST,
    PATH_TOKEN,
    UpstreamClient,
    UpstreamError,
)


def make_settings(**overrides) -> Settings:
    base = {"upstream_client_id": "test-id", "upstream_client_secret": "test-secret"}
    base.update(overrides)
    return Settings(**base)


class FakeUpstream:
    """MockTransport 假上游：记录请求，按路径分发可编程响应。"""

    def __init__(self, *, token_ttl: float = 3600) -> None:
        self.requests: list[tuple[str, dict | str, str]] = []
        self.lock = threading.Lock()
        self.token_ttl = token_ttl
        self.token_status = 200
        self.token_payload: dict | None = None
        #: 业务响应函数 (path, body, auth) -> (status, payload)
        self.business = lambda path, body, auth: (200, {"code": 200, "msg": "ok", "data": {}})

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        raw = request.content.decode()
        try:
            body = json.loads(raw) if raw else {}
        except ValueError:
            body = raw
        auth = request.headers.get("Authorization", "")
        with self.lock:
            self.requests.append((path, body, auth))
        if path.endswith(PATH_TOKEN):
            if self.token_status != 200:
                return httpx.Response(self.token_status, json={})
            payload = self.token_payload
            if payload is None:
                payload = {
                    "code": 200,
                    "msg": "ok",
                    "data": {
                        "accessToken": f"tok-{len(self.requests)}",
                        "expiresIn": self.token_ttl,
                    },
                }
            return httpx.Response(200, json=payload)
        status, payload = self.business(path, body, auth)
        return httpx.Response(status, json=payload)

    def token_calls(self) -> list[tuple[dict, str]]:
        return [(body, auth) for path, body, auth in self.requests if path.endswith(PATH_TOKEN)]

    def business_calls(self) -> list[tuple[str, dict]]:
        return [
            (path, body)
            for path, body, _ in self.requests
            if not path.endswith(PATH_TOKEN)
        ]


def test_path_whitelist_constants():
    """出站白名单恰好 3 个路径常量（AC-U5；grep 断言另见 test_redlines）。"""
    assert PATH_TOKEN == "/open/oauth2/token"
    assert PATH_ORDER_LIST == "/open/order/list"
    assert PATH_AD_SUMMARY == "/open/order/adSummary"


def test_token_cached_and_reused():
    """换票一次后缓存复用：两次业务请求只打一次 token 接口（AC-U1）。"""
    fake = FakeUpstream()
    with UpstreamClient(transport=fake.transport, settings=make_settings()) as client:
        client.post(PATH_ORDER_LIST, {"page": 1})
        client.post(PATH_ORDER_LIST, {"page": 1})
    assert len(fake.token_calls()) == 1
    # token 请求走 HTTP Basic（client-credentials 文档建议方式）
    assert fake.token_calls()[0][1].startswith("Basic ")
    # 业务请求 Bearer 携带同一 token
    business_auth = [
        auth for path, _, auth in fake.requests if not path.endswith(PATH_TOKEN)
    ]
    assert business_auth == ["Bearer tok-1", "Bearer tok-1"]


def test_token_early_refresh_within_margin():
    """到期前 60s 主动刷新：TTL=30s（< margin）→ 第二次调用必重换票。"""
    fake = FakeUpstream(token_ttl=30)
    with UpstreamClient(transport=fake.transport, settings=make_settings()) as client:
        client.post(PATH_ORDER_LIST, {})
        client.post(PATH_ORDER_LIST, {})
    assert len(fake.token_calls()) == 2


def test_http_401_replays_once_with_new_token():
    """HTTP 层 401：丢缓存 → 重换票 → 重放一次原请求（AC-U1）。"""
    fake = FakeUpstream()
    attempts = {"n": 0}

    def business(path, body, auth):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return 401, {}
        return 200, {"code": 200, "msg": "ok", "data": {"list": []}}

    fake.business = business
    with UpstreamClient(transport=fake.transport, settings=make_settings()) as client:
        payload = client.post(PATH_ORDER_LIST, {"page": 1})
    assert payload["code"] == 200
    assert attempts["n"] == 2
    assert len(fake.token_calls()) == 2  # 旧票 + 强刷的新票


def test_envelope_401_replays_once():
    """双层 401 的第二层：HTTP 200 但信封 code=401 同样触发单次重放。"""
    fake = FakeUpstream()
    attempts = {"n": 0}

    def business(path, body, auth):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return 200, {"code": 401, "msg": "token expired"}
        return 200, {"code": 200, "msg": "ok", "data": {}}

    fake.business = business
    with UpstreamClient(transport=fake.transport, settings=make_settings()) as client:
        client.post(PATH_AD_SUMMARY, {})
    assert attempts["n"] == 2
    assert len(fake.token_calls()) == 2


def test_persistent_401_does_not_loop():
    """持续 401：只重放一次后抛 UpstreamError，绝不循环（AC-U1）。"""
    fake = FakeUpstream()
    fake.business = lambda path, body, auth: (401, {})
    with UpstreamClient(transport=fake.transport, settings=make_settings()) as client:
        with pytest.raises(UpstreamError):
            client.post(PATH_ORDER_LIST, {})
    assert len(fake.business_calls()) == 2
    assert len(fake.token_calls()) == 2


def test_envelope_code_not_200_raises():
    """HTTP 200 但信封 code≠200/401：直接 UpstreamError（含可记录消息）。"""
    fake = FakeUpstream()
    fake.business = lambda path, body, auth: (
        200,
        {"code": 500, "msg": "upstream boom", "traceId": "t-123"},
    )
    with UpstreamClient(transport=fake.transport, settings=make_settings()) as client:
        with pytest.raises(UpstreamError) as excinfo:
            client.post(PATH_ORDER_LIST, {})
    assert "upstream boom" in str(excinfo.value)
    assert "t-123" in str(excinfo.value)


def test_http_500_raises():
    """HTTP 非 200 非 401：抛错（不重试）。"""
    fake = FakeUpstream()
    fake.business = lambda path, body, auth: (500, {})
    with UpstreamClient(transport=fake.transport, settings=make_settings()) as client:
        with pytest.raises(UpstreamError, match="HTTP 500"):
            client.post(PATH_ORDER_LIST, {})


def test_429_raises_without_retry_storm():
    """429 限流：记日志按窗口失败处理，不做重试风暴（AC-U7）。"""
    fake = FakeUpstream()
    fake.business = lambda path, body, auth: (429, {})
    with UpstreamClient(transport=fake.transport, settings=make_settings()) as client:
        with pytest.raises(UpstreamError, match="429"):
            client.post(PATH_ORDER_LIST, {})
    assert len(fake.business_calls()) == 1


def test_token_request_rejected_401():
    """换票本身 401：凭据无效，明确报错且不进业务请求。"""
    fake = FakeUpstream()
    fake.token_status = 401
    with UpstreamClient(transport=fake.transport, settings=make_settings()) as client:
        with pytest.raises(UpstreamError, match="invalid credentials"):
            client.post(PATH_ORDER_LIST, {})
    assert fake.business_calls() == []


def test_token_envelope_error_raises():
    """换票信封异常（code≠200 / 缺 accessToken）：抛错。"""
    fake = FakeUpstream()
    fake.token_payload = {"code": 200, "msg": "ok", "data": {}}
    with UpstreamClient(transport=fake.transport, settings=make_settings()) as client:
        with pytest.raises(UpstreamError, match="token envelope"):
            client.post(PATH_ORDER_LIST, {})


def test_token_alternate_key_names():
    """取值路径双键名兼容：expiresIn/accessToken 与 expires_in/access_token。"""
    fake = FakeUpstream()
    fake.token_payload = {
        "code": 200,
        "msg": "ok",
        "data": {"access_token": "alt-token", "expires_in": 3600},
    }
    with UpstreamClient(transport=fake.transport, settings=make_settings()) as client:
        token = client.get_token()
        client.post(PATH_ORDER_LIST, {})
    assert token == "alt-token"
    assert fake.business_calls()[0][1] == {}  # 业务请求发出（Bearer alt-token）
