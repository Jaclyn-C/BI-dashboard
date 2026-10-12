# 业务知识（business）

> 来源：`docs/reference/visualisation.html`、`docs/research/01-调研发现与逆向分析.md`（2026-10-12 提炼）。**口径变更必须走 requirement-flow 并更新本文件。**

## 业务概述

业务链路：**上游 netshort（短剧 CPS 平台）→ 我方处理 → 下游供应商**。看板展示订单与广告收益，按分成规则计算收益；重构后新增「处理 → 下游供给」链路（规则待需求逐步给出）。

## 收益分成（核心口径）

- **included（已计入）**：进老后端过滤报表的订单，分成 **20%**
- **excluded（被剔除/缺失）**：仅上游全量可见、被过滤掉的订单，分成 **70%**
- 数据实证（14 天 6,016 笔）：被剔除订单仅占 19.8% 笔数，却贡献 **47.1% 分成收入**——看板存在的核心理由

## ⚠️ 订单分类规则是黑盒（B1，全项目最高风险项）

- HTML 的「双源对账」（上游全量 vs 老后端报表 diff）只是**检测手段**；分类的真正来源是老后端内部的**隐藏过滤规则**
- 统计检验结论（research/01 §5）：规则**确定性**（12 分钟复测 6,016 笔 0 翻转）、与全部可见字段无关（币种/国家/剧/金额/时段均无规则）、剔除率 ~80/20 稳定、**退款单被剔除率是正常单 2 倍** → 依据隐藏属性（推测为上游归属/结算口径或用户类型）
- **红线**：规则确认前不得猜测实现分类器、不得对外输出 20/70 分类金额；分类器做成可插拔接口（planning/02 A6），分成比例配置化（B2）
- 70% 档的合同口径 = 待确认 B2

## KPI 口径

| KPI | 口径 |
|---|---|
| Total revenue (USD) | 订单收益 + 广告收益 |
| Filtered order revenue | included 订单毛额 × 20% |
| Missing order revenue | excluded 订单毛额 × 70% |
| Ad revenue | 上游按日上报的渠道新用户广告收益（USD，`/open/order/adSummary`） |
| Gross revenue | 当前视图 completed 订单毛额 |
| Orders | 当前视图订单数（returned 单独计数展示） |
| Countries | 订单 language 推断的国家数 |

## 新旧美元口径对比（conv 卡片）

- **旧口径**：原生金额 × 静态汇率表（原表来自 export_orders.py，约 30 币种、2026-08 估值）；无汇率币种直接丢弃（与旧导出逻辑一致）
- **新口径**：上游自报美元额（上游 `orderAmount`，老后端改名 `usdOrderAmount`）；无自报值的 completed 订单被排除并提示
- 一致性阈值：两者相差 ≤ 0.5% 视为 agree

## 订单事实

- CSV 字段（13 列）：orderId, createTime, theaterId, chapterId, country, language, currency, amount, estUsd, class, revShare, earningsUsd, status, promotionCode
- 上游原始字段：orderId, createTime, theaterId, chapterId, language, currencyType, amount, orderAmount(USD), refundTime, promotionCode（country/estUsd/class/revShare/earningsUsd/status 是看板派生）
- status：Completed / Returned（returned 判定 = refundTime 非空）
- 国家由订单 language 推断（countryOf 映射），未知归 Unknown
- **createTime 疑似 UTC 且有数十分钟同步延迟（B5）**：存储层存上游原值，展示层定时区，不在存储层猜——「今天」的数据永远不全，完整数据次日才有

## 时间与筛选

- 预设：今天 / 近7天 / 近14天 / 近30天 / 自定义区间（**最长 92 天**）
- 订单表：25 行/页分页；可按 类型 / 币种 / 状态 筛选

## 其他既有行为

- CSV 导出两档：当前视图 / 全部订单（表头、UTF-8 BOM、防公式注入逻辑照搬参考 HTML）
- 双语 EN / 中文一键切换；深色模式跟随系统
- 看板自身登录：账号密码 → token（新系统账号体系见下）

## 内部账号体系（已确认 2026-10-12，REQ-20261012-01）

多账号自服务注册，账号 = 邮箱（全局唯一）；注册/找回密码用邮箱验证码（SMTP，未配置时降级打印日志）；注册成功自动登录；本期无角色区分；密码 8–64 位含字母数字；token 8 小时无 refresh；重置密码后所有旧 token 失效。

## 看板重构默认值（REQ-20261012-02 定稿，用户委托设计 2026-10-12）

- 同步：定时每 30 分钟、滚动回看 3 天（幂等 upsert）、首次部署回填 92 天；↻ 手动刷新 = 当前区间即时同步，失败回落已落库数据 + 降级标记
- B1 降级形态：三档数据集入口保留，20%/70% 两档 disabled 标「待规则确认」；分成金额不出（KPI 占位、图表毛额+标注、CSV 的 class/revShare/earningsUsd 三列留空）；每日卡仅币种堆叠、无类别堆叠
- 时间：createTime 原值（UTC）存储与展示、表头标注；日界取原值日期部分；预设「今天」按浏览器本地日；区间含最新可见日时状态行常驻「数据可能不全」注记
- 拉取参数照搬 HTML 并配置化：pageSize=1000 / 二分深度 6 / 最小窗 120s / 并发 4；adSummary 单请求不二分
- 静态汇率表 = 后端冻结常量（仅对比卡用）；20%/70% 配置化，B1 期间不接入任何输出路径
- 看板一律读库（不实时穿透上游）、聚合后端 Decimal、前端零金额运算
- 默认视图：近 7 天 / 语言 en / 深色跟随系统
- 完整决策与依据：`docs/requirements/REQ-20261012-02-dashboard.md` 第 6 节

## 待业务确认（对 planning/02 B 清单与 research/01 §7 的索引）

- **B1 分类规则**（最高优先级）、B2 70% 合同口径、B3 历史标签迁移、B4 供应商账号迁移、B5 createTime 时区——详见 `docs/planning/02-重构计划与待确认清单.md`
