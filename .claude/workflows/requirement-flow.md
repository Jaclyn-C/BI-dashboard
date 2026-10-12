# 需求工作流（requirement-flow）

> 适用：需求进入 → 技术方案定稿。结束后进入 [development-flow.md](development-flow.md)。总规则见 `CLAUDE.md`；Agent 定义见 `.claude/agents/`。

```
用户需求 → Product Agent → Architect Agent → 方案评审（Reviewer 把关）→ 任务包就绪
```

## 产物目录约定

| 目录 | 内容 | 命名 |
|---|---|---|
| `docs/requirements/` | 需求说明 | `REQ-<YYYYMMDD>-<NN>-<简述>.md` |
| `docs/design/` | 技术方案与任务包 | `DESIGN-<对应REQ编号>-<简述>.md` |

## 步骤 1：需求分析

| 项 | 说明 |
|---|---|
| **责任 Agent** | product-agent |
| **输入** | 用户原始需求；`.claude/memory/business.md`、`api.md`；参考 HTML（涉既有功能时） |
| **输出** | `REQ-*.md`：背景、功能描述、验收标准（可测试）、口径变更清单（旧值→新值）、影响面、待确认项 |
| **验收标准** | ① 验收标准可判定通过/失败；② 口径变更逐条列出旧值→新值；③ 影响面覆盖供应商接口与 i18n；④ 业务不确定点全部列入待确认而非自行假设；⑤ 用户已确认待确认项的答案 |

## 步骤 2：技术方案设计

| 项 | 说明 |
|---|---|
| **责任 Agent** | architect-agent |
| **输入** | 步骤 1 的 REQ；`.claude/memory/architecture.md`、`api.md`、`business.md`；现状代码勘察（自行 Read/Grep，禁止凭记忆假设） |
| **输出** | `DESIGN-*.md`：技术方案、API 契约（URL/入出参/错误码）、数据模型变更方案、backend-task / frontend-task 任务包（含依赖顺序）、风险清单 |
| **验收标准** | ① API 契约完整，前后端可并行开发；② 金额链路全 Decimal/Numeric；③ 供应商隔离与鉴权方案明确；④ 上游失败降级策略明确；⑤ 违禁选型为零（TS/换库等）；⑥ 对外契约破坏性变更已标注"需用户确认" |

## 步骤 3：方案把关（轻量评审）

| 项 | 说明 |
|---|---|
| **责任 Agent** | reviewer-agent（只读） |
| **输入** | REQ + DESIGN；CLAUDE.md 规则基线 |
| **输出** | 方案评审意见（对话交付，阻断项回 architect-agent 返工） |
| **验收标准** | ① 红线零违反；② 方案与需求验收标准一一对应，无遗漏；③ 与现有代码冲突点已识别 |

## 出口条件（进入开发）

- REQ 经用户确认；DESIGN 通过评审；任务包齐备且依赖关系明确。

## 角色约束

- product / architect 均**无业务代码写权限**（文档层与代码层隔离）。
- 需求或方案改变业务/架构事实时，责任 Agent 同步更新 `.claude/memory/business.md` / `architecture.md`。
