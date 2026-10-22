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

## 4. 任务包

**backend-task**

| # | 任务 | 文件 |
|---|---|---|
| B-T1 | Offer 模型 + 汇总导入 | `app/models/offer.py`、`app/models/__init__.py` |
| B-T2 | 迁移 0005（建表 + netshort 种子） | `alembic/versions/0005_offers.py` |
| B-T3 | schema + 路由 + 挂载 | `app/schemas/offers.py`、`app/api/v1/offers.py`、`app/api/v1/__init__.py` |
| B-T4 | 接口测试（角色门禁/形状/排序/空态） | `tests/test_offers_api.py` |

**frontend-task**

| # | 任务 | 文件 |
|---|---|---|
| F-T1 | api 函数 | `src/api/offers.js` |
| F-T2 | OffersPage | `src/pages/OffersPage.jsx` |
| F-T3 | 路由 + 侧边栏 + 更名 | `src/App.jsx`、`src/components/Sidebar.jsx` |
| F-T4 | i18n + 样式 | `src/i18n/{zh,en}.json`、`src/styles/dashboard.css` |

## 5. 风险清单

| 风险 | 对策 |
|---|---|
| 种子数据被当成上游接口数据误解 | REQ §1.2 明示自有配置；description 写明来源 |
| 测试库不可达导致 DB 测试 skip | 尝试起本地 dev 库跑全量；不可达则如实报告 skip |
| 客户角色误见分成条款 | 后端 403 强制 + 前端守卫/侧边栏双拦 |
| 侧边栏更名影响既有文案 | 仅 nav.* 词条变更；页面标题/副标题不动，grep 确认 |
