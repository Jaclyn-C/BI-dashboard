# DESIGN-20261022-02 · Offer 管理页面技术方案

> 对应 [REQ-20261022-02](../requirements/REQ-20261022-02-offers-page.md)。基线：feature/REQ-20261022-01-sidebar-layout @ b797131。
> 结论先行：新增 `offers` 表（Alembic 0005，含 netshort 种子）+ 只读 `GET /api/v1/offers`（admin+）+ 前端 OffersPage；顺带侧边栏「客户视图」→「客户订单」。

## 1. 数据模型与迁移

```python
# app/models/offer.py
class Offer(Base):
    __tablename__ = "offers"
    id: BigInteger Identity pk
    code: String(32) unique        # 稳定标识，如 'netshort'
    name: String(100)              # 展示名
    description: String(500) | None
    supplier_share: Numeric(5, 4)  # 供应商分成比例，0.5000 = 50%（金额纪律：Numeric）
    in_use: bool = False           # 是否在用
    sort_order: int = 0            # 展示排序
    created_at / updated_at        # 同 users 惯例（func.now()）
```

**迁移 0005_offers**：create_table + 种子 insert netshort（`supplier_share=0.5, in_use=true, sort_order=0`，description 说明其为当前对接上游）。手写（单表新增+数据种子，无 alter 风险；与 0004 风格一致）。

## 2. API 契约

**`GET /api/v1/offers`** — `require_role(ADMIN, SUPER_ADMIN)`，响应：

```json
{"offers": [{"id": 1, "code": "netshort", "name": "netshort 短剧 CPS",
             "description": "…", "supplier_share": "0.5000",
             "supplier_share_pct": "50", "in_use": true, "sort_order": 0}]}
```

- 排序：`in_use desc → sort_order → id`（REQ AC-4 稳定排序）。
- `supplier_share`：Decimal 字符串（精度保真）；`supplier_share_pct`：后端预格式百分比字符串（前端零运算，直接拼 `%`）。
- 路由挂 `app/api/v1/offers.py`（tags=["offers"]），prefix `/offers`（同 users 顶层资源惯例，不挂 dashboard 前缀——非看板数据）。

## 3. 前端方案

- `src/api/offers.js`：`listOffers()`（走统一 client）。
- `src/pages/OffersPage.jsx`（路由 `/offers`，`RequireRole allow=['admin','super_admin']`）：AppBar + 两板块；数据一次拉全量，前端按 `in_use` 拆板块（数据量小，无需两接口）；加载/错误态沿 statusline/banner 惯例。
- 侧边栏：ITEMS 加 `{ key: 'nav.offers', to: '/offers' }`（客户订单之后、用户管理之前），ALLOWED admin+ 加 `/offers`。
- 「客户视图」→「客户订单」：仅改 `nav.customer` 词条（zh 客户订单 / en Customer orders），路由 `/customer` 与页面内容不动。
- 样式：`.offer-sec`（板块标题）、`.offer-grid`（auto-fill minmax 卡片栅格）、`.offer-card`（surface/border 变量）、`.offer-share`（大号比例数字）、`.offer-badge`（在用标记，文字样式无图标）；≤900px 单列。

## 4. 订单上游列/筛选、mock 隔离与供应商收益（REQ §1.4/§1.5，用户追加定稿）

- **迁移 0006**：`orders.upstream_code String(32) NOT NULL server_default 'netshort'`；同步 upsert 不写此列（恒取默认），存量订单自动落 netshort。
- **上游筛选**：`orders_query(upstream=…)` SQL 过滤；两订单接口加 `upstream` 参数 + 响应 `upstreams`（区间动态选项，`range_upstreams` 升序去重）；前端筛选框与币种同模式（失效回落 all）。CSV 导出**不加**该列（对账工具 export_diff 依赖现有列序，保持不动）。
- **迁移 0007**：`mock_orders` 表（结构同 orders 子集 + upstream_code，唯一 (upstream_code, order_id)）——**只建表不带数据**，生产恒空表，真实链路不读。
- **`GET /offers/earnings`**（admin+，`offers_service.offer_earnings`）：在用 offer × {Σincluded 订单 usd_minor（orders ∪ mock_orders 分表聚合）× supplier_share}；全程 Decimal，输出 `money_exact` 真值字符串；响应含合计三件套 + 逐 offer 明细。红线 12 不涉（内部管理页，非对外接口）。
- **mock 种子**：`tools/seed_mock_data.py`（幂等）：mock1 在用 30%（参与收益）、mock2 仅展示 65%；每 mock 上游 10 笔订单（单号 1..10、$1.00），order_class 用生产同一 `classify_order_no` 打标；只写开发库。
- **前端收益板块**：OffersPage 第三板块，选择芯片（全部/多选）纯过滤展示（零金额运算），合计行仅「全部」态显示。

## 5. 任务包

**backend-task**

| # | 任务 | 文件 |
|---|---|---|
| B-T1 | Offer 模型 + 汇总导入 | `app/models/offer.py`、`app/models/__init__.py` |
| B-T2 | 迁移 0005（建表 + netshort 种子） | `alembic/versions/0005_offers.py` |
| B-T3 | schema + 路由 + 挂载 | `app/schemas/offers.py`、`app/api/v1/offers.py`、`app/api/v1/__init__.py` |
| B-T4 | 接口测试（角色门禁/形状/排序/空态） | `tests/test_offers_api.py` |
| B-T5 | 迁移 0006 + Order/OrderRow 上游字段/筛选 + 测试 | `alembic/versions/0006_orders_upstream.py`、`app/models/order.py`、`app/services/orders_query.py`、`app/schemas/dashboard.py`、`app/api/v1/dashboard.py`、`tests/test_dashboard_api.py` |
| B-T6 | MockOrder 模型 + 迁移 0007（空表） | `app/models/mock_order.py`、`alembic/versions/0007_mock_orders.py` |
| B-T7 | 收益服务 + /offers/earnings + 测试 | `app/services/offers_service.py`、`app/api/v1/offers.py`、`tests/test_offers_api.py` |

**frontend-task**

| # | 任务 | 文件 |
|---|---|---|
| F-T1 | api 函数 | `src/api/offers.js` |
| F-T2 | OffersPage（三板块 + 收益选择器） | `src/pages/OffersPage.jsx` |
| F-T3 | 路由 + 侧边栏 + 更名 | `src/App.jsx`、`src/components/Sidebar.jsx` |
| F-T4 | i18n + 样式 | `src/i18n/{zh,en}.json`、`src/styles/dashboard.css` |
| F-T5 | OrdersCard 首列上游 + 上游筛选框 | `src/components/dashboard/OrdersCard.jsx`、`src/dashboard/use{,Customer}Orders.js`、`src/api/dashboard.js`、两页面 |

**tools**

| # | 任务 | 文件 |
|---|---|---|
| T-T1 | mock 演示数据种子（offer 在用态 + 10 笔订单/上游，开发库专用） | `tools/seed_mock_data.py` |

## 6. 风险清单

| 风险 | 对策 |
|---|---|
| 种子数据被当成上游接口数据误解 | REQ §1.2 明示自有配置；description 写明来源 |
| 测试库不可达导致 DB 测试 skip | 尝试起本地 dev 库跑全量；不可达则如实报告 skip |
| 客户角色误见分成条款 | 后端 403 强制 + 前端守卫/侧边栏双拦 |
| 侧边栏更名影响既有文案 | 仅 nav.* 词条变更；页面标题/副标题不动，grep 确认 |
