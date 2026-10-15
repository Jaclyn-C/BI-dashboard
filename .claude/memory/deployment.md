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

## 生产落地（2026-10-15，傻瓜式部署基建）

一键流程与购买建议见 `docs/deployment/部署指南.md`（香港轻量服务器 + 便宜域名，约 25 元/月）。

- **形态**：单机 `compose.prod.yaml` = postgres:16-alpine（不映射端口，仅内网）+ api（`backend/Dockerfile`，启动即 `alembic upgrade head`，单 worker——调度器是进程内协程，多 worker 会重复同步）+ web（`frontend/Dockerfile` 多阶段：pnpm build → caddy:2-alpine 托管 dist）
- **HTTPS/路由**：Caddy（`deploy/Caddyfile`），域名来自 `.env` 的 `DOMAIN`，自动签证书；`/api/*、/healthz、/docs*、/redoc*、/openapi.json` 反代 api:8000，其余走 SPA 回退
- **配置**：服务器 `/opt/partner-dashboard/.env`（模板 `.env.prod.example`）；`deploy/setup-server.sh` 首跑自动生成 SECRET_KEY / ORDER_FILTER_SALT / POSTGRES_PASSWORD（后两者永不可换）；DATABASE_URL 由 compose 覆盖指向内网 postgres，不读 .env 里的值
- **部署/升级同一条命令**：本地 `bash deploy/deploy.sh root@IP`（tar 走 ssh，排除 .env/data/.claude 等；服务器 .env 与数据卷不受影响）
- **备份**：`deploy/backup.sh`（pg_dump gzip 到 backups/，留 14 份），指南 §6 有 crontab 配法
- 坑：pnpm 12 在干净环境会拦 esbuild 安装脚本，镜像内用 `pnpm install --frozen-lockfile --allow-build=esbuild`；Dockerfile 基础镜像保持官方源（香港服务器直连无碍），国内本机构建可用镜像源拉取后 retag
- 方案 B（按量随用随开，阿里云节省停机模式）见 `docs/deployment/按量开关部署手册.md` + `deploy/teardown.sh`（月末备份下载后释放实例）；复用本方案全部命令，`DOMAIN` 可填 `http://<EIP>` 走明文 80（已实测）
