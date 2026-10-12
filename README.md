# Partner Dashboard

合作伙伴收益数据平台：上游取数落库 → 内部看板（React）→ 处理 → 下游供应商 API（FastAPI）。

| 入口 | 说明 |
|---|---|
| `CLAUDE.md` | Agent 总规则（技术栈、规范、红线） |
| `.claude/agents/` | 6 个角色定义：product / architect / backend / frontend / test / reviewer |
| `.claude/workflows/` | requirement / development / review 三条工作流 |
| `.claude/memory/` | 项目知识库（业务口径、上游 API 事实、架构、部署） |
| `docs/reference/visualisation.html` | 参考实现（行为规格，凭据已抹除） |
| `docs/reference/上游CPS开放API文档-v1.2.0.md` | 上游飞书文档全文还原 + 我方实测补充（上游客户端实现依据） |
| `docs/requirements/`、`docs/design/` | 需求与设计文档 |

开发环境搭建待 `backend/`、`frontend/` 初始化后补充。
