# DESIGN-20261022-01 · 侧边栏导航布局技术方案

> 对应 [REQ-20261022-01](../requirements/REQ-20261022-01-sidebar-layout.md)。基线：feature/REQ-20261020-01-roles @ a49b515（含角色守卫与用户管理页，本需求依赖其页面集）。
> 结论先行：**纯前端改版**——新增 `Sidebar` 组件 + `.shell` 页面外壳；路由、后端、数据链路零改动；AppBar 移除 `navs` 跳转按钮，全局操作原样保留。

## 1. Sidebar 组件（`frontend/src/components/Sidebar.jsx`）

```jsx
const ITEMS = [
  { key: 'nav.dashboard', to: '/' },      // 数据看板（REQ §1.3 定名）
  { key: 'nav.customer', to: '/customer' },
  { key: 'nav.users', to: '/users' },
]
const ALLOWED = {
  super_admin: ['/', '/customer', '/users'],
  admin: ['/', '/customer', '/users'],
  customer: ['/customer'],
}
```

- 条目按 `user.role` 过滤（与 App.jsx `RequireRole` 路由守卫同一套可见性：admin+ 全见、customer 仅客户视图）；pending 不挂 Sidebar（PendingPage 不接入外壳），无 fallback 渲染必要，`ALLOWED[role]` 未命中即空列表。
- 当前项判定：`location.pathname === item.to`（精确匹配，`/` 前缀匹配会误命中全站，禁用 NavLink 默认行为）。
- 当前项标识：`aria-current="page"` + 样式 `.sideitem.active`（文字加粗强调 + 左侧 3px 标记线，`::before` 实现）；无图标（红线 13）。
- 点击当前项 = Link 同路径导航，React Router 不重挂载组件、hooks 入参未变不重拉数据，等效无操作（REQ §1.1 步骤 1）。

## 2. 页面外壳接入（`.shell`）

三个登录后页面统一改为：

```jsx
<div className="shell">
  <Sidebar />
  <div className="shell-main">
    <div className="wrap"> …原页面内容（AppBar + 内容区）原封不动… </div>
  </div>
</div>
```

- DashboardPage（外层 TooltipProvider 保留，包住整个 shell）、CustomerViewPage、UsersPage。
- PendingPage 与认证三页不接入，维持现状。

## 3. AppBar 变化

- 删除 `navs` prop 及其渲染块（顶栏跳转按钮由侧边栏承接，REQ §1.2）。
- 其余（标题/副标题/状态行/语言切换/数据说明/刷新/退出）逐项不动。
- 三个页面对应清理：DashboardPage 删 navs 数组；CustomerViewPage 删 navs（`user` 仅此处使用，一并从解构移除）；UsersPage 删 navs（`navigate` 仅此处使用，一并移除 import）。

## 4. 样式（dashboard.css「页面外壳」节新增）

```css
.shell   { display: flex; min-height: 100dvh; }
.sidebar { position: sticky; top: 0; height: 100dvh; width: 176px; flex: none;
           display: flex; flex-direction: column; gap: 4px; padding: 20px 12px;
           border-right: 1px solid var(--border); }
.sideitem{ 文字链接，默认 var(--ink2)，hover 转强调 }
.sideitem.active { var(--ink) + 500 字重；::before 左侧 3px var(--series) 标记线贴侧边栏右缘 }
```

- 颜色全部走 theme.css 既有变量（明暗自适应，无新增变量）。
- `.shell-main { flex: 1; min-width: 0; }`，`.wrap` 原样嵌套（max-width 1240px 居中逻辑不变）。

**窄屏（≤900px，media query 与现有断点一致）**：`.shell` 转纵向，`.sidebar` 转横向导航行（`position: static; height: auto; border-bottom` 代替右边线，active 标记线转文字下划线）。
⚠️ 实现偏差（对 REQ §2）：受 DOM 结构所限（AppBar 在 `.wrap` 内、与 Sidebar 非同级），窄屏导航行位于页面最顶（顶栏**之上**）而非顶栏之下；属纯视觉顺序差异，记录于交付说明，如不接受需把 AppBar 提升为 shell 级组件（改动面扩大 3 页结构，暂不做）。

## 5. i18n（zh/en 同步）

| 动作 | key | zh | en |
|---|---|---|---|
| 新增 | `nav.label` | 主导航 | Main navigation |
| 新增 | `nav.dashboard` | 数据看板 | Data dashboard |
| 新增 | `nav.customer` | 客户视图 | Customer view |
| 新增 | `nav.users` | 用户管理 | Users |
| 删除 | `customer.navTo` / `customer.navBack` / `users.navTo` | —（仅被删除的顶栏跳转按钮引用） | — |

## 6. frontend-task

| # | 任务 | 文件 |
|---|---|---|
| F-T1 | Sidebar 组件 | `src/components/Sidebar.jsx`（新增） |
| F-T2 | 三页接外壳 + 删 navs | `src/pages/DashboardPage.jsx`、`CustomerViewPage.jsx`、`UsersPage.jsx` |
| F-T3 | AppBar 删 navs prop | `src/components/dashboard/AppBar.jsx` |
| F-T4 | 样式 + 窄屏 | `src/styles/dashboard.css` |
| F-T5 | i18n 增删 | `src/i18n/zh.json`、`en.json` |

backend-task：无。

## 7. 风险清单

| 风险 | 对策 |
|---|---|
| 路由/权限回归 | 路由表零改动；Sidebar 可见性与 RequireRole 同源映射，越权访问仍被守卫拦 |
| 看板内容被误动 | 页面内容区不碰，仅包壳与删 navs，验收逐项对照 REQ AC-4 |
| 窄屏遮挡回归（AC-R1） | 侧边栏横排换行 + 375px 验证 |
| i18n 残留 key | 删 key 后 grep 确认零引用 |
