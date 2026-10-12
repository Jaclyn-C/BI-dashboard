# 海外CPS-对外API文档（OAuth）v1.2.0 —— 全文还原

> **来源**：飞书文档 `https://jcnchr0bwmpq.feishu.cn/docx/P8YodTptCocySAxnTL4cJH9FnAV`（2026-10-12 抓取还原，共 239 个内容块，含 8 张表格）
> **逐字完整存档**：`上游CPS开放API文档-v1.2.0-完整存档.md`（含全部 3 个完整 Java 示例类等一切内容，程序化校验 100% 覆盖）——引用原文细节时以存档为准
> **用法**：本文是上游接口契约的**一手参考**。第一部分为文档原文忠实还原；第二部分为我方从参考实现（`visualisation.html`）逆向实测到的补充事实，非文档内容，已明确标注。
> **完整性声明**：v1.2.0 原文声明"业务入参、出参沿用 v1.0.0"，而 **v1.0.0 未拿到**——因此业务接口的字段级契约仍然缺失（待确认问题 1）。本文第二部分实测内容可部分弥补，但不能替代 v1.0.0。

---

# 第一部分 · 文档原文还原

> 本文在原文档《海外CPS-对外api文档v1.0.0》的业务接口契约上，按 2026-09-04 现网实现更新鉴权：推荐 OAuth 2.0 Client Credentials（Bearer），MD5 签名继续兼容。业务入参、出参未改。
>
> 对象：playlet-cps 开放接口。路径相对网关前缀拼接，例如测试环境完整地址为「测试域名 + 接口路径」。

## 环境

| 环境 | 地址 |
|---|---|
| 测试 | https://adminapi.test.netshort.net/test-api/cps/ |
| 商用 | https://adminapi.netshort.com/prod-api/cps/ |

预发布域名原文未填写，本文不补造。

## 鉴权

### 双链规则

业务接口（`/open/**`，不含换票与算签工具）必须二选一鉴权。同时携带时，Bearer 优先，不再验 MD5（已废弃）。

| 方式 | 状态 | 说明 |
|---|---|---|
| OAuth Bearer | 推荐，新对接默认 | 先换 Access Token，再在业务请求头带 `Authorization: Bearer {token}`。按接口校验 scope。Token 为不透明串（`tok_` 前缀），默认有效期 3600 秒，过期后重新换票。 |
| MD5 签名 | 兼容存量合作方 | 请求头带 `systemCode`（或 `X-System-Code`）与 `sign`（或 `X-Sign`）。不校验 scope。验签规则见文末。 |

client_id / client_secret 由我方线下发放，本文不提供真实密钥。换票接口本身不验 Bearer，也不验 MD5。

### 获取 Access Token

OAuth 2.0 Client Credentials。凭证可用 HTTP Basic，或放在 form 字段。**建议使用 HTTP Basic 的方式！**

| 项 | 值 |
|---|---|
| 请求 URL | /open/oauth2/token |
| 请求方法 | POST |
| Content-Type | application/x-www-form-urlencoded |
| 鉴权 | 本接口不需要 Bearer / MD5 |

请求参数：

| 参数 | 类型 | 必须 | 描述 |
|---|---|---|---|
| grant_type | String | Y | 固定 client_credentials |
| scope | String | N | 空格分隔。不传则授予该客户端全部已授权 scope；传入值必须是已授权子集，具体 scope 参考下面「接口与 scope」 |
| client_id | String | 条件 | 未使用 Basic 时必填 |
| client_secret | String | 条件 | 未使用 Basic 时必填 |
| Authorization | Header | 条件 | `Basic base64(client_id:client_secret)`。与 form 凭证二选一，Basic 优先 |

成功仍走统一 R，data 字段如下：

| 字段 | 类型 | 描述 |
|---|---|---|
| accessToken | String | 不透明 Access Token，形如 `tok_` + 十六进制 |
| tokenType | String | 固定 Bearer |
| expiresIn | Long | 有效期秒数，默认 3600 |
| scope | String | 实际授予的 scope，空格分隔 |

#### 方式一：form 字段

client_id、client_secret 放在 application/x-www-form-urlencoded 请求体，不要带 Authorization。

