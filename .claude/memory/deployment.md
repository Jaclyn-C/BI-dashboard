# 部署知识（deployment）

> 目标：公网服务器部署，供应商经公网调用下游 API。首次实际部署后由负责 Agent 补充实测细节。

## 代码远端

- GitHub `Jaclyn-C/BI-dashboard`（https://github.com/Jaclyn-C/BI-dashboard.git，用户受控）。
- 推送策略（用户指示 2026-10-12）：**每个功能完成后先交用户验证，用户确认没问题才推送**。

## 形态（计划）

- Docker Compose：`api`（FastAPI/uvicorn）+ `postgres` + 反向代理（Caddy 或 Nginx，HTTPS/自动证书）
- 前端构建产物由反向代理静态托管（具体在首次部署 DESIGN 中定）
- 配置全部走环境变量 / `.env`；配置项清单见根目录 `.env.example`

## 安全底线（外网 = 红线加强）

1. 所有凭据走 `.env`（上游 OAuth、数据库、供应商 API key、内部账号）——代码零硬编码
2. 下游 API：API key + 按供应商隔离 + 限流
3. HTTPS 强制；内部看板登录对标参考 HTML 行为（token）
4. 数据库不暴露公网端口；`pg_dump` 定时备份

## 环境规划

- **dev**：本地 docker compose（PostgreSQL 与生产同款，不用 SQLite 替代，避免方言漂移）
- **prod**：公网 VPS + compose；升级流程待首次部署时补充

## 物料落地（2026-10-15，临时演示）

- `compose.prod.yaml`：api + postgres（不映射端口）+ caddy（静态前端 + /api 反代 + SPA 回退），可选 `--profile tunnel`（cloudflared 快速隧道，免域名 HTTPS）
- `backend/Dockerfile`（py3.12-slim，启动先 alembic upgrade）、`frontend/Dockerfile`（node20 + pnpm@10 构建 → caddy:2-alpine 托管 dist）、`deploy/Caddyfile`（SITE_ADDRESS 空=纯 80；填 sslip.io 域名=自动 HTTPS）
- `.env.prod.example` → `.env.prod`（不入库）；操作手册 `docs/deploy-temp-demo.md`（按量付费 VPS、pg_dump 本地数据导入、演示完销毁）
- 演示默认 ENVIRONMENT=development（验证码走日志）；上游凭据留空 → sync 调度自动不跑，分类口径零触碰
