"""/api/v1 总路由（DESIGN §2.1）。

- auth：认证三件套（REQ-20261012-01）；
- dashboard：内部看板路由（登录保护，REQ-20261012-02）；
- 预留：supplier（下游供应商 API，API key 鉴权 + OpenAPI 对外文档），后续需求挂载。
"""

from fastapi import APIRouter

from app.api.v1 import auth, dashboard

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)

# 预留：from app.api.v1 import supplier → api_router.include_router(supplier.router)

