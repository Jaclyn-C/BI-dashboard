# DESIGN-20261012-02 看板重构（上游接入 + 聚合引擎 + 前端看板）

| 项 | 值 |
|---|---|
| 对应 REQ | REQ-20261012-02（定稿，93 AC + D1–D16 默认值） |
| 日期 / 作者 | 2026-10-12 / architect-agent |
| 状态 | **可开发**——RQ-1~7 已决议（2026-10-12 用户拍板，§8.2）；reviewer 评审意见 M1+m1~m12 已修复（修订记录见文末） |
| 能力域 | ingest（A1/A2/A5/A6）+ dashboard（A7/A8/A9）；supplier 域无改动 |
| 分支 | `feature/REQ-20261012-02-dashboard`（前后端同分支、按 scope 拆提交） |
| 一手依据 | `docs/reference/visualisation.html`（行为规格，行号引用记作 HTML:xxx）、`docs/reference/上游CPS开放API文档-v1.2.0.md`、`docs/planning/02` A 清单、REQ D1–D16 |
| 现状勘察 | backend/app/（auth 已落地，本设计向其分层与风格看齐）、backend/alembic 0001 基线、frontend/src/（client/auth/i18n/theme.css 已就绪） |

**红线自查索引**：金额全链路 Decimal/Numeric（§2.5、§4.2）；口径零猜测（§4 全部照搬 HTML 算法，差异处显式登记）；禁图标 emoji（§6.5，仅保留 HTML 既有文本字形）；TS 禁用（§6 全 JS）；出站只调 3 个上游接口（§3.1.4）；B1 分成零输出（§4.3、§5 各响应含 null 契约）。

---

## 1. 方案总览

### 1.1 模块归属与分层

```
React 看板（DashboardPage，替换占位）
   │  /api/v1/dashboard/**（Bearer，全部登录墙后）
   ▼
FastAPI
   api/v1/dashboard.py（薄路由）
        │
        ├─ services/aggregation.py    ★A7 聚合（Decimal，summary 全口径）
        ├─ services/csv_export.py     ★A9 CSV（流式）
        ├─ services/sync_service.py   ★A2 接入管道（幂等 upsert / sync_runs / 覆盖自愈）
        ├─ services/classifier.py     ★A6 可插拔分类器（空实现，class 恒 None）
        ├─ services/share_service.py  ★分成能力（配置化，B1 不接任何输出路径）
        ├─ upstream/client.py         ★A1 OAuth 客户端（换票/缓存/60s 提前刷新/401 单次重试）
        ├─ upstream/fetcher.py        ★A1 窗口化拉取 + 二分补全；A5 adSummary
        └─ upstream/scheduler.py      ★定时任务（lifespan 启动，30min + 覆盖自愈 + 手动插队）
        │
   models: orders / ad_revenue_daily / sync_run（迁移 0002，接 0001 之后）
   ▼
PostgreSQL 16  ←→  上游 netshort CPS（仅 /open/oauth2/token、/open/order/list、/open/order/adSummary）
```

- 上游 HTTP 只出现在 `app/upstream/`；聚合/导出只读库（看板一律不穿透上游，D14）。
- 复用既有件：`get_current_user` 鉴权依赖、`ApiError` 错误信封、`get_db` 会话依赖、lifespan 装配模式、前端 `client.js`/`AuthProvider`/i18n/theme.css。
- 挂载点：`app/api/v1/__init__.py` 预留的 dashboard 行启用（`api_router.include_router(dashboard.router)`）。

### 1.2 端到端数据流

1. **定时**：lifespan 启动调度协程 → 每 30 分钟（D1）跑一次同步：重拉最近 3 天（D2）订单+广告；发现 92 天（D3）覆盖缺口则自动补（首次部署即自动回填，无需人工）。
2. **手动**：↻ → `POST /dashboard/sync {from,to}` → 插队执行当前区间同步（D4）→ 前端轮询 `GET /sync/status` → 完成后重拉 summary。
3. **读路径**：看板打开 → `GET /dashboard/summary`（一次装载全看板，对标 HTML「一次 loadRange 全页 derive」）→ 订单表分页另走 `GET /dashboard/orders`；CSV 走 `GET /dashboard/orders.csv`。
4. **降级**：上游失败/广告失败/截断 → 库内数据照常返回 + `meta` 状态标记 → 前端横幅/状态行呈现（AC-S5/S7/S9），永不 500 白屏。

### 1.3 关键选型决策（8 条，含理由与备选）

| # | 决策点 | **定案** | 理由 | 落选备选 |
|---|---|---|---|---|
| S1 | 图表实现 | **自绘 SVG 组件**（移植 HTML 的 columnPath/barPathH/donutArc/niceCeil/axisMoney，约 4 个组件 + 1 个工具模块） | ① 零新依赖（pnpm 无新增包）；② 像素级复刻参考实现（柱顶 4px 圆角、段间 2px 缝、十字准线、键盘可达 hit-rect、$K 轴缩写）；③ 本项目图表有大量**非默认**需求——双卡共享 y 轴上限（AC-E2）、aria-label 含合计（AC-V4）、切片键盘聚焦 tooltip、CSS 变量配色随明暗切换——图表库（Recharts/ECharts/Chart.js）每一项都要逃逸口，样式覆写成本 > 自写成本；④ 库的默认渐变/动画/字体与极简规范冲突，reviewer 逐条验 AC 反而更难 | Recharts（+1.5MB 级依赖、默认风格需全面覆写）；ECharts（更重）；chart.js+d3 混用（违「同类图表不混用两套」） |
| S2 | 定时同步机制 | **FastAPI lifespan 启动 asyncio 循环任务**；同步管道本体为同步代码，经 `asyncio.to_thread` 执行（DB 是同步 SQLAlchemy，不阻塞事件循环）；单飞 `threading.Lock` 防并发重入 | ① 零依赖；② 单进程部署（compose：api+postgres+proxy，单 uvicorn）下最简可靠；③ 手动刷新天然用 `asyncio.create_task(to_thread(...))` 插队；④ 优雅停机 = cancel task | APScheduler 3/4（多一个依赖与线程模型，只用得上「固定间隔」一个功能，版本迁移成本白付）；外部 cron/systemd timer（部署耦合，dev 环境不可用） |
| S3 | 数据模型 | `orders`（uq order_id 幂等键）+ `ad_revenue_daily`（date 主键幂等）+ `sync_runs`（运行记录含 truncated_dates JSONB），金额列全 `Numeric`，详见 §2 | 见 §2 各表理由 | 无缝表（power BI 直读）——过度设计 |
| S4 | 聚合策略 | **Python 内存聚合**（一次载入区间订单行 → Decimal 聚合出 summary 全部口径） | ① 92 天量级评估：实测 14 天 6,016 单 → 92 天 ≈ 4.0 万行，元组载入 + Decimal 聚合 < 100ms，内存 < 50MB；② summary 需要 7 种口径（毛额/旧美元/新美元/按日/按币种/按国家/对比表），SQL 要写 7 组 GROUP BY 且 Decimal 精度经 psycopg 驱动往返，Python 一次遍历全部产出且精度路径单一；③ 与 HTML derive() 逐行对照可审计（对账友好）；④ 重估阈值：区间行数 > 50 万或出现 supplier 并发读时再迁 SQL/预聚合表（风险项登记） | 纯 SQL 聚合（视图多、口径散、难逐条对标 HTML）；物化视图（无刷新调度收益，30min 同步节奏下无必要） |
| S5 | CSV 组装位置（D16） | **后端流式生成**（`StreamingResponse` + 生成器，UTF-8 BOM 首块、CRLF、防注入、babel 本地化国家名） | ① 金额两位小数量化在后端 Decimal 完成，前端不出现任何 `toFixed`（AC-X3 + 金额纪律的最强形态）；② 92 天 4 万行级导出流式输出不占前端内存（前端 blob 中转 ~6MB 可接受，但不该承担拼装）；③ 页面与 CSV 同源同格式化（AC-X5 由同一服务层保证）；④ 未来 supplier 导出可复用同一服务。**代价**：后端需 CLDR 区域名（引 `babel>=2.16`，纯 Python、CLDR 数据随包；RQ-1 已决议引入） | 前端组装（复用页面 Intl 不引新依赖，但金额格式化回前端、全量行需额外端点、与金额纪律精神相悖） |
| S6 | 降级数据形状（D7/D8 字段级） | **键保留、值 null** + 顶层 `degraded.share_rules_pending: true` 常驻标志；CSV 三列表头保留值留空 | ① 响应形状稳定（前端/契约测试可断言键存在），null 语义明确=「不可用」而非「零」；② 前端把 null 统一映射为占位 `–` + 「待规则确认」标注（§6.8 有逐卡清单）；③ 规则接入后同键出值，前端零结构改动（AC-CL3） | 缺省键（形状漂移，测试与前端都要双分支）；值 0（危险：0 是合法金额语义，违「宁不出错钱」） |
| S7 | 手动刷新机制 | 复用同步任务：`POST /sync` 触发（区间参数服务端钳制）→ 202 立返 + `GET /sync/status` 1s 轮询（含「a/b 天」进度，对齐 AC-S1 loadingDays）→ idle 后前端重拉 summary；运行中重复点击 accepted=false 不报错 | 同步逻辑单一实现（定时/手动/回填同管道），进度状态自然暴露；HTTP 202 语义准确（异步已受理） | WebSocket/SSE 推进度（30 分钟级任务+天数粒度进度，轮询足够，复杂度不值）；同步阻塞请求直到完成（92 天区间可能分钟级，必超时） |
| S8 | 前端状态管理 | **纯 hooks + 现有 Context**：会话沿用 AuthProvider；看板数据自写 `useSummary`/`useOrders`/`useSyncStatus` 三个轻量 hook（含 loading/error/reload），无新状态库 | 数据流简单（单页、5 个端点、无跨页共享），现有代码即此风格；CLAUDE 前端规范禁重库 | React Query（+依赖，本项目的加载/错误语义要自定义横幅与 dim，抽象反而碍事）；Redux/Zustand（纯增重） |

