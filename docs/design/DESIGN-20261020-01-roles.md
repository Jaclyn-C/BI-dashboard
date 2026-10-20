# DESIGN-20261020-01 · 角色权限技术方案

> 对应 [REQ-20261020-01](../requirements/REQ-20261020-01-roles.md)。基线：main @ 1b3b710。
> 结论先行：`users.role` 单列四值（无 RBAC 表）+ 后端 `require_role` 路由依赖 + 前端角色守卫。
> token 与会话机制零改动（角色每请求查库，天然即时生效）。

## 1. 数据模型与迁移

### 1.1 users 表

```python
# app/models/user.py
ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "admin"
ROLE_CUSTOMER = "customer"
ROLE_PENDING = "pending"
ROLE_LEVEL = {super_admin: 3, admin: 2, customer: 1, pending: 0}
ROLE_ALL = (ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_CUSTOMER, ROLE_PENDING)

role: Mapped[str] = mapped_column(String(16), nullable=False, default=ROLE_PENDING, server_default=ROLE_PENDING)
```

- 合法值由应用层（Pydantic Literal + 服务层常量）约束，不加数据库 CHECK（与仓库现有风格一致）。
- **Alembic 迁移**（数据库变更唯一入口）：`add_column users.role, String(16), nullable=False, server_default='pending'`——存量账号自动落 `pending`。

### 1.2 超管 bootstrap（app 启动幂等）

- `config.py` 新增 `SUPER_ADMIN_EMAIL: EmailStr | None = None`（.env 模板同步加注释行）。
- `main.py` lifespan 内、DB 就绪后执行 `ensure_super_admin(db)`：
  - 邮箱未配置 → 跳过（开发/测试环境无感）；
  - 账号存在且非 super_admin → 提为 super_admin（**不 bump credential_version**，无需重登）；
  - 账号不存在 → warning 日志跳过；
  - 重复启动无副作用（已是 super_admin 则不动）。

## 2. 后端 API 契约

### 2.1 现有接口变化

**认证三件响应带角色**：`UserPublic` 增加 `role: Literal["super_admin","admin","customer","pending"]`，
`/api/v1/auth/login`、`/register`、`/me` 响应自动携带。入参、错误码不变（向后兼容，只加字段）。

**路由权限依赖**（`app/api/deps.py` 新增）：

```python
def require_role(*allowed: str):  # 依赖工厂，先走 get_current_user 再判角色
```

| 路由（/api/v1/dashboard） | 现状 | 改为 |
|---|---|---|
| `GET /summary`、`GET /orders`、`GET /orders.csv`、`POST /sync`、`GET /sync/status` | 登录即可 | `require_role(ADMIN, SUPER_ADMIN)` |
| `GET /customer-orders`、`GET /customer-orders.csv` | 登录即可 | `require_role(CUSTOMER, ADMIN, SUPER_ADMIN)` |

- 未通过 → `403 {"error":{"code":"FORBIDDEN","message":"insufficient role"}}`（沿用现有错误形状；
  `pending` 用户任何数据接口即此 403，登录/注册/找回等认证接口不受影响）。
- 401 语义不变（未登录/凭证失效），前端先判 401 再判 403。

### 2.2 新增用户管理接口（`app/api/v1/users.py`，tag=users）

**`GET /api/v1/users`** — `require_role(ADMIN, SUPER_ADMIN)`

响应（按 created_at 倒序，全量返回不分页——账号量级 ≤ 几十）：

```json
{"users": [{"id": 1, "email": "a@b.c", "nickname": "a", "role": "admin",
            "created_at": "...", "last_login_at": "..." | null}]}
```

**`PATCH /api/v1/users/{user_id}/role`** — `require_role(ADMIN, SUPER_ADMIN)`

请求体：`{"role": "admin" | "customer" | "pending"}`（Pydantic Literal，`super_admin` 与其他值 → 422）。

判定顺序与错误（全部沿用 `{"error":{"code","message"}}` 形状）：

1. 目标用户不存在 → `404 USER_NOT_FOUND`
2. 等级规则（REQ §1.3，服务层单函数 `can_assign_role(operator, target, new_role)`）：
   `operator != target` 且 `LEVEL[operator.role] > LEVEL[target.role]` 且 `new_role ∈ {admin,customer,pending}` 且 `LEVEL[new_role] ≤ LEVEL[operator.role]`
   不满足 → `403 FORBIDDEN`（覆盖：动平级/上级/自己）
