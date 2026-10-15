# 上游 API 事实（api）

> 来源：飞书《海外CPS-对外API文档（OAuth）v1.2.0》+ `docs/research/01-调研发现与逆向分析.md`（2026-10-12 提炼）。**凭据一律 .env，本文件不存真实值。**
> **上游文档还原**：整理版 `docs/reference/上游CPS开放API文档-v1.2.0.md`（原文 + 我方实测补充，实现上游客户端前必读）；逐字完整存档 `docs/reference/上游CPS开放API文档-v1.2.0-完整存档.md`（全部 239 块 100% 覆盖，引用原文细节以此为准）。

## 上游 netshort CPS（新系统运行时唯一出站依赖）

- 环境：测试 `https://adminapi.test.netshort.net/test-api/cps/`，商用 `https://adminapi.netshort.com/prod-api/cps/`
- 鉴权：OAuth 2.0 Client Credentials——`POST /open/oauth2/token`（HTTP Basic clientId:clientSecret，或 form 凭证），token 默认 **3600 秒**，业务接口 `Authorization: Bearer`；MD5 签名仅存量兼容，不用
- 统一响应信封 `{code, msg, data, traceId}`
- **8 个开放接口**：oauth2/token、sign/compute、shortPlay/list、shortPlay/info、shortPlay/playUrl、material/list、order/list、order/adSummary
  - 当前只用 3 个：`/open/oauth2/token`、`/open/order/list`、`/open/order/adSummary`
  - ⚠️ v1.2.0 只更新了鉴权部分，业务入出参沿用 v1.0.0——**v1.0.0 未拿到，字段级契约缺失**（待确认 1）；scope 表末尾有空行，不排除存在未列出接口
- 分页行为：`/open/order/list` 上游**无 hasMore** 字段；以"整页返回"判定可能截断（请求 pageSize=1000）→ 服务端拉取需**窗口化 + 时间窗二分补全**（照搬 HTML 逻辑落到服务端）
- ⚠️ **adSummary 单次查询区间 ≤1 天**（2026-10-12 真实回填实测：多天区间返回信封错误「查询时间范围不能超过1天」；参考 HTML 整区间单请求的做法在多天视图下已不可用）→ 必须**逐日拉取**（当日 00:00:00–23:59:59）
- `createTime` 疑似 UTC 且有数十分钟同步延迟（B5）——存储层存原值，展示层定时区

## 前开发自建后端（api.tfctechnology.com）——重写对象，禁止运行时依赖

- 代码已遗失。`/auth/login` 与 `/data/partner/order/report` 由我方重写；契约兼容规格见 research/01 §4.2（`{code,msg,data}` 信封、`hasMore` 标志、字段改名 `orderAmount → usdOrderAmount`、100 行截断改真分页）
- **在线文档**：`/docs`（FastAPI Swagger，规格 `/openapi.json`）——共 8 接口，比 HTML 用的多 4 个（`/auth/verify`、`theater/list`、`theater/info`、`short-link/create`）；架构=网关→partner-adapter+独立认证服务；订单 schema 含 HTML 未读的 `linkId`（归因链接）与 `orderStatus`(2=支付,3=退款)。详见 research/01 §8
- 分页实测确认是坏的（page1=page2 完全相同），响应有 `lastId` 游标可作为重写真分页的线索；theater/list 返回 502
- 其内部管道：换票 → 调上游 order/list → **黑盒过滤（B1）** → 字段改名 → 100 行截断
- 唯一例外：**Phase 0 数据记录器**可临时调用它留存分类标签真值（老后端随时可能下线，每多跑一天多一天真值；调研期是否允许查询 = 待确认 4）
- 老后端账号 REDACTED-USER/REDACTED-PASSWORD（值已抹除） 已随 HTML 泄露，按已失效处理；上游密钥轮换待办（待确认 6）
- ✅ **2026-10-12 18:00 复测：上游凭据恢复可用**（换票成功，research/01 §8.4 的 11:05 失效事件已过去——当时疑与我方清理泄露凭据撞期）。真实数据联调可用。仍建议择期正式轮换（凭据毕竟泄露过），但**不阻塞任何开发与验证**。
- 换票响应的 scope 清单比飞书文档多出 3 个：`order:adDetail`、`user:newSummary`、`monitorLink:create`——证实存在未文档化接口。
  - **`order:adDetail` 已探明（2026-10-15）**：`POST /open/order/adDetail`，入参与 adSummary 同形态；返回 `{date, linkId, ad_revenue_dollars}` = **按推广链接细分的每日广告收益**，各行加总 = adSummary 同日值。同样有 ≤1 天区间限制、同样只剩近约 3 天历史。当前仅 1 条链接故无增量；未来多链接投放时再考虑入同步（`user:newSummary` / `monitorLink:create` 仍待探）。

