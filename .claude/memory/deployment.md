# 部署知识（deployment）

> 目标：公网服务器部署，供应商经公网调用下游 API。首次实际部署后由负责 Agent 补充实测细节。

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
