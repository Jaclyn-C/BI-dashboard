# 部署知识（deployment）

> 目标：公网服务器部署，供应商经公网调用下游 API。已上线（2026-10-17），实测细节见文末「首次上线实测」。

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

一键流程与购买建议见 `docs/deployment/按量开关部署手册.md`（2026-10-17 起唯一操作手册：方案 B 阿里云按量 + 节省停机 + EIP 纯 IP，月 ¥10-25；原《部署指南》的共用部署段已并入手册，《部署实现记录》已删，选型依据见《部署选型记录.md》）。

- **形态**：单机 `compose.prod.yaml` = postgres:16-alpine（不映射端口，仅内网）+ api（`backend/Dockerfile`，启动即 `alembic upgrade head`，单 worker——调度器是进程内协程，多 worker 会重复同步）+ web（`frontend/Dockerfile` 多阶段：pnpm build → caddy:2-alpine 托管 dist）
- **HTTPS/路由**：Caddy（`deploy/Caddyfile`），域名来自 `.env` 的 `DOMAIN`，自动签证书；`/api/*、/healthz、/docs*、/redoc*、/openapi.json` 反代 api:8000，其余走 SPA 回退
- **配置**：服务器 `/opt/partner-dashboard/.env`（模板 `.env.prod.example`）；`deploy/setup-server.sh` 首跑自动生成 SECRET_KEY / ORDER_FILTER_SALT / POSTGRES_PASSWORD（后两者永不可换）；DATABASE_URL 由 compose 覆盖指向内网 postgres，不读 .env 里的值
- **部署/升级同一条命令**：本地 `bash deploy/deploy.sh root@IP`（tar 走 ssh，排除 .env/data/.claude 等；服务器 .env 与数据卷不受影响）
- **备份**：`deploy/backup.sh`（pg_dump gzip 到 backups/，留 14 份），手册 §5 有 crontab 配法
- 坑：pnpm 12 在干净环境会拦 esbuild 安装脚本，镜像内用 `pnpm install --frozen-lockfile --allow-build=esbuild`；Dockerfile 基础镜像保持官方源（香港服务器直连无碍），国内本机构建可用镜像源拉取后 retag
- 方案 B（按量随用随开，阿里云节省停机模式）见 `docs/deployment/按量开关部署手册.md` + `deploy/teardown.sh`（月末备份下载后释放实例）；复用本方案全部命令，`DOMAIN` 可填 `http://<EIP>` 走明文 80（已实测）

## 首次上线实测（2026-10-17，杭州 ecs.e-c1m1.large + EIP）

- **线上地址**：`http://114.55.107.28`（纯 IP 明文 HTTP，Caddy 以 :80 监听，验证过 healthz/SPA/OpenAPI/静态资源全通）；crontab 04:10 每日备份已配，`backups/pd-2026-10-17.sql.gz` 验证可产出
- **上线即回填**：启动后调度器自动拉上游订单，几分钟内入库 2.4 万行——上游凭据/调度器生产可用
- **国内节点四个坑（setup-server.sh 已内置前三项的兜底）**：
  1. Docker Hub 直连超时 → 从 `docker.m.daocloud.io/library/<img>` 拉取后 retag（daocloud 偶发卡死，重启拉取即恢复；终极兜底：本机拉好 `docker save | gzip | ssh 'gunzip | docker load'`）
  2. Apple Silicon 本机拉镜像默认 arm64，传到 x86 服务器 `exec format error`——本机操作必须 `--platform linux/amd64`
  3. `PIP_INDEX_URL` 加在本机 deploy.sh 上无效（compose 在服务器执行，env 过不了 ssh）——须在服务器侧设，或用脚本内置的探测回退；清华源对该机 403，阿里云 PyPI（mirrors.aliyun.com/pypi/simple）最快
  4. Caddy 站点按 Host 匹配：`DOMAIN=http://<EIP>` 时本机 curl 127.0.0.1 不命中站点——探测须带 `-H "Host: <EIP>"`
- `.env.prod.example` 的 DOMAIN 模板值必须留空——占位域名会绕过首跑必填检查（已修）
