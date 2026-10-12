# 评审与提交工作流（review-flow）

> 前置：[development-flow.md](development-flow.md) 已通过 test-agent 验证。本流程结束于 Git Commit。

```
变更集 → Reviewer 评审 →（问题回开发 Agent 修复 → 复审）→ Git Commit
```

---

## 步骤 1：代码评审

| 项 | 说明 |
|---|---|
| **责任 Agent** | reviewer-agent（**只读**，tools 无 Write/Edit/Bash） |
| **输入文件** | 变更集（文件清单 / diff / git 范围）；test-agent 验证报告；CLAUDE.md 第 9 节红线基线；对应 REQ/DESIGN |
| **输出文件** | 评审报告（对话交付）：总结论（可合入 / 修复后可合入 / 阻断）+ 问题列表（文件:行号、违反条目、severity） |
| **验收标准** | ① 每个问题均有代码证据，无臆测；② 红线检查覆盖 CLAUDE.md 第 9 节全部 10 条；③ 六个评审维度全查：红线 / 金额正确性 / 供应商安全 / 上游健壮性 / 一致性 / 测试质量；④ 风格问题未标为 blocker |

### 评审维度优先级（本项目定制）

1. **红线**（blocker）：真实凭据、口径变更无 REQ、float 金额、供应商越权、模型无迁移、main 直提
2. **金额正确性**（blocker~major）：口径与 business.md 一致性、全链路 Decimal
3. **供应商安全**（major）：鉴权、隔离、限流、OpenAPI 文档质量
4. **上游健壮性**（major）：token 缓存、二分边界、降级、幂等
5. **一致性 / i18n / 深色模式**（major~minor）

## 步骤 2：问题修复（有问题时）

| 项 | 说明 |
|---|---|
| **责任 Agent** | 按归属分发：backend-agent（`backend/**`）、frontend-agent（`frontend/**`） |
| **输入文件** | 评审问题列表（按归属过滤）+ 原任务包 |
| **输出文件** | 修复变更 + 每条问题的处理结果（fixed / skipped + 理由） |
| **验收标准** | ① blocker/major 全部处理或经用户同意豁免；② 修复是 surgical fix（不扩大改动面）；③ 修复后重新走 test-agent 验证 |

## 步骤 3：复审

| 项 | 说明 |
|---|---|
| **责任 Agent** | reviewer-agent |
| **输入文件** | 修复变更 + 原评审报告 |
| **输出文件** | 复审结论：逐条 closed / open；最终"可提交"判定 |
| **验收标准** | ① 原问题逐条核销；② 修复本身通过红线检查 |

## 步骤 4：Git Commit

| 项 | 说明 |
|---|---|
| **责任** | 由主对话（或用户授权的 Agent）在仓库根目录执行 git 命令 |
| **前提** | 当前分支为 `feature/<REQ编号>-<简述>`（非 main）；已通过步骤 1-3 |
| **要求** | ① 提交前 `git diff` 完整核对；② 提交信息 `type(scope): 中文描述（REQ 编号）`，scope ∈ api/web/db/ai/docs，一次提交聚焦一件事，跨前后端拆开提交；③ 未提交 `.env`、`node_modules/`、`dist/`、`.venv/`、`__pycache__/`、`.claude/settings.local.json`；④ 涉及迁移的变更在提交说明中列出执行步骤；⑤ 不 merge 到 main、不推送 main——合入由用户执行；⑥ 不使用 `--no-verify`、不强推 |

## 出口条件（流程闭环）

- 提交完成；若本次变更改变了架构/业务事实，对应 Agent 已更新 `.claude/memory/`。

## 回退机制

- 任一步骤发现**方案级**缺陷（而非实现缺陷）：停止流程，回 requirement-flow / architect-agent 修文档再入流。
- 用户在任何步骤均可否决；否决后按用户指示回退到对应步骤。
