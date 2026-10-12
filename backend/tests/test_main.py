"""应用装配与错误信封冒烟测试（不依赖数据库，任何环境可跑）。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz_ok() -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_404_uses_error_envelope() -> None:
    """路由不存在 → 统一信封 NOT_FOUND（FastAPI 原生 404 也走信封，DESIGN §3.4）。"""
    resp = client.get("/api/v1/no-such-route")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert "message" in body["error"]
    assert "details" not in body["error"]


def test_422_uses_error_envelope_with_details() -> None:
    """请求体非法 → 422 VALIDATION_ERROR + 字段级 details（DESIGN §3.2）。

    校验失败发生在路由执行前，不触库；details 不携带用户原始输入。
    """
    resp = client.post("/api/v1/auth/login", json={"email": "not-an-email"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    fields = {item["field"] for item in body["error"]["details"]}
    assert "password" in fields  # 缺失字段出现在 details
    assert "email" in fields  # 非法格式出现在 details
    # 原始输入（含可能的密码）绝不回显
    assert "not-an-email" not in resp.text
