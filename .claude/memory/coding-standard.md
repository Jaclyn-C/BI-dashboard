# 编码与验证标准（coding-standard）

## 验证命令（各 Agent 的最低义务）

| 侧 | 命令 | 时机 |
|---|---|---|
| backend | `ruff check .` | 每次改动后 |
| backend | `pytest` | 每次改动后（能跑范围，如实报告） |
| backend | `alembic upgrade head`（dev 库） | 涉迁移时 |
| frontend | `pnpm lint` | 每次改动后 |
| frontend | `pnpm build` | 动构建配置/依赖时 |

## 命名与风格

- Python：snake_case，遵循 FastAPI 惯例；新模块带简短 docstring；与周围代码风格一致优先于通用最佳实践
- React：组件文件 PascalCase；hooks `useXxx`；样式优先 CSS 变量（深浅色一套变量切换）
- i18n key：按页面/组件分组（如 `dashboard.kpi.total`）
- API 路径：版本前缀 `/api/v1`；具体命名以 DESIGN 契约为准

## 金额纪律（最高优先级）

- Python 端 `decimal.Decimal`；DB 端 `Numeric`；测试断言用 Decimal/字符串精确比较，禁止 float 断言
- 前端不运算只渲染；格式化用后端给定字符串或 Intl 展示

## Git

- 分支 `feature/<REQ编号>-<简述>`；提交 `type(scope): 中文描述（REQ 编号）`，scope ∈ api/web/db/ai/docs
- 跨前后端的变更拆成多个 scope 单一的提交，不混提