```bash
curl -X POST "https://adminapi.test.netshort.net/test-api/cps/open/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=client_xxx&client_secret=your-secret&scope=shortplay:list shortplay:read"
```

#### 方式二：HTTP Basic

请求头 `Authorization: Basic base64(client_id:client_secret)`。form 仍需带 grant_type（以及可选 scope），不要再传 client_id / client_secret。同时存在时服务端优先用 Basic。

```bash
curl -X POST "https://adminapi.test.netshort.net/test-api/cps/open/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "client_xxx:your-secret" \
  -d "grant_type=client_credentials&scope=shortplay:list shortplay:read"
```

两种换票方式成功响应相同：

```json
{
  "code": 200,
  "msg": "Success",
  "data": {
    "accessToken": "tok_0123456789abcdef0123456789abcdef",
    "tokenType": "Bearer",
    "expiresIn": 3600,
    "scope": "shortplay:list shortplay:read"
  },
  "traceId": "xxx"
}
```

#### Java 调用业务接口（原文示例，保留了有契约信息的部分）

从 data.accessToken 取出 token 后，业务请求只带 `Authorization: Bearer`。原文以 GET 短剧列表、POST 素材列表为例（这两个示例**顺带透露了业务接口的入参形态**，故保留）：

```java
// GET /open/shortPlay/list —— 查询参数形态：page, pageSize, language, status
String url = BASE + "/open/shortPlay/list?page=1&pageSize=100&language=en_US&status=1";

// POST /open/material/list —— JSON 请求体形态：{"shortPlayId":"10001","language":"en_US"}
String json = "{\"shortPlayId\":\"10001\",\"language\":\"en_US\"}";
```

（原文另有三个完整 Java 11 HttpClient 示例类——form 换票、Basic 换票、业务调用——逐字收录于 `上游CPS开放API文档-v1.2.0-完整存档.md`。）

#### 刷新 Token

Client Credentials 不返回 refresh_token，也没有单独的刷新接口。获取、续期、过期后重取，都再次调用 `POST /open/oauth2/token`，参数与首次换票相同（grant_type、凭证、可选 scope）。每次成功会颁发新的 accessToken；旧 token 在原 expiresIn 到期前仍可用，不必主动作废。

| 场景 | 建议 |
|---|---|
| 正常续期 | 按响应里的 expiresIn（默认 3600 秒）本地计时，建议在到期前约 60 秒重新换票，避免业务请求踩过期。 |
| 业务返回 401 | msg 为「Token 无效或已过期」/「Token 已过期」时：丢掉本地缓存，再换一次票，用新 token 重试该业务请求一次。不要循环重试。 |
| 换票失败 | 按统一错误码处理。401/403（凭证错误、IP 不在白名单、客户端停用等）不要盲着重试；网络或 5xx 可有限退避。 |

不要每个业务请求都换票。缓存 accessToken，按 expiresIn 提前刷新即可。刷新请求本身不需要带旧的 Bearer Token；与首次获取相同，不要传旧 accessToken。

```bash
curl -X POST "https://adminapi.test.netshort.net/test-api/cps/open/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "client_xxx:your-secret" \
  -d "grant_type=client_credentials&scope=shortplay:list shortplay:read"
```

## 业务接口 Header

| Header | 必须 | 描述 |
|---|---|---|
| Authorization | OAuth 时 Y | `Bearer {accessToken}` |
| systemCode / X-System-Code | MD5 时 Y | 系统编码，用于查密钥，不参与 MD5 拼接 |
| sign / X-Sign | MD5 时 Y | 32 位十六进制 MD5 |

## 接口与 scope

仅 OAuth 校验 scope；MD5 链路跳过。换票 `POST /open/oauth2/token`、算签 `POST /open/sign/compute` 不校验 scope。Token 未包含对应 scope 时返回 `code=403`。

换票时 scope 为空格分隔；不传则授予该客户端已配置的全部 scope。传入值必须是已授权子集。

### scope 覆盖的接口

