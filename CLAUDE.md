# CLAUDE.md — Partner Dashboard 数据平台 总规则

> 本文件是所有 Agent 在本仓库工作的总规则。详细知识见 `.claude/memory/`（business / api / architecture / deployment / coding-standard）。Agent 定义见 `.claude/agents/`，协作流程见 `.claude/workflows/`。
> **双文件镜像**：仓库根的 AGENTS.md 与 CLAUDE.md 内容完全一致——修改任一个后，必须将同一修改同步到另一个（整文件复制即可）。

## 1. 项目介绍

合作伙伴收益数据平台（Partner Dashboard）：把单文件 HTML 看板（`docs/reference/visualisation.html`，行为规格）重构为前后端分离系统，并扩展「处理 → 供给下游」链路。

**一手资料（改业务逻辑前必读）**：`docs/research/01-调研发现与逆向分析.md`（遗留系统逆向 + 过滤规则数据分析）、`docs/planning/02-重构计划与待确认清单.md`（目标架构、A/B 清单、分阶段计划）。

核心业务链路：

```
上游 netshort CPS API（飞书文档 v1.2.0 的 8 个接口，当前只用 3 个）
        ↓（新系统运行时唯一出站依赖）
同步任务落库 → 内部看板（React）
        ↓ 处理（筛选/分配/调整）
下游供应商 API（API key 鉴权 + OpenAPI 文档）
```

⚠️ 两个关键事实：

- **前开发自建后端（api.tfctechnology.com）代码已遗失，运行时禁止依赖**——其 `/auth/login` 与 `/data/partner/order/report` 由我方重写；仅 Phase 0 数据记录器临时调用它留存分类标签真值（见 planning/02）。
- **订单分类规则（20%/70% 归属）是黑盒**：统计分析确认其依赖两边接口都不暴露的隐藏属性（确定性、约 80/20、与退款相关，见 research/01 §5）。分类器必须做成可插拔；规则确认（B1）前**不得猜测实现、不得对外输出分类金额**。

三个能力域：

- **数据接入（ingest）**：定时/手动从上游拉取订单与广告收益，落 PostgreSQL
- **内部看板（dashboard）**：重构 HTML 的全部功能——时间范围/数据集筛选、KPI、每日收益、新旧美元口径对比、国家分布、订单明细、CSV 导出、EN/中文双语、深色模式
- **下游供给（supplier）**：处理后的订单数据按供应商隔离供给，配 API key 与接口文档

**参考实现即规格**：`docs/reference/visualisation.html` 是现有行为的唯一参照（凭据已抹除）。任何口径变更（分成比例、汇率、聚合规则、数据集定义）必须先走需求流程（`.claude/workflows/requirement-flow.md`），不允许实现时"顺手"改口径。

## 2. 技术栈

**后端** `backend/`：Python 3.12+、FastAPI、httpx（上游调用）、SQLAlchemy 2 + Alembic（迁移）、PostgreSQL 16、pytest、ruff。配置走 pydantic-settings + `.env`（模板 `.env.example`，`.env` 永不入库）。

**前端** `frontend/`：React 18 + Vite + JavaScript（**不是 TS**）、pnpm、eslint。图表方案等具体依赖由 DESIGN 文档定。

**部署**：Docker Compose（api + postgres + 反向代理），目标公网服务器，HTTPS + API key。详见 `.claude/memory/deployment.md`。

## 3. 项目目录说明

