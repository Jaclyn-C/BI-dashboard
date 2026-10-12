# 架构知识（architecture）

> 由 architect-agent / 各 Agent 维护：现状 + 决策记录。

## 总体架构（2026-10-12 定稿）

```
上游 API ──→ 同步任务(定时/手动, 幂等) ──→ PostgreSQL ──→ 看板 API ──→ React 看板
                                               ↓ 处理(筛选/分配/调整)
                                               └→ 供应商 API (API key + OpenAPI 文档)
```

三个能力域：**ingest**（数据接入）/ **dashboard**（内部看板）/ **supplier**（下游供给）。

## 技术栈（已定，变更需用户确认）

- 后端：Python 3.12+ / FastAPI / httpx / SQLAlchemy 2 / Alembic / PostgreSQL 16 / pytest / ruff / pydantic-settings（.env）
- 前端：React 18 / Vite / JavaScript（**非 TS**）/ pnpm / eslint
- 部署：Docker Compose（api + postgres + 反向代理 HTTPS），目标公网（见 deployment.md）

## 目录

见 CLAUDE.md 第 3 节。**代码尚未初始化**——首次开发由 architect-agent 出初始化 DESIGN（backend 脚手架 + Alembic 初始化 + frontend 脚手架）。

## 关键决策记录

| 日期 | 决策 | 理由 |
|---|---|---|
| 2026-10-12 | PostgreSQL（否决 SQLite / 无 DB 纯透传） | 供应商公网并发调用、金额审计、外网部署备份 |
| 2026-10-12 | 前端 JS（否决 TS） | 项目体量与用户偏好 |
| 2026-10-12 | 上游调用收进后端（原 HTML 是浏览器直连） | 解决 CORS + 凭据不暴露给浏览器 |
| 2026-10-12 | Alembic 是数据库变更唯一入口 | 迁移即代码，无需独立 database-agent |
| 2026-10-12 | agent team 6 角色（无 database-agent） | 迁移归 backend-agent；DB 复杂化后再拆 |
| 2026-10-12 | 参考实现 docs/reference/visualisation.html 凭据抹除后入库 | 行为规格可版本化，凭据走 .env |
