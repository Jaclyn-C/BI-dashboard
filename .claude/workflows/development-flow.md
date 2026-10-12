# 开发工作流（development-flow）

> 前置：[requirement-flow.md](requirement-flow.md) 已产出 DESIGN（含任务包）。后续：[review-flow.md](review-flow.md)。

```
建分支 feature/<REQ编号>-<简述>（禁止直接改 main）
      ↓
DESIGN 任务包 → Backend Agent ∥ Frontend Agent → Test Agent 验证 → 交付评审
```

两个开发 Agent 并行时的分工边界（防冲突）：

| Agent | 独占目录 |
|---|---|
| backend-agent | `backend/**`、根 `.env.example` |
| frontend-agent | `frontend/**` |

---

## 步骤 1a：后端开发

| 项 | 说明 |
|---|---|
| **责任 Agent** | backend-agent |
| **输入文件** | DESIGN 的 backend-task（API 契约）；`.claude/memory/business.md`（口径）、`api.md`；参考 HTML（口径存疑时对照） |
| **输出文件** | `backend/**` 代码 + Alembic 迁移；变更说明（接口清单、迁移执行说明、ruff/pytest 结果、未验证项） |
| **验收标准** | ① `ruff check .` 通过、`pytest` 通过（或如实报告无法运行的原因）；② 金额计算全 Decimal 且有单测；③ 模型变更配齐迁移；④ 无真实凭据入码；⑤ 口径与 business.md / 参考 HTML 一致 |

## 步骤 1b：前端开发（与 1a 并行）

| 项 | 说明 |
|---|---|
| **责任 Agent** | frontend-agent |
| **输入文件** | DESIGN 的 frontend-task（与 1a 同源的 API 契约）；参考 HTML（视觉/文案/变量底稿） |
| **输出文件** | `frontend/**` 变更；变更说明（页面/组件、api 函数、i18n 完成度、lint 结果） |
| **验收标准** | ① `pnpm lint` 通过；② 请求全走 `src/api/` 且与契约一致；③ 文案全 i18n（en/zh 对齐）；④ 前端零金额计算；⑤ 深色模式走 CSS 变量 |

## 步骤 2：验证

| 项 | 说明 |
|---|---|
| **责任 Agent** | test-agent |
| **输入文件** | 两个开发 Agent 的变更说明；DESIGN 契约；business.md 口径基准 |
| **输出文件** | 验证报告（已验证 / 失败附 文件:行号 / 跳过附原因）+ 问题清单；必要时新增测试 |
| **验收标准** | ① ruff + pytest + pnpm lint 均执行且结果如实记录；② 静态核查全查：前后端契约、模型↔迁移对齐、供应商隔离、i18n 对齐、凭据扫描；③ 未验证项与已验证严格区分，无夸大 |

## 出口条件（进入评审）

- 阻断级问题为零；验证报告已产出。
- 开发中发现 DESIGN 偏差：小偏差自行处理并在变更说明记录；接口契约/表结构级偏差**必须回 architect-agent** 更新 DESIGN 后再继续。