---

## 2. 数据模型与迁移

### 2.1 `orders`（新表）

| 列 | 类型 | 约束/默认 | 说明 |
|---|---|---|---|
| id | BigInteger | PK, Identity | 代理键（对齐 users 风格） |
| order_id | String(64) | NOT NULL, **UNIQUE `uq_orders_order_id`** | 上游 orderId。**幂等键**：upsert 冲突目标（AC-S3/U3） |
| create_time | String(32) | NOT NULL | 上游原值（`YYYY-MM-DD HH:mm:ss`），**零换算存储**（D6/AC-S8）。字符串字典序=时间序（HTML tableRows 同样按字符串排序） |
| create_date | Date | NOT NULL | 派生列（入库时 `create_time[:10]`），日界=原值日期部分（对标 HTML `slice(0,10)`）。区间查询/按日聚合均走此列 |
| theater_id / chapter_id | String(64) | NOT NULL | 上游透传（空串兜底） |
| language | String(16) | NULL | 如 `en_US`；国家推断输入 |
| currency_type | String(8) | NOT NULL | ISO 币种码 |
| amount_minor | **Numeric(18,4)** | NOT NULL | 原币金额·最小单位（AC-U3），原值精度无损（scale 4 容忍异常小数） |
| usd_order_amount_minor | **Numeric(18,4)** | NULL | 上游 `orderAmount` 规范名（usdOrderAmount 语义），缺失=NULL → 新口径排除+计数（AC-AG3） |
| refund_time | String(32) | NULL | 上游原值；空白=NULL |
| is_returned | Boolean | NOT NULL default false | 入库时派生：`refund_time` 非空白（HTML isReturned 同规则）。便于筛选/索引 |
| promotion_code | String(64) | NULL | 上游透传 |
| order_class | String(16) | NULL, CHECK IN ('included','excluded') | **B1 恒 NULL**（分类器空实现写入）。CHECK 为 B1 恢复预留，无索引（恢复时按需加） |
| created_at / updated_at | DateTime(tz) | server_default now() / onupdate | 审计字段（对齐 users） |

索引：`uq_orders_order_id`（幂等）；`ix_orders_create_date`（区间扫描）。排序/分页在 4 万行级由 PG 内存排序承担，不另建排序索引（重估阈值同 S4）。

upsert 更新集（`on_conflict_do_update`）：`amount_minor, usd_order_amount_minor, language, currency_type, refund_time, is_returned, promotion_code, order_class, updated_at`——3 天回看由此捕获退款回填与金额修正；`create_time/create_date/theater_id/chapter_id` 视为上游不可变，不入更新集。

### 2.2 `ad_revenue_daily`（新表）

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| date | Date | **PK** | 幂等键=日（AC-U4）。单渠道，无其他维度 |
| amount_minor | **Numeric(14,2)** | NOT NULL | 广告收益·**美元最小单位**（上游 `ad_revenue_dollars` 为美元单位，入库 ×100 统一口径，AC-U4） |
| updated_at | DateTime(tz) | server_default now()/onupdate | 审计 |

行数上界 92 + 少量溢出，无额外索引。

### 2.3 `sync_runs`（新表）

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | BigInteger | PK, Identity | |
| trigger | String(16) | CHECK IN ('scheduled','manual','backfill') | 触发来源 |
| window_start / window_end | Date | NOT NULL | 本次覆盖日期窗（含） |
| status | String(16) | CHECK IN ('running','success','partial','failed') | orders 阶段失败→failed；成功但有广告失败或截断→partial |
| orders_fetched / orders_upserted | Integer | NOT NULL default 0 | 诊断用 |
| truncated_dates | **JSONB** | NOT NULL default '[]' | 二分到底仍整页的**日期清单**（AC-S7 横幅按日精确呈现，比布尔更诚实） |
| orders_error / ad_error | Text | NULL | 两阶段错误分离（AC-S9：广告失败不连坐订单） |
| started_at / finished_at | DateTime(tz) | NOT NULL / NULL | 状态行「更新于 t」取最近 orders_error IS NULL 行的 finished_at |

索引：`ix_sync_runs_started_at`（取最新行）。覆盖自愈（§3.3.3）以「status IN ('success','partial') 且 orders_error IS NULL 的运行窗口并集」计算已覆盖日期，无需额外表。

### 2.4 迁移要点

- 新迁移 **`0002_dashboard_ingest`**，`down_revision = "0001_auth_baseline"`；`alembic revision --autogenerate` 生成后人工核对（现有流程），upgrade/downgrade 均须可执行。
- `app/models/__init__.py` 增补三个模型导入（Alembic 可见性）。

### 2.5 金额与时间口径（全链路约定）

- **单位约定**：DB 一律存**最小单位**（minor）：`amount_minor`（原币）、`usd_order_amount_minor`（USD）、`amount_minor`（广告，USD）。API 一律出**主单位 2 位小数字符串**（如 `"1234.56"`），由服务层 `Decimal / 100` 后 `quantize("0.01")` 产生；前端只做 `Intl` 格式化渲染与图表几何缩放，**不做任何金额加减**（图例折叠、按日 other 合并等需要求和的派生一律由后端给出，见 §5.2）。
- **RQ-4 实现指引（所有币种统一 /100，照搬 HTML）**：`/100` 假设**只存在于展示层**（API 主单位换算与 CSV 输出）；规范化层与存储层保留上游 `amount` 的 Decimal 原值、不做任何位数假设。未来若确认存在 0 位小数币种（如 JPY），只需在展示层加「币种→小数位数」映射，存储、聚合、幂等键零改动。
- **禁止 float**：解析上游数值用 `Decimal(str(value))`；psycopg 按 Decimal 往返 Numeric。
- **时间**：存储层零时区换算（D6）；「今天」预设按浏览器本地日（前端）；`latest_orders_sync_at` 等 API 时间戳为 ISO 8601 UTC，前端本地化展示。

---

## 3. 上游客户端与同步设计

### 3.1 上游客户端（A1，`app/upstream/client.py`）

3.1.1 **TokenProvider**（AC-U1）

- `POST /open/oauth2/token`，HTTP Basic（文档建议方式），form 体 `grant_type=client_credentials`。
- 缓存 `{token, expires_at}`；`expires_at - 60s` 内主动重换（AC-U1；文档「刷新 Token」建议）。
- 响应取值路径双键名兼容：`data.accessToken || data.access_token`、`expiresIn || expires_in`（实测补充）。

3.1.2 **post() 双层 401 单次重试**（HTML:926-939 移植）

- HTTP 层 401 **或** HTTP 200 信封 `code=401` → 丢弃缓存 → 重换票 → **重放一次**原请求；再失败抛 `UpstreamError`。绝不循环。
- 信封 `code != 200` → `UpstreamError(msg)`（携带 traceId 进日志，不进用户面）。
- `httpx.Client(base_url=settings.upstream_base, timeout=settings.upstream_timeout_seconds)`；线程安全（窗口并发 4 复用同一 client）。**任何日志不得出现凭据或 token**。