## 下游接口（我们提供给供应商的）

- 原则已定（REQ-20261014-01）：只返回 `tag = included` 的订单、**只暴露必要字段**（不返回 tag/send_flag 等内部字段）；已计入订单状态随上游同步更新。**本期不实现**，待单独需求（供应商实体/API key/多供应商分配 = B4 待确认）
- `/api/v1/supplier/**`、API key 鉴权、按供应商隔离、FastAPI OpenAPI（`/docs`）作为对外文档

## 2026-10-14 实测更新（order/list 字段与 adSummary 状态）

- **order/list 实际返回 11 个字段**（此前文档只记 9 个）：新增 `linkId`（归因链接）与 `orderStatus`（2=支付、3=退款——此前只见于老后端 schema）。单日实测 318/318 笔 `orderAmount` 全部有值（BHD/KZT 等小币种也有）
- **adSummary 当日整体故障**：全部日期/参数格式返回信封错误「系统异常」（traceId 每次不同），同凭据 order/list 正常；库里广告数据最新到 10-13 说明故障为近期发生。降级路径（partial + 横幅 + lookback 自愈）已覆盖，恢复后自动补数
- ⚠ **2026-10-14 17:55 复测（独立导出脚本逐日探测 75 天）**：故障已恢复，但**上游只保留最近约 2 天广告数据**——10-13/10-14 有值，更早 73 天一律空 list。历史广告数据仅存于本地 ad_revenue_daily。含义：① 现行 30 分钟 + lookback 3 的同步节奏安全（每天在其可取窗口内被抓到）；② **同步停摆 >2 天 = 该期间广告数据永久丢失**（上游不补历史）；③ 库内 ad_revenue_daily 成为唯一历史口径，需当作重要资产对待。纯接口导出脚本：`tools/fetch_ad_summary_to_xlsx.py`

## 2026-10-14 下午追加实测（独立导出脚本全量拉取时发现，修正上文「分页行为」结论）

- **order/list 现已返回 `hasMore`**：`data` 含 `{list, page, pageSize, hasMore, lastId, timeZero}`，`timeZero="+00:00"` 证实 createTime 为 UTC。上文「上游无 hasMore」已过时（上游近期明显升级过接口）。
- **order/list 同样限单次区间 ≤ 1 天**：多天区间返回 code=400「查询时间范围不能超过1天」（此前只知 adSummary 有此限制）→ 订单也必须逐日拉取。
- **pageSize 必须在 [100, 1000]**：小于 100 返回 code=400「pageSize 需在 [100, 1000] 区间」。
- **pageSize=100 时翻页是坏的**：不同 page 返回完全相同的数据（与老后端同病症）；pageSize=1000 时单日一页全量返回（hasMore=False）。当前日量 200–500 单/天，1000 上限充足；若未来单日超 1000 行需重评拉取策略。
- **数据起点 2026-08-05**：此前全空。全量拉取 2026-08-01～10-14 共 22,825 单，无重复、无截断。
- 独立导出脚本：`tools/fetch_orders_to_xlsx.py`（读 backend/.env 凭据，逐日全量导出 xlsx，含字段语义说明页；Charles/ 下另有使用副本）。
