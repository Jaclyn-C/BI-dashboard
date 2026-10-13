# Partner Dashboard

合作伙伴收益数据平台：上游 netshort CPS 取数落库 → 内部看板（React + FastAPI）→ 处理 → 下游供应商 API（规划中）。

## 新机器首次搭建（拉代码后从这里开始）

**前置：装好这三样**（都没有就先装）：

| 依赖 | 版本要求 | 安装方式 |
|---|---|---|
| Docker Desktop | 任意近期版 | https://www.docker.com/products/docker-desktop （数据库跑在里面） |
| Python | ≥ 3.12 | https://www.python.com （mac 自带的版本旧，建议 brew install python@3.12） |
| Node.js + pnpm | Node ≥ 18 | https://nodejs.com ；pnpm：`npm install -g pnpm` |

**五步初始化**（每个新克隆的机器执行一次）：

```bash
# 1. 克隆
git clone https://github.com/Jaclyn-C/BI-dashboard.git partner-dashboard
cd partner-dashboard

# 2. 后端：建虚拟环境 + 装依赖（读 pyproject.toml，无需手动装任何包）
cd backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"     # 只运行不开发可去掉 [dev]
cd ..

# 3. 前端：装依赖（读 package.json）
cd frontend && pnpm install && cd ..

# 4. 配置：复制模板并填关键项（此文件不进 git）
cp .env.example backend/.env
#    编辑 backend/.env：
#    - SECRET_KEY：跑 python3 -c "import secrets; print(secrets.token_urlsafe(32))" 生成填入
#    - UPSTREAM_CLIENT_ID/SECRET：上游凭据（没有则数据同步不启动，页面仍可看）

# 5. 建表：起数据库并执行迁移（生成 users 等表结构）
docker compose -f compose.dev.yaml up -d
cd backend && .venv/bin/alembic upgrade head && cd ..
```

> 项目**不需要任何 Docker 镜像推送**：唯一用到的镜像是官方公共镜像 `postgres:16`，第 5 步会自动拉取。应用本身从源码运行（Python venv + pnpm），不在容器里。

完成后再按下面「快速启动」起服务。新库是空的——填了上游凭据的话，后端启动后自动回填最近 92 天数据（2~5 分钟）。

## 快速启动（本地开发）

三个终端按顺序启动：数据库 → 后端 → 前端。

### ① 数据库（PostgreSQL，Docker）

```bash
cd partner-dashboard
docker compose -f compose.dev.yaml up -d      # 首次会自动拉镜像；已启动则秒过
```

停止：`docker compose -f compose.dev.yaml down`（数据存在卷里，不会丢）

### ② 后端（FastAPI，端口 8000）

```bash
cd partner-dashboard/backend
.venv/bin/uvicorn app.main:app --port 8000
```

- 启动后若 `backend/.env` 配了上游凭据，会自动开始数据同步（每 30 分钟 + 首次回填 92 天）
- 验证码：SMTP 已配则发邮件；未配时打印在**这个终端的日志里**（搜 `code=`）
- 停止：终端里 `Ctrl + C`
- API 文档：http://localhost:8000/docs

### ③ 前端（React + Vite，端口 5173）

```bash
cd partner-dashboard/frontend
pnpm dev
```

- 打开 http://localhost:5173（若 5173 被占，vite 自动换 5174/5175，看终端输出的地址）
- 停止：终端里 `Ctrl + C`

### 账号

- 自助注册（邮箱验证码）或用已有账号
- 演示账号：`admin@admin.com` / `admin123`

## 公网演示隧道（Cloudflare Tunnel）

作用：不开部署、不用服务器，把本机跑着的看板临时暴露到公网，给外部的人看。
**这是演示环境：Mac 必须开机（合盖/睡眠链接即断），别人要看提前说一声，跑一下下面命令。**

```bash
./start-demo.sh    # 一键：数据库→后端→前端→隧道，输出公网地址（每次地址随机）
./stop-demo.sh     # 一键关闭：隧道+前端+后端（数据库保留，数据不丢）
```

- 演示账号随脚本输出一起给出（admin@admin.com / admin123）
- 手动单开隧道：`/opt/homebrew/opt/cloudflared/bin/cloudflared tunnel --url http://localhost:5173`
- 没装 cloudflared 的话先装：`brew install cloudflared`

## 常用排查命令

```bash
# 看哪些服务在跑（Python=后端 8000 / node=前端 5173 / com.docke=数据库 5432）
lsof -i -P | grep LISTEN

# 断掉后端 / 前端（按端口杀，端口空了就没输出）
lsof -ti:8000 | xargs kill
lsof -ti:5173 | xargs kill

# 看数据库里有什么表 / 多少订单
docker exec pd-dev-postgres psql -U pd -d pd -c '\dt'
docker exec pd-dev-postgres psql -U pd -d pd -c 'SELECT count(*) FROM orders;'

# 手动触发全量数据同步（起后端后，任意已登录用户的 token）
curl -X POST http://localhost:8000/api/v1/dashboard/sync \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"from":"2026-08-05","to":"2026-10-13"}'
```

## 项目导航

| 入口 | 说明 |
|---|---|
| `CLAUDE.md` | Agent 总规则（技术栈、规范、13 条红线） |
| `.claude/agents/` | 6 个角色定义：product / architect / backend / frontend / test / reviewer |
| `.claude/workflows/` | requirement / development / review 三条工作流 |
| `.claude/memory/` | 项目知识库（业务口径、上游 API 事实、架构、部署） |
| `docs/reference/visualisation.html` | 参考实现（行为规格，凭据已抹除） |
| `docs/reference/上游CPS开放API文档-v1.2.0.md` | 上游飞书文档全文还原 + 我方实测补充（上游客户端实现依据） |
| `docs/requirements/`、`docs/design/` | 需求（REQ）与设计（DESIGN）文档 |
| `tools/export_diff.py` | 新旧系统 CSV 逐单对账脚本 |

## 配置说明

所有配置在 `backend/.env`（本地文件，**不进 git**）；模板见根目录 `.env.example`（每个键有注释）。要点：

- 上游凭据 `UPSTREAM_CLIENT_ID/SECRET`：留空则同步调度器不启动
- SMTP（163 邮箱）：`SMTP_HOST=smtp.163.com` + `SMTP_PORT=465` + `SMTP_SSL=true` + 授权码（不是邮箱密码）
- 同步频率：`SYNC_INTERVAL_MINUTES`（默认 30）、回看窗口 `SYNC_LOOKBACK_DAYS`（默认 3）

## 测试与质量

```bash
cd backend && .venv/bin/ruff check . && .venv/bin/python -m pytest   # 194 个测试
cd frontend && pnpm lint && pnpm build                                # lint + 构建
```
