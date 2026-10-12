# 上游 API 事实（api）

> 来源：飞书《海外CPS-对外API文档（OAuth）v1.2.0》+ `docs/research/01-调研发现与逆向分析.md`（2026-10-12 提炼）。**凭据一律 .env，本文件不存真实值。**

## 上游 netshort CPS（新系统运行时唯一出站依赖）

- 环境：测试 `https://adminapi.test.netshort.net/test-api/cps/`，商用 `https://adminapi.netshort.com/prod-api/cps/`
- 鉴权：OAuth 2.0 Client Credentials——`POST /open/oauth2/token`（HTTP Basic clientId:clientSecret，或 form 凭证），token 默认 **3600 秒**，业务接口 `Authorization: Bearer`；MD5 签名仅存量兼容，不用
- 统一响应信封 `{code, msg, data, traceId}`
- **8 个开放接口**：oauth2/token、sign/compute、shortPlay/list、shortPlay/info、shortPlay/playUrl、material/list、order/list、order/adSummary
  - 当前只用 3 个：`/open/oauth2/token`、`/open/order/list`、`/open/order/adSummary`
  - ⚠️ v1.2.0 只更新了鉴权部分，业务入出参沿用 v1.0.0——**v1.0.0 未拿到，字段级契约缺失**（待确认 1）；scope 表末尾有空行，不排除存在未列出接口
- 分页行为：`/open/order/list` 上游**无 hasMore** 字段；以"整页返回"判定可能截断（请求 pageSize=1000）→ 服务端拉取需**窗口化 + 时间窗二分补全**（照搬 HTML 逻辑落到服务端）
- `createTime` 疑似 UTC 且有数十分钟同步延迟（B5）——存储层存原值，展示层定时区

## 前开发自建后端（api.tfctechnology.com）——重写对象，禁止运行时依赖

- 代码已遗失。`/auth/login` 与 `/data/partner/order/report` 由我方重写；契约兼容规格见 research/01 §4.2（`{code,msg,data}` 信封、`hasMore` 标志、字段改名 `orderAmount → usdOrderAmount`、100 行截断改真分页）
- 其内部管道：换票 → 调上游 order/list → **黑盒过滤（B1）** → 字段改名 → 100 行截断
- 唯一例外：**Phase 0 数据记录器**可临时调用它留存分类标签真值（老后端随时可能下线，每多跑一天多一天真值；调研期是否允许查询 = 待确认 4）
- 老后端账号 REDACTED-USER/REDACTED-PASSWORD（值已抹除） 已随 HTML 泄露，按已失效处理；上游密钥轮换待办（待确认 6）

## 下游接口（我们提供给供应商的）

- 待需求阶段定义。原则已定：`/api/v1/supplier/**`、API key 鉴权、按供应商隔离、FastAPI OpenAPI（`/docs`）作为对外文档；供应商账号迁移 = B4 待确认
