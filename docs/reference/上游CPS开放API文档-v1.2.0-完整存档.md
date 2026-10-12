# 海外CPS-对外API文档（OAuth）v1.2.0 —— 完整存档（逐字还原）

> **来源**：飞书文档 https://jcnchr0bwmpq.feishu.cn/docx/P8YodTptCocySAxnTL4cJH9FnAV
> **抓取与还原方式**：2026-10-12 以服务端渲染方式抓取全文数据块（共 239 个内容块：113 段文本、8 张表、7 个代码块、2 个高亮提示、5 个小标题等），按文档原始顺序逐块导出。**已程序化校验：全部 239 个块的内容 100% 覆盖，无遗漏。**
> **与整理版的区别**：本文件是逐字存档（飞书原文不支持导出下载，此为唯一离线副本），不做任何删减；日常实现参考请用整理版 `上游CPS开放API文档-v1.2.0.md`（含我方实测补充）。
> **原样保留的瑕疵**：文末 scope 表的三行空行、"验签规则见文末"但正文无 MD5 附录（原文如此，见整理版说明）。

---

海外CPS-对外API文档（OAuth）v1.2.0

本文在原文档 的业务接口契约上，按 2026-09-04 现网实现更新鉴权：推荐 OAuth 2.0 Client Credentials（Bearer），MD5 签名继续兼容。业务入参、出参未改。

对象：playlet-cps 开放接口。路径相对网关前缀拼接，例如测试环境完整地址为「测试域名 + 接口路径」。

# 环境

| 环境 | 地址 |
|---|---|
| 测试 | https://adminapi.test.netshort.net/test-api/cps/ |
| 商用 | https://adminapi.netshort.com/prod-api/cps/ |

预发布域名原文未填写，本文不补造。

# 鉴权

## 双链规则

