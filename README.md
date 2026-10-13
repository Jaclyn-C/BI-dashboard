# Partner Dashboard

合作伙伴收益数据平台：上游 netshort CPS 取数落库 → 内部看板（React + FastAPI）→ 处理 → 下游供应商 API（规划中）。

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
**前提：前后端已按上面启动，Mac 保持开机不合盖。**

开一个新终端，执行：

```bash
/opt/homebrew/opt/cloudflared/bin/cloudflared tunnel --url http://localhost:5173
```

- 输出里的 `https://xxxxx.trycloudflare.com` 就是公网访问地址（每次启动都不同），发给对方即可
- **关闭隧道：在这个终端按 `Ctrl + C`**（地址随之失效）
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