3.1.3 **超时/限流**（AC-U7）：请求超时 30s（配置）；429/超时记录 warning 日志并按窗口失败处理，**不重试风暴**——失败窗口留给下一轮 30 分钟同步或手动刷新自愈。

3.1.4 **出站白名单**（AC-U5）：模块内仅出现 3 个路径常量（`/open/oauth2/token`、`/open/order/list`、`/open/order/adSummary`）；代码审查断言：`grep -rn "tfctechnology" backend/app/` 零命中。

### 3.2 窗口化拉取与二分补全（A1，`app/upstream/fetcher.py`）

按日窗口 + 二分，**逐条移植** HTML:950-983 语义：

```
fetch_day(date) -> FetchResult(rows, truncated: bool)
  window = [date 00:00:00, date 23:59:59]        # HTML loadDay 的日窗，秒级端点（非 .999）
  return fetch_window(start, end, depth=0)

fetch_window(start, end, depth):
  resp = POST /open/order/list {startDate, endDate, page:1, pageSize: settings.upstream_page_size}
  rows = resp.data.list or []
  if len(rows) < page_size:  return rows, truncated=False        # 上游无 hasMore，整页=可能截断
  if depth >= max_split_depth or (end - start) < min_split_window_seconds:
      return rows, truncated=True                                 # 记入 run.truncated_dates
  mid = 将 (start+end)/2 向下取整到秒                              # HTML: floor(…/2000)*1000
  a = fetch_window(start, mid, depth+1)
  b = fetch_window(mid + 1s, end, depth+1)
  return a.rows + b.rows, a.truncated or b.truncated
```

- 参数全部配置化（D10）：`page_size=1000`、`max_split_depth=6`、`min_split_window_seconds=120`、并发 4。
- 窗口时间戳格式 `YYYY-MM-DD HH:mm:ss`（HTML apiStamp 同款）；窗口运算用 naive datetime（不引时区）。
- 窗口始终在单日内（二分子窗不跨日）→ truncated 归属到**当天**记入 `truncated_dates`。

**广告拉取（A5）**：`fetch_ad_summary(from, to)` 单请求（startDate=from 00:00:00，endDate=to 23:59:59，page=1，pageSize=1000），不二分（D11：≤92 行 < 页上限）。取行内 `date[:10]` 与 `ad_revenue_dollars` → `Decimal(str(v)) * 100` 入 minor（HTML:1028-1032 同口径）。

### 3.3 同步管道（A2，`app/services/sync_service.py`）

3.3.1 **编排**（trigger ∈ scheduled / manual / backfill，days 为日期集合）：

1. 建 `sync_runs` 行（running）。
2. **orders 阶段**：ThreadPoolExecutor(4) 并发跑 `fetch_day`（HTTP 并行）→ 汇集后**单会话串行 upsert**（会话非线程安全；分批 500 行 `insert … on_conflict_do_update`）→ 批内按 order_id 去重 → 规范化映射（AC-U3）：`orderAmount→usd_order_amount_minor`、`amount→amount_minor`、`create_date=create_time[:10]`、`is_returned=refund_time 非空白`、`order_class=classifier.classify(row)`（空实现→NULL）。**该阶段独立 commit**。
3. **ad 阶段**：`fetch_ad_summary` → 按日 upsert `ad_revenue_daily`。独立 commit（AC-S9：广告失败不回滚订单）。
4. 收尾更新 run 行：status（§2.3 规则）、truncated_dates、counts、errors、finished_at。

3.3.2 **手动插队**（D4/AC-S4）：`run_manual(from, to)`——区间服务端钳制（`from = max(from, to-91)`、`to = min(to, today_utc)`；**today_utc = 服务器 UTC 当日**，与数据日界同口径）后并入 days 集合执行；语义=「清缓存重拉当前区间」（**全区间重拉**，RQ-2 已决议）。单飞锁被占时 accepted=false 返回当前进度快照（§5.5）。

3.3.3 **覆盖自愈（含首次回填）**：每次 scheduled 运行的 days = `最近 lookback_days 天（以 UTC 日计）` ∪ `期望域 [today_utc-backfill_days+1, today_utc] 中未被成功运行窗口覆盖的日期`。首次部署无运行记录 → 自动等价于 92 天回填（D3，RQ-5 已决议），失败日由后续轮次自动补拉，无需人工干预。启动时（lifespan）立即跑一次 scheduled（同时完成回填判定），此后每 `sync_interval_minutes` 一轮。

3.3.4 **幂等**：orderId 唯一约束 + upsert（AC-S3）；广告按日主键 upsert。重跑零重复行（单测断言）。

### 3.4 调度器（`app/upstream/scheduler.py` + main.py lifespan）

```
lifespan:
  if settings.sync_enabled and upstream 凭据已配置:
      app.state.sync_task = asyncio.create_task(scheduler_loop())
  yield
  cancel + await task

scheduler_loop():
  while True:
      await asyncio.to_thread(sync_service.run_scheduled)   # 同步管道在 worker 线程
      await asyncio.sleep(settings.sync_interval_minutes * 60)
```

- **单飞**：`sync_service` 模块级 `threading.Lock`，`acquire(blocking=False)` 失败 → scheduled 跳过本轮 / manual 返回 accepted=false。单进程假设（compose 单 uvicorn worker）登记于 §8.1。
- **孤儿 running 行清理（m9）**：进程崩溃/重启会遗留 `status='running'` 的 sync_runs 行——lifespan 启动时（先于调度器）执行一次性 UPDATE：`status='running'` → `'failed'`，`orders_error` 为空则补 `'orphaned: process restarted'`。保证状态行/last_run 永不悬挂在 running。
- **测试隔离（m7）**：`tests/conftest.py` **显式强制 `SYNC_ENABLED=false`**（会话级设置环境变量或覆写 Settings），不依赖 `.env` 凭据恰好为空；调度器启动条件保留双保险（`sync_enabled=false` **或** 上游凭据未配置均不启动）。B-T5 交付此项。
- **进度态**：模块级 `CurrentRun`（带锁 dataclass：run_id/trigger/window/days_done/days_total/phase），HTTP 状态端点直读；持久态以 `sync_runs` 为准（重启后仍可查最近结果）。

### 3.5 失败降级映射（对照 AC）

| 场景 | 行为 | AC |
|---|---|---|
| 上游订单阶段失败 | 本轮 orders_error 记录；库内数据照常供 summary；`meta.sync_status='failed'` → 前端红点 + 错误横幅（重试按钮=POST /sync） | S5 |
| 广告阶段失败 | run.ad_error；summary `ad_available=false` → 广告横幅，订单区块不受影响 | S9 |
| 窗口截断 | run.truncated_dates；summary `meta.truncated_days`（与区间相交者）→ 警告横幅「合计可能偏低」 | S7 |
| 我方 API 网络失败 | 前端 connFailed + 错误横幅 + 重试 | S5 |
| 区间含最新覆盖日 | `meta.incomplete_tail` → 状态行常驻注记 | S6/D5 |

### 3.6 配置清单（Settings 增项 + 根 `.env.example` 增段）

| 键 | 默认 | 说明 |
|---|---|---|
| SYNC_ENABLED | true | 调度总开关（测试/本地关） |
| SYNC_INTERVAL_MINUTES | 30 | D1 |
| SYNC_LOOKBACK_DAYS | 3 | D2 |
| SYNC_BACKFILL_DAYS | 92 | D3 |
| UPSTREAM_BASE / UPSTREAM_CLIENT_ID / UPSTREAM_CLIENT_SECRET | （已有占位） | .env.example 已预留，本期启用 |
| UPSTREAM_PAGE_SIZE | 1000 | D10 |
| UPSTREAM_MAX_SPLIT_DEPTH | 6 | D10 |
| UPSTREAM_MIN_SPLIT_WINDOW_SECONDS | 120 | D10 |
| UPSTREAM_CONCURRENCY | 4 | D10/AC-U7 |
| UPSTREAM_TIMEOUT_SECONDS | 30 | AC-U7 |
| SHARE_INCLUDED / SHARE_EXCLUDED | "0.20" / "0.70" | **D13：B1 期间不接入任何输出路径**（仅 share_service 读取，§4.4） |

---

## 4. 聚合与降级（A7，`app/services/aggregation.py` + `fx_legacy.py`）

### 4.1 聚合规则清单（全部照搬 HTML derive()/convCompareData()/countries map，B1 语义替换分成→毛额）

