# 临时演示部署手册（按量付费 VPS，给外部的人看一眼）

> 场景：临时把看板部署到一台便宜的公网服务器，演示完销毁。
> 形态：Docker Compose 三容器——`api`（FastAPI）+ `postgres`（不出服务器）+ `caddy`（静态前端 + /api 反代）。
> 正式对外的生产部署（供应商 API、限流、备份）不走本手册，见 `.claude/memory/deployment.md` 规划。

## 0. 租服务器（约 ¥0.12/小时 + 流量 ¥0.8/GB）

腾讯云 https://console.cloud.tencent.com/cvm 或阿里云 ECS 按量付费，配置：

- 计费：**按量计费**；地域就近（广州/上海）
- 规格：**2 核 2G** 入门款；镜像：**Ubuntu Server 22.04**（系统盘 40G）
- 带宽：**按使用流量**，峰值拉满不影响费用
- 安全组：放行 **22（SSH）、80（HTTP）**，来源 0.0.0.0/0（部署完建议收紧，见 §5）

## 1. 服务器初始化（SSH 登录后执行一次）

```bash
ssh root@服务器IP

# Docker + compose 插件（官方脚本，Ubuntu 全版本通吃）
curl -fsSL https://get.docker.com | sh

# 大陆服务器拉不动 docker.io → 配镜像源（腾讯云机器优先用云内源，逐个回退）
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{"registry-mirrors": ["https://mirror.ccs.tencentyun.com", "https://docker.m.daocloud.io"]}
EOF
systemctl restart docker
```

## 2. 上传代码与配置

本机执行（在 partner-dashboard 仓库根目录）：

```bash
rsync -az --exclude node_modules --exclude .venv --exclude dist \
  --exclude data --exclude .git --exclude backend/.env \
  ./ root@服务器IP:/opt/partner-dashboard/
```

服务器上生成配置（两条 python 命令在服务器或有 python3 的机器上跑）：

```bash
cd /opt/partner-dashboard
cp .env.prod.example .env.prod
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # 填 SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(16))"   # 填两处数据库密码
vim .env.prod    # DATABASE_URL 与 POSTGRES_PASSWORD 的密码保持一致
```

## 3. 启动

```bash
docker compose --env-file .env.prod -f compose.prod.yaml up -d --build
docker compose -f compose.prod.yaml ps        # 三服务应 healthy/running
curl -s http://localhost/healthz              # {"status":...} 即通
```

浏览器访问 `http://服务器IP`。

## 4. 导入本地数据（朋友看到的与本机演示一致）

本机导出（dev 库是 compose.dev.yaml 那个容器）：

```bash
docker exec pd-dev-postgres pg_dump -U pd -d pd --no-owner --no-privileges \
  | gzip > /tmp/pd-demo.sql.gz
scp /tmp/pd-demo.sql.gz root@服务器IP:/tmp/
```

服务器导入：

```bash
# 先清空（仅重复导入时需要）：
docker compose -f compose.prod.yaml exec -T postgres \
  psql -U pd -d pd -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
# 导入：
gunzip -c /tmp/pd-demo.sql.gz | \
  docker compose -f compose.prod.yaml exec -T postgres psql -U pd -d pd
```

导入后演示账号 `admin@admin.com / admin123`（随库过来）即可登录。
新注册账号：验证码走日志——`docker compose -f compose.prod.yaml logs api | grep -i code`。

## 5. 收尾（重要）

- **安全组收紧**：把 80 端口来源改成你朋友的 IP（防弱密码被公网爆破）；22 也可限自己 IP
- 演示完：云控制台**销毁实例**（按量付费只关机仍扣磁盘/IP 保留费，销毁才停止计费）

## HTTPS（可选，二选一）

- **境外服务器 + sslip.io**：`.env.prod` 设 `SITE_ADDRESS=1-2-3-4.sslip.io`（按 IP 写），Caddy 自动签证书
- **tunnel profile（大陆服务器推荐）**：`docker compose --env-file .env.prod -f compose.prod.yaml --profile tunnel up -d`，
  `docker compose -f compose.prod.yaml logs cloudflared 2>&1 | grep -o 'https://.*trycloudflare.com'` 取地址（每次重启变化）

## 常见排查

| 症状 | 命令/原因 |
|---|---|
| 页面打不开 | `docker compose -f compose.prod.yaml logs caddy`；安全组 80 是否放行 |
| 登录 401/数据空 | 数据没导入（§4）；或 `DATABASE_URL` 密码与 `POSTGRES_PASSWORD` 不一致 |
| api 起不来 | `docker compose -f compose.prod.yaml logs api`；常见为 `.env.prod` 配置缺项 |
| 改了代码要更新 | 本机重新 rsync 后 `up -d --build` 重建 |