| scope | 对应接口 |
|---|---|
| shortplay:list | GET /open/shortPlay/list（获取短剧列表） |
| shortplay:read | GET /open/shortPlay/info（获取短剧详情）<br>GET /open/shortPlay/playUrl（获取播放地址） |
| material:list | POST /open/material/list（获取短剧投放素材列表） |
| order:list | POST /open/order/list（获取付费订单列表） |
| order:adSummary | POST /open/order/adSummary（广告收益每日汇总） |

> 原文表格末尾另有三行空行，疑似预留待补或已移除接口，含义不明（见调研报告待确认问题 1）。
>
> 原文提到"MD5 验签规则见文末"，但 v1.2.0 正文实际未包含该附录（沿用 v1.0.0，未拿到）。

---

# 第二部分 · 我方实测补充（非文档内容）

> 以下事实来自对参考实现 `docs/reference/visualisation.html` 的逆向（行号指该文件），以及 2026-10-12 的真实数据抓取。**可信度高但属实测行为，非官方契约**——如与上游后续提供的 v1.0.0 文档冲突，以官方文档为准。

## 统一响应信封与错误行为

- 信封：`{code, msg, data, traceId}`；`code ≠ 200` 即业务错误（HTML:867-869、940-942）。
- **HTTP 200 + body `code=401` 表示 token 失效**：上游可能在 HTTP 层返回 401，也可能在 200 的信封里用 code=401 表达同一件事（HTML:934-939 对两种情况都做了处理）。客户端需同时检查两层。

## POST /open/order/list（获取付费订单列表）

- 请求体（实测形态）：`{"startDate": "YYYY-MM-DD HH:mm:ss", "endDate": "…", "page": 1, "pageSize": N}`（HTML:951-953、969-972）
- 响应：`data.list` 为订单数组；**无 hasMore 字段**——返回行数等于请求 pageSize 时应视为"可能截断"（HTML:967、975）。
- 实测请求 pageSize=1000 可被接受；整页返回即触发调用方的时间窗二分补全策略（HTML:968-983，最大深度 6，最小窗口 120 秒）。
- 订单字段（实测，直连上游返回的原始字段名）：`orderId, createTime, theaterId, chapterId, language, currencyType, amount, orderAmount, refundTime, promotionCode`。
  - `amount` = 原币金额（最小单位，如美分为单位的 USD）；`orderAmount` = **上游已折算好的美元金额**（最小单位）——前开发后端将其改名为 `usdOrderAmount`（HTML:745-754）。
  - `refundTime` 非空 = 已退款；`language` 形如 `en_US`，是"流量来源国家"的推断依据（HTML:730-739）。
  - `promotionCode` = 渠道推广码。
- `createTime` 疑似 **UTC 时区**，且存在数十分钟的同步延迟——"今天"的数据永远不全，完整数据需次日获取（调研报告 §5.5）。

## POST /open/order/adSummary（广告收益每日汇总）

- 请求体与 order/list 同形态：`{startDate, endDate, page, pageSize}`（HTML:1022-1024）
- ⚠️ **2026-10-12 18:30 真实实测：单次查询区间不能超过 1 天**（多天区间返回信封错误「查询时间范围不能超过1天」）。参考 HTML 是整区间单请求（HTML:1057），该做法已失效——多天数据必须**逐日请求**（当日 00:00:00 至 23:59:59），按日聚合。此为文档未载、实测发现的上游约束。。
- 响应：`data.list` 为按日汇总行，实测字段：`date`（截取前 10 位为日期）、`ad_revenue_dollars`（**美元为单位**，非最小单位，HTML:1028-1032）。
- 口径："该渠道纯新用户"的每日广告收益（HTML 广告卡副标题）。

## 换票接口实测细节

- 响应取值路径：`payload.data.accessToken`（同时兼容 `access_token` 键名读取，HTML:900-901）；`expiresIn` / `expires_in` 双键名兼容（HTML:904）。
- 提前 60 秒刷新、401 单次重试（丢弃缓存 → 重换 → 重放一次业务请求，不循环）（HTML:880-908、926-939）。

## 上游已知但本文档未覆盖的行为缺口

- 订单/广告接口的完整字段表、排序规则、时间窗参数的边界语义（等 v1.0.0）；
- 上游限流策略未知（429 行为未观测）；
- scope 表末尾空行对应的接口是否存在未知。