| 口径 | 规则（源码依据） |
|---|---|
| 参与聚合的订单 | 退款单（is_returned）**不进任何金额聚合**，仅进退款计数（AC-AG2，HTML:1121） |
| 毛额 gross | Σ usd_order_amount_minor（当前视图=B1 全部订单，AC-K5） |
| 每日（两口径） | 日界=create_date；**est 口径**=amount_minor×静态汇率（无汇率币种不计入该口径，订单数独立计）；**usd 口径**=usd_order_amount_minor（缺失不计入，AC-AG3）。逐日含零值日；byCurrency 为**该口径美元额**按订单币种分组、降序 |
| 广告 | 区间内 ad_revenue_daily 求和 + 有数据日数（AC-K4） |
| 国家 | language→地区子标签（`_-XX$` 正则取 XX 大写；无子标签=原语种串；空=未知哨兵）。聚合 key 用**稳定 key**（区域码/原串/`__unknown`），展示名由前端 Intl 按语言本地化（AC-AG4/N2）。按毛额 USD 降序；byCurrency 为**原币金额** |
| 对比卡 | 输入=全部已完成订单；每币种：native=Σamount_minor、legacy=native×rate（无汇率跳过且 hasRate=false）、server=Σusd（缺失计入 no_usd_order_count）；**`no_usd_currencies`=缺失 usd 的完成订单涉及币种清单（AC-C8 横幅数据源，聚合遍历顺带产出，M1）**；行排序=max(server,legacy) 降序；delta=server−legacy；deltaPct=delta/base 1 位小数带符号（base=server或legacy）；flagged=\|delta\|≥$1 且 ≥base 1%（AC-C3）；agree=总 delta/base（base=serverTotal或legacyTotal）<0.5%（AC-C5） |
| 折叠派生（后端预计算，防前端金额求和） | ① 每日图表序列=币种按区间毛额（usd 口径）降序前 6 + `__other`（逐日折叠值）；② 对比环图 slices=**前 7 + `__other`（≤8 切片，RQ-3 已决议照搬 HTML:1632-1635）**，双口径值都给；③ 国家 bars=前 9 + `__other`（usd/orders/byCurrency **求和**合并，HTML:1725-1729 同款）。表格式输出（每日表 byCurrency、对比表、国家表）不折叠 |
| 分成（×20/×70） | **不计算、不输出**（AC-AG5/D3）。`share_service.share_amount()` 能力实现 + 单测，但聚合/API/CSV 零 import（B1 恢复时再接线） |

### 4.2 精度实现

- 输入：DB Decimal；汇率常量 Decimal；中间量全 Decimal；输出 `quantize(Decimal("0.01"), ROUND_HALF_UP)` → str。（HTML 的美分整数 + float 是被修正的缺陷，允许与新结果存在末位舍入差，对账工具抽查。）
- 聚合输入列裁剪：只 SELECT `create_date, currency_type, language, amount_minor, usd_order_amount_minor, is_returned`（4 万行轻载）。

### 4.3 B1 降级契约（字段级，S6 定案）

| 位置 | B1 形态 |
|---|---|
| 响应顶层 | `degraded: {share_rules_pending: true}`（规则接入后置 false 并最终移除） |
| `kpis.included_revenue` / `kpis.excluded_revenue` | `null`（键在） |
| 订单行 `order_class` | `null` |
| CSV `class` / `rev_share` / `earnings_usd` | 表头保留，值空串（AC-X3） |
| 前端渲染 | null → 值位 `–` + 「待规则确认」标注 + 卡片置灰；数据集后两档 disabled；类别筛选 disabled；类别堆叠视图不提供（D7/D8/D9，§6.8 全清单） |

### 4.4 分类器接口（A6，`app/services/classifier.py`）

```python
class OrderClassifier(Protocol):
    def classify(self, order: NormalizedOrder) -> Literal["included", "excluded"] | None: ...

class UnknownClassifier:      # 本期唯一实现：恒返回 None（AC-CL1，不猜规则）
```

- 接入点唯一：同步管道规范化时调用（§3.3.1），写 `order_class`。其余模块只读标签列，不关心来源（planning/02「唯一的缝」）。
- `share_service.py`：`share_amount(usd_minor, order_class)` 读 SHARE_* 配置——**B1 无任何调用方**（AC-AG5；测试用例直接单测该函数）。

### 4.5 静态汇率表（`app/services/fx_legacy.py`）

HTML:764-768 的 **27 个键**（AED/AUD/BRL/CAD/CHF/CLP/CZK/EUR/GBP/HKD/IDR/INR/JPY/KRW/MXN/MYR/NGN/PHP/QAR/SAR/SGD/THB/TRY/TWD/USD/VND/ZAR，逐值清点）**逐值冻结**为模块级 `LEGACY_USD_RATES: dict[str, Decimal]`（含 `USD: 1`），注释标明「2026-08 估值、仅对比卡使用、口径变更须走 REQ」（D12）。无汇率=键缺失 → 不计入旧合计（与 export_orders.py 一致）。单测断言键数=27 且与 HTML 逐值相等。

### 4.6 与参考实现的差异登记（评审要求集中列出）

本设计对 HTML 的移植声明为「逐条移植」，以下为**全部已知可观测差异**（架构性迁移——数据路径、计算位置、凭据位置——见 REQ §1.3，不在此重复）。新增差异必须先登记于此再实现：

| # | 差异 | 性质 | 依据与影响 |
|---|---|---|---|
| 1 | **金额舍入**：HTML 用「float + 美分整数」计算；新系统全链路 Decimal，`ROUND_HALF_UP` 量化 2 位。展示值可能与 HTML 偶有 ±0.01 末位差 | 行为修正（REQ 架构性变更 #8：float 是被修正的缺陷） | §4.2；对账抽查登记于验证报告 |
| 2 | **`conv.no_usd_currencies` 字段新增**：HTML 由前端遍历订单现算缺美元币种；新契约由后端聚合顺带产出清单（M1 修复） | 契约新增（无 HTML 对应物，行为等价） | §5.2；AC-C8 横幅数据源 |
| 3 | **自定义区间 start>today 钳制**：设计初稿漏写，本次补齐 `start 也钳到今天`（m4）——补齐后**行为与 HTML:1937 一致，非偏差**，登记仅为可审计 | 文本补齐（行为一致） | §6.4；AC-T3 |
| 4 | **CSV 文件名**：B1 期间两档导出同名 `orders_all_{from}_to_{to}.csv`（数据集标识恒为 all）；HTML 中 dataset 可变故不同名 | REQ 授权的差异（AC-X2 明示同名可接受，不自行改名） | §5.4；m5 |
| 5 | **all 档 CSV 行序**：按 `create_time` 降序（与订单表默认序一致）；HTML 的 all 档为前端缓存自然序（≈拉取日序） | 实现差异（内容集合相同，仅顺序；确定性更好） | §5.4；AC-X5 按行数与字段值验收不受影响 |
| 6 | **服务端「今天」= UTC 日**（§3.3.2/3.3.3 钳制与覆盖域）；HTML 无服务端，预设「今天」按浏览器本地日（D6 双轨保留） | 设计澄清（新增服务端行为，取与数据日界同口径的 UTC） | m6；前端预设逻辑不变（§6.4） |

---

## 5. API 契约（前后端并行的唯一真源）

### 5.1 通用约定

- 前缀 `/api/v1/dashboard/**`，router 级 `dependencies=[Depends(get_current_user)]`（AC-SEC2）；未带/失效 token → 既有 401 `UNAUTHORIZED` 信封（前端 client 已有跳转逻辑，AC-G2）。
- 错误信封沿用 `{"error": {code, message, details?}}`（DESIGN-01 §3.2，零新增机制）。
- 日期参数 `from`/`to`：`YYYY-MM-DD`；校验（Query 模型 validator → 422 `VALIDATION_ERROR`）：`from ≤ to`、跨度 ≤ 92 天。前端负责预设/钳制逻辑（§6.4），后端只做防御校验（查询类）或钳制（sync 动作类）。
- **金额**：主单位 2 位小数**字符串**（§2.5）；计数 int；日期串 `YYYY-MM-DD`；时间戳 ISO 8601 UTC。
- 字段命名 snake_case（与 auth API 的 `access_token` 先例一致；上游 camelCase 在规范化层一次性映射）。

### 5.2 `GET /dashboard/summary?from&to` — 一次装载全看板（除订单表）