```
partner-dashboard/
├─ CLAUDE.md                        ← 本文件（Agent 总规则）
├─ .claude/
│  ├─ agents/                       ← 6 角色：product/architect/backend/frontend/test/reviewer
│  ├─ workflows/                    ← requirement / development / review 三条流程
│  └─ memory/                       ← 项目知识库（Agent 边干边维护）
├─ docs/
│  ├─ reference/visualisation.html  ← 参考实现（行为规格，凭据已抹除，禁止删除）
│  ├─ research/                     ← 遗留系统调研与逆向分析（一手资料）
│  ├─ planning/                     ← 重构计划与待确认清单（一手资料）
│  ├─ requirements/REQ-*.md         ← 需求文档
│  └─ design/DESIGN-*.md            ← 技术方案与任务包
├─ tools/                           ← 对账/验收脚本（export_diff.py 等）
├─ data/                            ← 本地数据分析集（真实业务数据，gitignore 不入库）
├─ backend/                         ← FastAPI
│  ├─ app/
│  │  ├─ config.py                  ← pydantic-settings（读 .env）
│  │  ├─ db.py                      ← engine / session
│  │  ├─ models/                    ← SQLAlchemy 模型（变更必须配 Alembic 迁移）
│  │  ├─ schemas/                   ← Pydantic 入出参
│  │  ├─ api/                       ← 路由：dashboard（内部）/ supplier（下游）/ auth
│  │  ├─ services/                  ← 业务逻辑：分成/汇率/聚合/处理
│  │  └─ upstream/                  ← 上游客户端与同步任务（OAuth2、时间窗二分）
│  ├─ alembic/                      ← 迁移脚本（数据库变更唯一入口）
│  └─ tests/
└─ frontend/                        ← React + Vite + JS
   └─ src/
      ├─ api/                       ← 统一请求层（唯一出口）
      ├─ pages/                     ← 页面
      ├─ components/                ← 可复用组件
      └─ i18n/                      ← en / zh
```

## 4. Ponytail 基线（前后端通用）

代码生成与代码审查一律按 Ponytail（懒高级开发者基线）执行——最小完整变更、优先复用既有实现、不加没人要的抽象/选项/配置、无死代码与魔法值、新增非平凡逻辑配一条最小测试；环境里有 ponytail skill 时直接调用，没有则按本条自查。

## 5. 后端开发规范

- 分层：`api/`（路由，薄）→ `services/`（业务逻辑）→ `models/`（ORM）；上游调用只出现在 `upstream/`，禁止在路由里直接 httpx。
- **金额纪律**：一切金额/汇率计算用 `decimal.Decimal`，数据库列用 `Numeric`，**禁止 float**。前端不做金额运算，只渲染后端给定的值。
- **上游集成**：OAuth2 token 缓存复用（过期再取）；时间窗超 100 行上限按参考实现二分策略（最大深度 6）拆分拉取；同步任务幂等（重跑不产生重复数据）。
- **数据库变更唯一入口是 Alembic**：改模型必须 `alembic revision --autogenerate` 生成迁移并人工检查；禁止手写 SQL 改库、禁止改了模型不生成迁移。
- API 路径加版本前缀：内部 `/api/v1/dashboard/**`，下游 `/api/v1/supplier/**`；下游接口必须 API key 鉴权 + 按供应商隔离数据。
- 错误处理：上游不可用时降级（返回已落库数据 + 状态标记），不允许 500 裸奔。
- 验证义务：改动后至少 `ruff check .` + `pytest`（能跑的范围），结果如实报告。

## 6. 前端开发规范

- **沿用 JS**（非 TS）；函数组件 + hooks；页面放 `src/pages/`，可复用 UI 放 `src/components/`。
- 请求统一走 `src/api/` 封装的 client，禁止组件内裸 fetch/axios 散落。
- **i18n**：用户可见文案必须走 i18n（en/zh 两个 locale 同步），禁止硬编码文案。
- **深色模式**：跟随系统 `prefers-color-scheme`，颜色一律用 CSS 变量（参考 HTML `:root` 变量表是迁移底稿）。
- 图表实现选型（自绘 SVG vs 图表库）由 DESIGN 文档定；定了之后同类图表不混用两套方案。
- **极简风格，禁止图标**：不引入任何图标库（react-icons / lucide / 组件库 icons 等），不使用 emoji 作为界面元素；视觉表达靠文字、排版与留白，风格对标参考 HTML。复刻参考实现既有控件时，其中的文本字形（↻ ✓ ↓ 等）可原样保留，不得新增。
- 验证义务：改动后至少 `pnpm lint`；涉及构建配置时 `pnpm build`。