3. 成功 → `200` 返回更新后 UserPublic（含新 role）。不 bump credential_version（在线会话不中断，角色下一请求生效）

## 3. 前端方案

### 3.1 会话与 403 处理

- `AuthProvider` 的 `user` 增加 `role`（来自 login / register / me 响应，已有字段透传）。
- `src/api/client.js` 拦截 403：重拉 `GET /me` 更新 user（守卫随新 role 自动跳转）；401 行为不变。
  用户被改角色后，下一次任意请求即触发跳转——无需轮询。

### 3.2 路由守卫（App.jsx，在 RequireAuth 内层再加角色判定）

| 路由 | 允许角色 | 其余去向 |
|---|---|---|
| `/`（DashboardPage） | admin / super_admin | customer → `/customer`；pending → `/pending` |
| `/customer`（CustomerViewPage） | customer / admin / super_admin | pending → `/pending` |
| `/users`（新 UsersPage） | admin / super_admin | customer → `/customer`；pending → `/pending` |
| `/pending`（新 PendingPage） | pending | 其余 → `/` |
| `/login` `/register` `/forgot` | 不变 | 不变 |

- `pending` 访问任何受护路由统一落到 `/pending`，不做局部放行。

### 3.3 新页面

- **PendingPage**：复用 AuthCard 布局，一句提示（i18n：`等待管理员分配权限` / `Waiting for an administrator to assign your access`）+ 退出登录按钮，无其他元素。
- **UsersPage**：极简文字表格（邮箱 / 昵称 / 角色 / 注册时间 / 最近登录）+ 行内文字操作
  「设为管理员 / 设为客户 / 撤销权限」（当前非可赋角色不渲染对应项；自己与平级/上级行不渲染操作）。
  操作即时生效、行内刷新；不做确认弹窗（操作可逆——重新赋权即可）。

### 3.4 导航与 i18n

- 内部页导航（现 Dashboard ↔ 客户视图切换处）增加「用户管理」入口，仅 admin / super_admin 渲染；
  customer 登录后导航只含客户视图。
- 新增 i18n key（en/zh 同步）：pending 提示、用户管理页表头/角色名/操作/成功与失败文案、FORBIDDEN 错误映射。

## 4. 任务包

### backend-task（顺序执行）

1. **模型与迁移**：User.role 常量与列 + Alembic 迁移 + config SUPER_ADMIN_EMAIL + lifespan `ensure_super_admin`；测试：迁移后存量 pending、bootstrap 幂等/缺账号跳过
2. **require_role + 路由挂载**：deps 依赖工厂；dashboard 七个端点按 §2.1 挂权限；UserPublic.role 透出；测试：权限矩阵（4 角色 × 2 类接口 + pending 全 403）、角色变更即时生效（旧 token 复用）
3. **用户管理接口**：GET /users、PATCH role + `can_assign_role`；测试：矩阵（admin 动客户 ✓ / 动管理员 ✗ / 动超管 ✗ / 改自己 ✗ / 请求 super_admin 422、超管全可动）

### frontend-task（依赖 backend §2 契约，可并行开工）

1. **会话层**：client 403 拦截重拉 /me；AuthProvider 透传 role
2. **守卫与页面**：路由表改造 + PendingPage + 跳转分流
3. **用户管理页**：UsersPage + api 封装 + 导航入口 + i18n（en/zh）

### 验证义务

后端每任务 `ruff check .` + `pytest`；前端 `pnpm lint`（改构建配置时 `pnpm build`）。结果如实写入交付报告。

## 5. 风险清单

| 风险 | 应对 |
|---|---|
| 迁移把线上存量账号全落 pending，部署后没人能赋权 | **上线顺序硬性要求**：先在服务器 `.env` 配 `SUPER_ADMIN_EMAIL` 再拉新版镜像；启动即自动提权，超管登录后给其余账号赋权 |
| 用户在角色被改后停留旧页面 | 后端 403 已兜底；前端下一请求即重拉 /me 跳转，无数据泄露窗口 |
| SUPER_ADMIN_EMAIL 填错/账号不存在 | 启动 warning 日志；修正 .env 重启即恢复（幂等） |
| 忘记给某个内部同事赋权 | 其登录见 pending 提示页，找超管/管理员赋权即可，无数据暴露 |
| .env 泄露邮箱 | 邮箱非凭据，且不入库不入 git（.env 模板只含占位注释） |