```json
{
  "range": { "from": "2026-09-29", "to": "2026-10-12" },
  "meta": {
    "orders_total": 6016,
    "latest_orders_sync_at": "2026-10-12T09:29:33+00:00",
    "sync_status": "ok",                 // ok | failed | running | never（订单阶段视角）
    "latest_covered_date": "2026-10-12", // 最近成功运行 window_end
    "incomplete_tail": true,             // to >= latest_covered_date → 常驻注记（D5）
    "truncated_days": [],                // 与区间相交的截断日期（AC-S7）
    "ad_available": true, "ad_error": null
  },
  "degraded": { "share_rules_pending": true },
  "kpis": {
    "total_revenue": "83233.87",         // B1：毛额口径 = orders_gross_usd + ad_total（AC-K1）
    "orders_gross_usd": "80833.75",      // total 的订单部分（aux 拆分用）
    "ad_total": "2400.12",
    "included_revenue": null,            // B1（AC-K2）
    "excluded_revenue": null,            // B1（AC-K3）
    "gross_usd": "80833.75",             // AC-K5（B1 全部订单，与 orders_gross_usd 同值）
    "orders_completed": 5959,            // B1 口径自洽：completed + returned = orders_total
    "orders_returned": 57,
    "countries": 15,
    "top_country": "US",                 // countries.table[0].key；空则 null
    "ad_days_reported": 14
  },
  "daily": {
    "days": ["2026-09-29", "…"],
    "currency_rank": ["USD", "JPY", "EUR"],          // 区间毛额(usd 口径)降序全量；图例/序列色分配依据
    "est": [                                           // 估算口径逐日（含零值日）
      { "date": "2026-09-29", "orders": 431, "total": "5781.02",
        "by_currency": [ {"currency": "USD", "amount": "4021.02"} ],   // 该口径美元额，降序，表用（不折叠）
        "series":    [ {"key": "USD", "amount": "4021.02"}, {"key": "__other", "amount": "210.00"} ] } ],
    "usd":   [ { …同形，usd 口径… } ],
    "ad":    [ {"date": "2026-10-01", "amount": "171.44"} ]            // 仅有数据日
  },
  "conv": {
    "empty": false,
    "rows": [ {"currency": "JPY", "has_rate": true, "rate": "0.0068", "orders": 1201,
               "native": "1234567.89", "legacy_usd": "8395.06", "server_usd": "8210.55",
               "delta": "-184.51", "delta_pct": "-2.2", "flagged": true} ],   // 排序 max(server,legacy) 降序
    "slices": [ {"key": "JPY", "legacy_usd": "8395.06", "server_usd": "8210.55"},
                {"key": "__other", "legacy_usd": "…", "server_usd": "…"} ],  // 前 7 + 其他（≤8 切片，RQ-3 决议=照搬 HTML）
    "legacy_total": "64123.00", "server_total": "63420.11",
    "delta_total": "-702.89", "delta_pct": "-1.1", "agree": false,
    "no_rate_currencies": ["BHD"], "no_usd_order_count": 3,
    "no_usd_currencies": ["BHD", "KZT"]   // 缺 usd 完成订单的币种清单（AC-C8 横幅，M1）
  },
  "countries": {
    "table": [ {"key": "US", "usd": "31000.11", "orders": 2100, "share": "38.4",
                "by_currency": [ {"currency": "USD", "amount": "310000.11"} ] } ],  // 全量降序；by_currency=原币金额
    "bars":  [ { …同形，前 9…}, {"key": "__other", "usd": "6210.44", "orders": 812, "by_currency": […合并…]} ]
  }                                        // __other 的 orders 为尾部国家求和（§4.1/HTML:1725-1729，m3）
}
```

说明：① `daily.est/.usd[].orders` 各自独立计数（口径不同参与订单不同，两卡独立判空 AC-E8）；② `series` 为图表预折叠（前 6+`__other`），`by_currency` 为表格全量；③ `conv.rows/native`、`countries.by_currency` 为**原币主单位**串；④ `total_revenue` B1 语义=毛额+广告，aux 由前端拼 `orders_gross_usd`/`ad_total` + 毛额标注（§6.8）；⑤ 金额字符串一律非空（0 → `"0.00"`），「不可用」只用 null；⑥ **conv 色分配**=排序位 `i<7 → var(--cat{i+1})`，`__other` 与表尾第 8+ 币种 → `var(--muted)`（HTML convColors:1579-1584 与 MAX_SLICES=7:1632-1635 两处对齐，RQ-3 决议）。

### 5.3 `GET /dashboard/orders?from&to&currency&status&sort&dir&page` — 订单分页表

Query：`currency`（`all`|币种码）、`status`（`all|completed|returned`）、`sort`（`date|currency|amount|usd`，默认 `date`）、`dir`（`asc|desc`，默认 `desc`）、`page`（1 起，默认 1）。页大小固定 25（AC-O4，常量不开放参数）。B1 无 class 筛选参数（恢复时追加，向后兼容）。

```json
{
  "rows": [ { "order_id": "R2026…", "create_time": "2026-10-12 01:26:33", "create_date": "2026-10-12",
              "country_key": "US", "language": "en_US", "currency": "USD",
              "amount": "2.99", "usd": "2.99", "order_class": null, "status": "completed" } ],
  "page": 1, "page_size": 25, "pages": 241,
  "total": 6016,            // 筛选后行数（副标题 n）
  "total_in_range": 6016,   // 未筛选（副标题 m，AC-O5）
  "currencies": ["ARS", "BRL"]   // 区间内动态币种选项（AC-O2）
}
```

- 排序 SQL：date→`create_time`（字符串序=时间序）；currency→`currency_type`；amount→`amount_minor`；usd→`coalesce(usd_order_amount_minor, -1)`（HTML null→-1 语义，AC-O3）；末位统一追加 `order_id` 决定性 tiebreak。
- 空态由前端区分（区间无订单 vs 筛选无匹配，AC-O6：`total_in_range==0` → 前者）。
- `country_key`：区域码（`US`）/ 原语种串 / **`"__unknown"`（未知统一哨兵，m12：与 summary `countries.key` 同一枚值）**。前端 `format.js` 的 countryOf 集中映射：`__unknown` → `t('dashboard.unknownCountry')`；两位区域码 → `Intl.DisplayNames`；其余原串直出。后端 CSV 同规则本地化为「Unknown/未知」。

### 5.4 `GET /dashboard/orders.csv?from&to&scope&currency&status&sort&dir&lang` — CSV（S5 后端流式）

- `scope=view|all`：view=套用表格筛选+排序全量行；all=区间全部订单（忽略筛选，AC-X1）。`lang=en|zh` 选表头与状态词。其余参数同 5.3（all 时忽略筛选排序参数，按 create_time desc 固定序）。
- 响应：`200 text/csv; charset=utf-8`，`Content-Disposition: attachment; filename="orders_{dataset}_{from}_to_{to}.csv"`，`dataset` = 数据集标识——**B1 期间恒为 `all`，两档同名**（REQ AC-X2 明示可接受，差异来自内容；不自行改名，差异登记 §4.6-4）。前端以带 Authorization 的 fetch → blob → a[download] 落盘（client 新增下载助手）。
- 内容（AC-X2/X3/X4）：UTF-8 **BOM** 首块；**CRLF**；14 列表头逐字照搬 HTML csvHeaders（en/zh）；`amount`/`est_usd` 两位小数（est_usd=usd 主单位，缺失空）；**class/rev_share/earnings_usd 三列空**；防公式注入：值以 `= + - @ \t \r` 开头前置 `'`，含 `",\n\r` 加引号并双写内部引号（HTML csvCell 逐条移植）；`country` 用 babel CLDR 按 lang 本地化（未知→「Unknown/未知」），`status` 用冻结小词表（Completed/Returned ↔ 已完成/已退款）。

### 5.5 `POST /dashboard/sync` + `GET /dashboard/sync/status` — 手动刷新（S7）

`POST /dashboard/sync` body `{"from": "...", "to": "..."}`（当前视图区间；服务端按 §3.3.2 钳制）→

```json
202 Accepted
{ "accepted": true, "status": { …与 GET 同形快照… } }
// 单飞锁被占：202 { "accepted": false, "status": {…当前进度…} }   // 不报错，前端继续轮询
```

`GET /dashboard/sync/status` →