## 7. 下游供应商接口规范

- 鉴权：每供应商独立 API key，数据按供应商隔离——A 绝不可能看到 B 的数据（reviewer 重点检查项）。
- 契约稳定：已发布的下游接口入出参只加不破（向后兼容）；破坏性变更走 `/api/v2`。
- 接口文档：FastAPI 自动生成的 OpenAPI（`/docs`）即对外文档，tag/描述要写清楚——这是给供应商看的东西。

## 8. Git 规范

- **禁止直接在 main/master 上开发**：任何变更先建 `feature/<REQ编号>-<简述>` 分支（如 `feature/REQ-20261012-01-supplier-api`），提交前走 review-flow。
- 提交信息 `type(scope): 中文描述（REQ 编号）`，scope ∈ `api`（后端）/ `web`（前端）/ `db`（迁移）/ `ai`（agent 配置与 memory）/ `docs`；一次提交聚焦一件事，跨前后端拆开提交。
- 禁止提交：`.env`、`node_modules/`、`dist/`、`__pycache__/`、`.venv/`、`.claude/settings.local.json`、数据库备份文件。
- 远端仓库：GitHub `Jaclyn-C/BI-dashboard`（用户创建并授权的**受控远端**，2026-10-12 起）。**推送时机：每个功能经用户验证确认后**由主对话执行 push，review-flow 之外不推。
- 历史版本中出现过真实凭据（已全部抹除并重写历史）——**任何残留凭据外泄都是事故**；除上述受控远端外严禁推送任何其他仓库。

## 9. Agent 协作规则

- **知识优先**：接任务先查 `.claude/memory/` 对应文档；发现 memory 与代码/现实不符时，以现实为准并更新 memory。
- **口径变更走流程**：分成比例、汇率口径、聚合规则、数据集定义的任何变更，必须有对应 REQ 文档；reviewer 见到"无 REQ 的口径变更"直接 blocker。
- **并行分工**：backend-agent 只动 `backend/**`，frontend-agent 只动 `frontend/**`，靠目录所有权防冲突（见 development-flow）。
- **如实报告**：验证报告必须区分 已验证 / 未验证（附原因）；禁止把未验证项写成通过。
- **不确定即问**：涉及对外契约（下游接口）、凭据管理、部署的改动，先向用户确认。

## 10. 禁止事项

1. **禁止**在代码、配置、日志、迁移、提交中出现真实凭据（上游 OAuth 凭据、数据库密码、供应商 API key、测试账号密码）——一律 `.env`，模板进 `.env.example`。
2. **禁止**改动业务口径（分成/汇率/聚合/数据集定义）而不走需求流程。
3. **禁止**用 float 做金额运算或存储；禁止前端计算金额。
4. **禁止**绕过 `src/api/` 直接发请求；禁止组件里硬编码 API 地址。
5. **禁止**改了 SQLAlchemy 模型不生成 Alembic 迁移；禁止手改数据库不留迁移。
6. **禁止**硬编码用户可见文案（必须 i18n，en/zh 同步）。
7. **禁止**供应商数据越权（下游任何查询必须带供应商维度过滤）。
8. **禁止**删除或"清理" `docs/reference/visualisation.html` 与 `.claude/` 配置。
9. **禁止**直接在 main 上提交开发变更；禁止 `--no-verify`、强推主干。
10. **禁止**跳过验证义务（对应侧 ruff/pytest/eslint 至少跑一次并如实报告）。
11. **禁止**在运行时调用前开发自建后端（api.tfctechnology.com）作为依赖（仅 Phase 0 数据记录器例外）；新系统出站只允许调飞书文档内的 8 个上游接口。
12. **禁止**在分类规则确认（planning/02 B1）前用猜测规则实现订单分类器，或对外输出 20%/70% 分类金额——宁出全量视图，不出错误的钱。
13. **禁止**引入图标库或以 emoji 作为界面图标——前端走极简文字风格（对标参考 HTML，详见第 6 节）。
