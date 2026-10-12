# 架构知识（architecture）

> 由 architect-agent / 各 Agent 维护：现状 + 决策记录。

## 总体架构（2026-10-12 定稿，模块划分详见 docs/planning/02 §1）

```
供应商 / 看板前端 ──HTTPS──→ 新后端（我方自研）
  ① 鉴权服务（重写 /auth/login，邮箱账号体系，REQ-20261012-01）
  ② 上游客户端（OAuth 换票/缓存/续期；窗口化拉单 + 二分补全）
  ③ 订单接入管道（全量拉取 → 规范化 → 落库）
  ④ ★分类器 classify(order) → included|excluded（可插拔，规则 = B1 待确认）
  ⑤ 报表服务（重写 order/report，真分页）
  ⑥ 广告收入代理（adSummary 服务端代理）
  ⑦ 聚合/结算引擎（20/70 分成、按日/币种/国家聚合）
  ⑧ 数据记录器（Phase 0：双源留档分类标签真值）
                        │ 唯一出站依赖
                        ▼
             上游 netshort CPS（8 接口，当前用 3 个）
```

**分类器 ④ 是全系统唯一的"缝"**：其余模块只依赖「订单 + 分类标签」，不关心分类怎么来的。分阶段计划（Phase 0 记录器 → Phase 1 A 清单并行 → Phase 2 规则接入与切换）与 A/B 清单见 `docs/planning/02-重构计划与待确认清单.md`。

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