```json
{
  "state": "running",                      // running | idle
  "current": { "id": 123, "trigger": "manual", "window_start": "2026-09-29",
               "window_end": "2026-10-12", "days_done": 5, "days_total": 14, "phase": "orders" },  // idle 时 null
  "last_run": { "id": 122, "trigger": "scheduled", "window_start": "…", "window_end": "…",
                "status": "success", "started_at": "…", "finished_at": "…",
                "truncated_days": [], "orders_upserted": 6101,
                "orders_error": null, "ad_error": null }   // 无任何运行时 null
}
```

### 5.6 错误码总表（本域新增仅 1 个语义码，其余复用）

| HTTP | code | 场景 |
|---|---|---|
| 401 | UNAUTHORIZED | 未登录/失效（既有，AC-G2） |
| 422 | VALIDATION_ERROR | from/to 缺失、格式错、from>to、跨度>92（details 字段级） |
| 429 | SYNC_BUSY | **不使用**——单飞冲突走 202 accepted=false |
| 500 | INTERNAL_ERROR | 兜底（既有） |

### 5.7 契约演进（B1 恢复时，AC-CL3 预埋）

- summary/orders 增加可选 `dataset` 参数（`all|included|excluded`，默认 all，B1 期间传非 all → 422）；`kpis.included_revenue` 等字段由 null 转出值；订单行 `order_class` 出值；CSV 三列出值。全部**加法变更**，前端按 `degraded.share_rules_pending` 与 null 分支已预置渲染路径。

---

## 6. 前端设计

### 6.1 页面与组件树（替换 `pages/DashboardPage.jsx` 占位）

```
DashboardPage（状态中枢，§6.3）
├─ AppBar                 标题 + 副标题(B1 毛额口径) + StatusLine + LangToggle(复用) + ↻ + 退出
├─ TimeFilters            4 预设 chip + 起止 date 输入（AC-T1–T5）
├─ DatasetBar             三档分段控件（后两档 disabled+待规则确认）+ 两档 CSV 按钮（AC-D1）
├─ Banners                错误(重试)/同步失败/广告不可用/截断/缺美元币种 五类（AC-S5/S7/S9/C8）
├─ KpiSection             hero + 6 小卡（B1 降级态 §6.8）
├─ DailyCard ×2           est / usd 双卡，共享 chart|table 切换与 yMax（AC-E1–E8）
├─ AdCard                 广告柱状（AC-A1–A3）
├─ ConvCard               双环 + 图例 + 全量表 + 合计 + 尾注（AC-C1–C8）
├─ CountryCard            横向条形 + 表（AC-N1–N4）
└─ OrdersCard             三筛选 + 排序 + 25/页分页（AC-O1–O9）
components/dashboard/charts/：ColumnChart（堆叠柱：每日双卡与广告卡共用）、DonutChart、CountryBars
共用：Tooltip（portal 定位）、EmptyState、chartMath.js、useElementSize.js
逻辑模块 src/dashboard/：range.js（预设/钳制）、format.js（Intl 重建 + countryOf）、useSummary/useOrders/useSyncStatus
样式：styles/dashboard.css（新增）+ theme.css 增补变量（§6.5）
```

### 6.2 图表组件规格（S1 自绘 SVG）

- `chartMath.js`：逐函数移植 `columnPath`（柱顶 4px 圆角）/ `barPathH` / `donutArc` / `niceCeil`（1/2/2.5/5×10ⁿ 向上取整）/ `axisMoney`（$K 缩写）（HTML:1890-1914）。
- `ColumnChart` props：`rows=[{date, total:Number, count, segs:[{key,label,color,amount:Number,display}]}]`、`yMax`（外部传入实现双卡共享，AC-E2）、`emptyLabel`、`ariaLabel`。渲染：4 档 y 网格 + 轴标签、`labelEvery=ceil(n/8)` x 标签、段间 2px 缝/仅顶段圆角、透明 `rect.bar-hit`（tabIndex=0、role=img、逐柱 aria-label）、pointermove/focus → 十字准线 + Tooltip、legend。广告卡=单序列 `--ad` 色复用本组件。
- `DonutChart` props：`slices=[{key,label,color,value:Number,display,shareDisplay}]`、`centerDisplay`、`ariaLabel`。切片 class=「slice」可聚焦（tabIndex=0）、surface 描边 2px、环心 `usdWhole` 合计。
- `CountryBars`：行高 38、labelW=min(150, W×0.3)、行尾 `usdWhole` 整美元、行级 hit-rect tooltip（国家+订单数+USD+币种拆分）。
- `Tooltip`：单例 portal，fixed 定位 + 视口钳制（HTML showTip 移植）；内容为后端字符串直渲染。
- `useElementSize`：ResizeObserver + 150ms 防抖 → 宽度；`W = max(320, width||800)`；容器变化整树重渲染（React 天然无残留，AC-R3）。
- **金额纪律执行**：后端字符串 → `Number()` 仅供几何缩放与 niceCeil（可视化）；一切展示值用原字符串 + Intl。

### 6.3 状态与数据流（S8）

```
DashboardPage state：
  range {preset, from, to}        // range.js：预设/自定义逻辑（§6.4），变更 → 重置页码
  dailyView 'chart'|'table'       // 双卡共享（AC-E1）
  filters {currency, status}      // 'all'|值；类别筛选 B1 恒禁用
  sort {key:'date', dir:'desc'}   // 点击表头切换（AC-O3）
  page 1..n                       // 筛选/排序/区间变更 → 重置 1（AC-T5）
hooks：
  useSummary(range)    → {data, loading, error, reload}     // loading → loadingdim + 状态行（AC-S1）
  useOrders(range, filters, sort, page) → {data, loading}
  useSyncStatus()      → {status, start(from,to), polling}  // POST → 1s 轮询 → idle 后 reload summary+orders
挂载时序：RequireAuth（已有）→ setPreset('7d')（AC-T2/D15）→ useSummary 装载。
meta.sync_status=='running' 或轮询中 → 状态行「正在加载 {a}/{b} 天…」（AC-S1），idle 后自动重拉。
```

- 401 → client 既有跳转 `/login?expired=1`（AC-G2）；退出按钮 → logout + navigate('/login')（AC-G3）。
- 币种筛选选项取自 orders 响应 `currencies`；当前选中失效回落 `all`（AC-O2）。
- 状态行：`updated {t} · {n} orders`（绿点）/ `connFailed`（红点）/ loading（中性点）+ `incomplete_tail` 常驻注记（i18n，D5）。

### 6.4 时间范围逻辑（range.js，HTML:1918-1955 逐条移植）

- 预设：today/7d/14d/30d（今天=浏览器本地 00:00，`todayStart()`）；`date inputs max=今天`；chips aria-pressed + ✓ 前缀（CSS 既有选择器迁移）。
- 自定义：任一变更生效；起>止交换；**止>今天钳今天，且起>今天也钳到今天**（HTML:1936-1937 两行都移植，m4）；跨度>92 → 起点收缩为 `止-91` 天；预设与输入框双向同步（`syncControls`）。
- 区间传给 API 的即本地日历日串（B1/D6 口径：数据按 UTC 日存储，展示层不换算）。

### 6.5 样式与主题迁移

- `theme.css` 增补（两套模式各一）：`--cat1..8`、`--inc`、`--exc`、`--ad`（HTML:11-36 原值）；其余变量已就绪。
- `dashboard.css` 新增：从 HTML `<style>` 迁移 appbar/chip/seg/card/kpis(+900px 两列)/banner/cardhead/two|pietwo|convtwo(+640px)/table(sortable/mono/chip-status/pagebtn)/tablewrap/dsbar/tooltip/legend/axis-label/empty/loadingdim/visually-hidden 等规则；类名保持一致，便于与 HTML 逐条对照验收。
- 断点：900px（kpis 两列、双栏转单列）与 640px（convtwo 转单列）——375/1280 两基准即被覆盖（AC-R1/R2）。
- 文本字形白名单（原样保留、不新增）：`↻ ✓ ↩ ‹ › ⚠ ⤓` 及退出按钮字符（HTML:272/249/250 的 `&#x2913;`/`&#x21BB;`/`&#x2B91;` 实体照搬）（AC-V3）。

### 6.6 i18n 迁移（en.json / zh.json 增 `dashboard` 命名空间）

