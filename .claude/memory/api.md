# 上游 API 事实（api）

> 来源：`docs/reference/visualisation.html` 的 CONFIG / UPSTREAM 段（2026-10-12 提炼）。**凭据一律 .env，本文件不存真实值。**

## 数据源 1：TFC 后端 API（过滤订单 + 广告收益）

- BASE：`https://api.tfctechnology.com`
- 登录：POST `/auth/login`（用户名/密码 → token）
- 过滤订单报表：`/data/partner/order/report`
  - 请求页大小设 1000，但**单次响应上限 100 行**
  - 时间窗报告 hasMore 时需二分拆窗：最大深度 6（MAX_SPLIT_DEPTH），并发 4（FETCH_CONCURRENCY）
- 广告收益：按区间查询的日汇总接口（loadAdSummary）
- 允许的日期区间最长 92 天

## 数据源 2：上游 CPS 全量订单（识别缺失订单用）

- BASE：`https://adminapi.netshort.com/prod-api/cps`
- 认证：OAuth 2.0 client credentials（上游 2026-09 切换）——POST `/open/oauth2/token`，HTTP Basic（clientId:clientSecret）→ access token；后续请求 `Authorization: Bearer <token>`
- 同样受 100 行/窗上限与二分策略约束
- 用途：与过滤报表比对得出 excluded（缺失）订单

## 已知坑

- 原实现从浏览器直连上游，受 CORS 限制（token 端点也要 CORS）——重构后改为后端服务端调用，CORS 问题自然消失
- 上游不可用时原行为：降级只显示过滤报表并提示。重构后落了库，可降级显示历史数据 + 状态标记

## 下游接口（我们提供给供应商的）

- 待需求阶段定义。原则已定：`/api/v1/supplier/**`、API key 鉴权、按供应商隔离、FastAPI OpenAPI（`/docs`）作为对外文档