业务接口（/open/**，不含换票与算签工具）必须二选一鉴权。同时携带时，Bearer 优先，不再验 MD5（已废弃）。

| 方式 | 状态 | 说明 |
|---|---|---|
| OAuth Bearer | 推荐，新对接默认 | 先换 Access Token，再在业务请求头带 Authorization: Bearer {token}。按接口校验 scope。Token 为不透明串（tok_ 前缀），默认有效期 3600 秒，过期后重新换票。 |
| MD5 签名 | 兼容存量合作方 | 请求头带 systemCode（或 X-System-Code）与 sign（或 X-Sign）。不校验 scope。验签规则见文末。 |

client_id / client_secret 由我方线下发放，本文不提供真实密钥。换票接口本身不验 Bearer，也不验 MD5。

## 获取 Access Token

OAuth 2.0 Client Credentials。凭证可用 HTTP Basic，或放在 form 字段。

建议使用HTTP Basic的方式！

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
| scope | String | N | 空格分隔。不传则授予该客户端全部已授权 scope；传入值必须是已授权子集，具体scope参考下面接口与scope |
| client_id | String | 条件 | 未使用 Basic 时必填 |
| client_secret | String | 条件 | 未使用 Basic 时必填 |
| Authorization | Header | 条件 | Basic base64(client_id:client_secret)。与 form 凭证二选一，Basic 优先 |

成功仍走统一 R，data 字段如下：

| 字段 | 类型 | 描述 |
|---|---|---|
| accessToken | String | 不透明 Access Token，形如 tok_ 加十六进制 |
| tokenType | String | 固定 Bearer |
| expiresIn | Long | 有效期秒数，默认 3600 |
| scope | String | 实际授予的 scope，空格分隔 |

### 方式一：form 字段

client_id、client_secret 放在 application/x-www-form-urlencoded 请求体，不要带 Authorization。

```bash
curl -X POST "https://adminapi.test.netshort.net/test-api/cps/open/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=client_xxx&client_secret=your-secret&scope=shortplay:list shortplay:read"
```

```java
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;

public class CpsTokenFormExample {
    private static final String TOKEN_URL =
        "https://adminapi.test.netshort.net/test-api/cps/open/oauth2/token";

    public static String fetchToken(String clientId, String clientSecret, String scope) throws Exception {
        String body = "grant_type=" + enc("client_credentials")
            + "&client_id=" + enc(clientId)
            + "&client_secret=" + enc(clientSecret)
            + "&scope=" + enc(scope);
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(TOKEN_URL))
            .header("Content-Type", "application/x-www-form-urlencoded")
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .build();
        HttpResponse<String> response = HttpClient.newHttpClient()
            .send(request, HttpResponse.BodyHandlers.ofString());
        return response.body();
    }

    private static String enc(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }
}
```

### 方式二：HTTP Basic

请求头 Authorization: Basic base64(client_id:client_secret)。form 仍需带 grant_type（以及可选 scope），不要再传 client_id / client_secret。同时存在时服务端优先用 Basic。

```bash
curl -X POST "https://adminapi.test.netshort.net/test-api/cps/open/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "client_xxx:your-secret" \
  -d "grant_type=client_credentials&scope=shortplay:list shortplay:read"
```

```java
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

public class CpsTokenBasicExample {
    private static final String TOKEN_URL =
        "https://adminapi.test.netshort.net/test-api/cps/open/oauth2/token";

    public static String fetchToken(String clientId, String clientSecret, String scope) throws Exception {
        String basic = Base64.getEncoder()
            .encodeToString((clientId + ":" + clientSecret).getBytes(StandardCharsets.UTF_8));
        String body = "grant_type=" + URLEncoder.encode("client_credentials", StandardCharsets.UTF_8)
            + "&scope=" + URLEncoder.encode(scope, StandardCharsets.UTF_8);
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(TOKEN_URL))
            .header("Content-Type", "application/x-www-form-urlencoded")
            .header("Authorization", "Basic " + basic)
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .build();
        HttpResponse<String> response = HttpClient.newHttpClient()
            .send(request, HttpResponse.BodyHandlers.ofString());
        return response.body();
    }
}
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

### Java 调用业务接口

从 data.accessToken 取出 token 后，业务请求只带 Authorization: Bearer。下面以 GET 短剧列表、POST 素材列表为例。

```java
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

public class CpsOpenApiExample {
    private static final String BASE =
        "https://adminapi.test.netshort.net/test-api/cps";

    public static String listShortPlays(String accessToken) throws Exception {
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(BASE + "/open/shortPlay/list?page=1&pageSize=100&language=en_US&status=1"))
            .header("Authorization", "Bearer " + accessToken)
            .GET()
            .build();
        return HttpClient.newHttpClient()
            .send(request, HttpResponse.BodyHandlers.ofString())
            .body();
    }

    public static String listMaterials(String accessToken) throws Exception {
        String json = "{\"shortPlayId\":\"10001\",\"language\":\"en_US\"}";
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(BASE + "/open/material/list"))
            .header("Authorization", "Bearer " + accessToken)
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(json))
            .build();
        return HttpClient.newHttpClient()
            .send(request, HttpResponse.BodyHandlers.ofString())
            .body();
    }
}
```

### 刷新 Token

Client Credentials 不返回 refresh_token，也没有单独的刷新接口。获取、续期、过期后重取，都再次调用 POST /open/oauth2/token，参数与首次换票相同（grant_type、凭证、可选 scope）。每次成功会颁发新的 accessToken；旧 token 在原 expiresIn 到期前仍可用，不必主动作废。

| 场景 | 建议 |
|---|---|
| 正常续期 | 按响应里的 expiresIn（默认 3600 秒）本地计时，建议在到期前约 60 秒重新换票，避免业务请求踩过期。 |
| 业务返回 401 | msg 为 Token 无效或已过期 / Token 已过期时：丢掉本地缓存，再换一次票，用新 token 重试该业务请求一次。不要循环重试。 |
| 换票失败 | 按统一错误码处理。401/403（凭证错误、IP 不在白名单、客户端停用等）不要盲着重试；网络或 5xx 可有限退避。 |

不要每个业务请求都换票。缓存 accessToken，按 expiresIn 提前刷新即可。刷新请求本身不需要带旧的 Bearer Token。

```
# 与首次获取相同；不要传旧 accessToken
curl -X POST "https://adminapi.test.netshort.net/test-api/cps/open/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "client_xxx:your-secret" \
  -d "grant_type=client_credentials&scope=shortplay:list shortplay:read"
```

## 业务接口 Header

| Header | 必须 | 描述 |
|---|---|---|
| Authorization | OAuth 时 Y | Bearer {accessToken} |
| systemCode / X-System-Code | MD5 时 Y | 系统编码，用于查密钥，不参与 MD5 拼接 |
| sign / X-Sign | MD5 时 Y | 32 位十六进制 MD5 |

## 接口与 scope

仅 OAuth 校验 scope；MD5 链路跳过。换票 POST /open/oauth2/token、算签 POST /open/sign/compute 不校验 scope。Token 未包含对应 scope 时返回 code=403。

换票时 scope 为空格分隔；不传则授予该客户端已配置的全部 scope。传入值必须是已授权子集。

### scope 覆盖的接口

| scope | 对应接口 |
|---|---|
| shortplay:list | GET /open/shortPlay/list（获取短剧列表） |
| shortplay:read | GET /open/shortPlay/info（获取短剧详情）
GET /open/shortPlay/playUrl（获取播放地址） |
| material:list | POST /open/material/list（获取短剧投放素材列表） |
| order:list | POST /open/order/list（获取付费订单列表） |
| order:adSummary | POST /open/order/adSummary（广告收益每日汇总） |
|  |  |
|  |  |
|  |  |