- **迁移规则**：HTML I18N 表（480-637）除「弃用键」外全部迁入 `dashboard.*`，键名保持 HTML 原名（如 `dashboard.kpiTotal`），插值 `{x}` → `{{x}}`；`csvHeaders` 数组原样。
- **弃用键全清单（m8 补齐）**——两类：① 登录/会话系列已由 auth 命名空间覆盖（`loginTitle/loginSub/loginUser/loginPass/loginSubmit/loginBusy/loginInvalid/loginExpired/signedOut`）；② 浏览器直连时代语义在新架构无对应物（`netError/corsError/upstreamMissing/upstreamCors/upstreamBadBody/upstreamFailBody`——最后者由新键 `upstreamFailBodySync` 取代）。另 `dailySubType` B1 不提供（类别堆叠，AC-CL3 恢复时再加回）。保留 `clIncluded/clExcluded/subIncluded/subExcluded` 等键（B1 不渲染，恢复时零成本）。
- **新增键**（B1 降级 + 新架构状态，en/zh 定稿文案）：

| key | en | zh |
|---|---|---|
| pendingRule | Pending rule confirmation | 待规则确认 |
| subAllGross | All upstream orders · gross basis (share rules pending) | 全部上游订单 · 毛额口径（分成规则待确认） |
| kpiGrossNote | gross basis · no revenue share until rules confirmed | 毛额口径 · 分成规则确认前不计分成 |
| dailySubGross | Completed-order gross, stacked by currency · share rules pending | 已完成订单毛额，按币种堆叠 · 分成待规则确认 |
| hByCurrencyGross | Gross by currency | 按币种毛额 |
| classPending | Pending rule | 待规则确认 |
| dataIncompleteNote | Upstream sync lags — the most recent day may be incomplete. | 上游同步有延迟，最新一天数据可能不全。 |
| upstreamFailBodySync |  Showing data from the last successful sync. |  已显示最近一次成功同步的数据。 |
| syncRejected | A sync is already running — showing its progress. | 已有同步正在进行，正在展示其进度。 |

### 6.7 可访问性（AC-V4）与响应式（AC-R1–R3）

- aria-pressed：预设 chips、数据集/图表切换 seg；aria-sort：可排序表头（▲/▼ 指示）；svg role="img" + aria-label（含合计）；柱/切片/行 hit 元素 tabIndex=0 + focus 显示 tooltip；focus-visible 描边（CSS 迁移）。
- 375px：全部单列、KPI 两列 hero 跨行、表格容器内横滚；1280px：max-width 1240 居中、3:2 双栏（`.two`）。

### 6.8 B1 降级 UI 清单（逐 AC 对照）

| 区块 | B1 形态 |
|---|---|
| 副标题 | `subAllGross`（AC-D2） |
| 数据集 seg | included/excluded disabled（不可聚焦）+ `pendingRule` 标注；all pressed（AC-D1） |
| KPI 2/3 卡 | 值 `–` + `pendingRule` + 置灰态（AC-K2/K3） |
| Hero aux | 订单/广告拆分 + 日期 + `kpiGrossNote`（AC-K1） |
| 每日双卡副标题 | `dailySubGross`；类别堆叠切换不存在（AC-E4） |
| 每日表 | 列=日期/订单数/毛额/广告/按币种毛额（去分成列，AC-E7） |
| 订单表类别列 | 置灰 `classPending` 占位（AC-O1）；类别筛选 disabled（AC-O2）；无剔除行斜纹（AC-O8） |
| CSV | 三列空（AC-X3）；按钮两档均可用（AC-X1） |
| 联动 | 全部由 `degraded.share_rules_pending` + null 字段驱动，规则接入后同代码路径出值（AC-CL2/CL3） |

---

## 7. 任务包

> 约定：backend-agent 只动 `backend/**`（+根 `.env.example` 对应段），frontend-agent 只动 `frontend/**`；每任务完成即跑对应侧验证义务（ruff+pytest / pnpm lint，涉及配置加 build）并如实报告。前端自 F-T1 起即可对 mock 契约并行，**联调点 = B-T7 合入后**。

### 7.1 backend-task（依赖序）

| # | 任务 | 内容 | 依赖 | 关键验收（AC） |
|---|---|---|---|---|
| B-T1 | 模型与迁移 | 3 个模型 + `models/__init__` 汇总 + Settings 增项（§3.6）+ `.env.example` 增段 + 迁移 0002 | — | upgrade/downgrade 可逆；ruff |
| B-T2 | 上游客户端 | `upstream/client.py`：TokenProvider（60s 提前刷新）+ post()（双层 401 单次重试）+ 超时/白名单 | B-T1 | U1/U5/U6/U7（httpx MockTransport 单测：缓存命中、401 重放一次不循环、信封 code=401 分支） |
| B-T3 | 窗口拉取 | `upstream/fetcher.py`：fetch_day/二分/adSummary（§3.2 规格） | B-T2 | U2/U4（假上游页：整页触发分裂、深度/最小窗截断、truncated 归日） |
| B-T4 | 分类器与分成能力 | `classifier.py`（接口+Unknown）+ `share_service.py`（配置化，不接线）+ `fx_legacy.py` 冻结表 | B-T1 | CL1/AG5（断言 classify 恒 None；share_amount 单测；全仓 grep 确认聚合/API/CSV 无 import） |
| B-T5 | 同步管道与调度 | `sync_service.py`（规范化/upsert/sync_runs/覆盖自愈/单飞/进度态/孤儿 running 行清理）+ `scheduler.py` + lifespan 接线 + **conftest 强制 SYNC_ENABLED=false** | B-T3, B-T4 | S3/U3（幂等重跑零重复）、S8（createTime 原值）、3.3.3 自愈单测；m7：测试套件在无凭据环境下不启调度；m9：重启后无悬挂 running 行 |
| B-T6 | 聚合服务 | `aggregation.py`：summary 全口径（§4.1），Decimal 全链 | B-T1 | AG1–AG4 + C1–C8 数字断言（黄金数字 fixture；含 `no_usd_currencies` 清单 M1）；RQ-3：slices=前 7+`__other`；m1：汇率表 27 键逐值断言；D3：响应无任何 ×20/×70 值 |
| B-T7 | 看板 API | `schemas/dashboard.py` + `api/v1/dashboard.py`（summary/orders/sync/status）+ 挂载 | B-T5, B-T6 | SEC2、§5 契约测试（形状/校验 422/分页排序/null 降级位）、O3 排序含 usd null 语义 |
| B-T8 | CSV 导出 | `csv_export.py`（流式/BOM/CRLF/防注入/babel 国名/冻结词表）+ orders.csv 路由（pyproject 增 babel） | B-T7 | X1–X5（注入用例、zh 表头、三列空、与订单表行数一致性） |
| B-T9 | 收尾验证 | 全量 ruff+pytest；迁移 up/down；grep 凭据零命中 | 全部 | 验证报告区分已验证/未验证 |

### 7.2 frontend-task

| # | 任务 | 内容 | 依赖 | 关键验收（AC） |
|---|---|---|---|---|
| F-T1 | 契约客户端与 fixtures | `api/dashboard.js` 五函数 + client 增 blob 下载助手 + `mocks/dashboardFixtures.js`（`VITE_DASHBOARD_MOCK=1` 时 api 层切换） | 契约冻结（本文档 §5） | 与 §5 逐字段一致；lint |
| F-T2 | i18n 与主题 | dashboard 命名空间全量迁移 + 新增键（§6.6）+ theme.css 增补 + dashboard.css 骨架 | — | I1–I4/V1/V2（双 locale 键数一致脚本或 lint 级自查） |
| F-T3 | 页面骨架与筛选 | DashboardPage 重写：AppBar/StatusLine/TimeFilters/DatasetBar(B1 降级)/Banners + range.js | F-T1, F-T2 | T1–T5/D1/D2/G1–G3/S1/S2/S6 |
| F-T4 | 图表基件 | chartMath/Tooltip/useElementSize/ColumnChart/DonutChart/CountryBars | —（纯展示，可对假数据） | E5/E6/A1/V4/R3 |
| F-T5 | KPI 与横幅 | KpiSection（7 卡含 B1 降级）+ Banners 五类 | F-T1, F-T2 | K1–K8/S5/S7/S9/C8 |
| F-T6 | 每日与广告卡 | DailyCard×2（共享切换/yMax）+ AdCard | F-T4, F-T1 | E1–E8/A2/A3 |
| F-T7 | 对比与国家卡 | ConvCard + CountryCard | F-T4, F-T1 | C1–C8/N1–N4 |
| F-T8 | 订单表与 CSV | OrdersCard（筛选/排序/分页/空态/B1 类别列）+ CSV 下载 | F-T1 | O1–O9/X1/X4/X5（**mock 档仅验下载契约形状**——文件名/表头/编码属后端行为，真实下载走查归 §7.3 第二联调点，m11） |
| F-T9 | 同步与降级联调 | useSyncStatus（↻/轮询/进度/失败回落）+ 全降级路径 | F-T3, **B-T7**（后端就绪） | S4/S5/S7/S9、O9（网络面板仅我方域名） |
| F-T10 | 走查收尾 | 375/1280、明暗、双语、a11y、lint+build | 全部 | R1/R2/V1–V4/I2（对照 HTML 逐区块走查记录） |

### 7.3 并行与联调点

- 契约冻结后：B-T1→B-T2→B-T3 与 B-T6（仅依赖 T1）**并行**；F-T2/F-T4 无依赖即起；F-T3 起前端全线对 mock 推进。
- 硬联调点 ①：B-T7 合入 → F-T9 切真实后端 → 双侧对 fixtures 与真实响应做一次 diff 校验。
- 硬联调点 ②（m11）：B-T8 合入后做 **CSV 真实下载走查**（真实浏览器下载 → Excel/Numbers 打开核对 BOM 中文表头、CRLF、国家名本地化、金额两位小数、防注入列前缀、与订单表行数一致）——F-T8 的 mock 下载仅验证契约形状，覆盖不到后端 B-T8 的 X1–X5 真值；归属：backend-agent 出真实接口 + frontend-agent 走查记录。
- 分支与提交：统一 `feature/REQ-20261012-02-dashboard`，提交按 scope 拆（api/web/db/docs），中文提交信息带 REQ 编号。

---

## 8. 风险与决议记录

### 8.1 风险表

| 风险 | 影响 | 缓解 |
|---|---|---|
| 上游限流策略未知（429 未观测） | 92 天回填/手动大区间触发限流 | 并发 4 可配（AC-U7）；429/超时记日志不重试风暴；覆盖自愈使失败日下轮自动补 |
| v1.0.0 字段契约缺失（待确认 1） | 字段异常导致管道崩溃 | 规范化层防御式解析（缺失→NULL/默认 + warning 日志），单测覆盖缺字段样例 |
| 首次回填时长（92 窗×二分，估 2–5 分钟） | 部署后首屏数据不全 | 进度在 /sync/status 可见、看板可先看空态；不阻塞部署（RQ-5 告知预期） |
| 单进程假设（内存锁/进度态） | 多 worker 部署时重复同步 | 部署规范钉死单 uvicorn worker；如需扩展改 PG advisory lock |
| Decimal 新旧结果末位差（HTML 为 float+美分整数） | 与参考实现展示值偶有 ±0.01 差 | 属修正而非回归；用 `tools/export_diff.py` 抽查对账并在验证报告登记 |
| **上游 client_id 实测失效（2026-10-12 11:00 起 `401 client_id 不存在`，api.md 与 research/01 §8.4）** | B-T2/B-T3/B-T5 真实联调、RQ-7 整页率观察期被阻 | 开发不受阻：上游客户端与管道验收全部走 httpx MockTransport；**行动项：开工前向 netshort 申请换发凭据**，到位后补一次真实拉取冒烟 + 记录整页率 |
| 4 万行级内存聚合遇到数据增长 | summary 变慢 | S4 重估阈值（50 万行）迁 SQL/预聚合；索引已按区间查询预留 |

### 8.2 RQ 决议表（2026-10-12 用户拍板，全部冻结）

| # | 问题（回顾） | **决议** | 落点/备注 | 影响任务 |
|---|---|---|---|---|
| RQ-1 | CSV 国家名本地化需在后端引 `babel`（约 +11MB 纯 Python CLDR） | **引入 babel**（S5） | `pyproject.toml` 增依赖，B-T8 接线 | B-T8 |
| RQ-2 | ↻ 手动刷新语义：全区间重拉 vs 只补未覆盖日期 | **↻ = 全区间重拉**（对标 HTML「清缓存重载」，D4 字面） | §3.3.2 已按此固化；放弃增量补缺口方案 | B-T5、F-T9 |
| RQ-3 | 对比卡环图折叠：REQ AC-C2 原写「前 6+其他 ≤7」，参考 HTML 实际「前 7+其他 ≤8」 | **= 7：前 7 + `__other`（≤8 切片，照搬 HTML）** | 需改两处：`MAX_SLICES` 常量 + `convColors` 截断位（HTML:1632-1635 与 1579-1584）；REQ 的 AC-C2 由主对话同步改为 7，本设计全文按 7（§4.1/§5.2） | B-T6、F-T7 |
| RQ-4 | 订单 `amount` 最小单位位数：所有币种统一 /100 是否安全 | **照搬 HTML（统一 /100）+ 实现指引** | §2.5：`/100` 仅存在于展示层（API 主单位换算 + CSV）；规范化/存储保留 Decimal 原值；未来 0 位小数币种只需展示层加「币种→位数」映射，存储聚合零改动 | B-T5/B-T6/F 全渲染 |
| RQ-5 | 首次部署自动回填 92 天（约 2–5 分钟，看板先空态+进度可见） | **自动回填** | §3.3.3 首次运行等价 92 天回填，无需人工触发 | B-T5 部署验收预期 |
| RQ-6 | 时间范围/筛选状态是否进 URL | **不进 URL** | 刷新回落默认近 7 天视图；range.js 不写 location/query | F-T3 |
| RQ-7 | 上游真实单页上限未知（若 <1000 会常态化误判截断） | **照 D10 用 pageSize=1000 + 观察期记录整页率** | 日志统计「整页返回」频率；若常态满页→按实际调低 page_size（只动配置）；观察期依赖新凭据（见 §8.1 client_id 失效风险） | B-T2/B-T3 |

---

## 修订记录

**v2（2026-10-12，评审修复版）**：RQ-1~7 全部决议（§8.2 决议表）；reviewer 意见（结论「修复后可开发」）M1 + m1~m12 修复落点：

| 项 | 内容 | 落点 |
|---|---|---|
| M1 | summary 契约新增 `conv.no_usd_currencies`（无 USD 汇率币种清单，AC-C8 横幅数据源，聚合遍产出） | §4.1、§5.2、B-T6、F-T5 验收挂 AC-C8 |
| m1 | 冻结汇率表键数更正 28→**27**（HTML:764-768 逐键复核），单测断言键数与逐值相等 | §4.5、B-T6 |
| m2 | §5.2 示例数值自洽（completed 5959 + returned 57 = total 6016） | §5.2 |
| m3 | `countries.bars.__other.orders` 按「求和合并」语义修正（0→812） | §5.2 |
| m4 | 起止日期钳制补齐 `start>today → start=today`（HTML:1936-1937 两行都移植） | §6.4 |
| m5 | CSV 文件名不擅自分化：两档同名 `orders_all_{from}_to_{to}.csv`（REQ AC-X2 授权） | §5.4、§4.6-4 |
| m6 | 服务端「今天」钉死为 **UTC 日**（与数据日界同口径） | §3.3.2/§3.3.3 |
| m7 | 测试隔离显式化：conftest 强制 `SYNC_ENABLED=false`（不依赖凭据为空的隐式行为） | §3.4、B-T5 |
| m8 | §6.6 弃用 i18n 键清单补全（login 系列→auth 命名空间；netError/corsError/upstream 系列→新架构无对应物；dailySubType B1 暂弃） | §6.6 |
| m9 | 孤儿 `running` 行清理：lifespan 启动时改判 `failed`（进程重启场景） | §3.4、B-T5 |
| m10 | 新增风险：上游 client_id 2026-10-12 11:00 起实测失效（`401 client_id 不存在`）——MockTransport 开发不受阻，真实联调与 RQ-7 观察期需换发凭据（行动项：开工前向 netshort 申请） | §8.1 |
| m11 | CSV 真实下载走查归属明确：F-T8 mock 仅验契约形状，B-T8 合入后作 §7.3 第二硬联调点 | §7.2/§7.3 |
| m12 | 未知国家哨兵统一 `__unknown`（summary 国家条目与订单行 `country_key` 一致） | §5.3 |

另按决议新增 §4.6「与参考实现的差异登记」（Decimal 舍入修正、M1 字段、m4 钳制、m5 文件名、all 档 CSV 按 create_time 降序、服务端 UTC 日界六项）；全文按 RQ-3=7 复核（每日图前 6+其他=HTML:1212 `MAX_CURRENCY_SERIES`、对比环图前 7+其他=HTML:1632 `MAX_SLICES`、国家条前 9+其他=HTML:1720 `MAXROWS`，三处折叠常量各自独立已逐一对齐）。

**v1（2026-10-12）**：初版（含 RQ-1~7 待确认清单，默认值先行）。
