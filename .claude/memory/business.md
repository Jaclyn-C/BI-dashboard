# 业务知识（business）

> 来源：`docs/reference/visualisation.html`（2026-10-12 提炼）。**口径变更必须走 requirement-flow 并更新本文件。**

## 业务概述

合作伙伴收益看板：展示从上游获取的订单与广告收益数据，按分成规则计算合作伙伴收益。重构后新增「处理 → 下游供应商供给」链路（规则待需求逐步给出）。

## 收益分成（核心口径）

- **included**（上游过滤接口返回的订单）：分成 **20%**
- **excluded**（仅上游全量接口可见、被过滤掉的"缺失订单"）：分成 **70%**
- class 判定：订单出现在上游全量接口但不在过滤接口结果中 = excluded

## 数据集（三个视角）

1. **Filtered orders（20%）**：仅过滤接口订单
2. **Missing orders（70%）**：全量 − 过滤（缺失订单）
3. **All orders**：全量，各按自己的分成比例计算

## KPI 口径

| KPI | 口径 |
|---|---|
| Total revenue (USD) | 订单收益 + 广告收益 |
| Filtered order revenue | included 订单毛额 × 20% |
| Missing order revenue | excluded 订单毛额 × 70% |
| Ad revenue | 上游按日上报的新用户广告收益（USD） |
| Gross revenue | 当前视图 completed 订单毛额 |
| Orders | 当前视图订单数（returned 单独计数展示） |
| Countries | 订单 language 推断的国家数 |

## 新旧美元口径对比（conv 卡片）

- **旧口径**：原生金额 × 静态汇率表（原表来自 export_orders.py）；无汇率币种被排除（与旧导出逻辑一致）
- **新口径**：上游上报的 `usdOrderAmount`；无上报值的 completed 订单被排除并提示
- 一致性阈值：两者相差 ≤ 0.5% 视为 agree

## 订单事实

- CSV 字段（13 列）：orderId, createTime, theaterId, chapterId, country, language, currency, amount, estUsd, class, revShare, earningsUsd, status, promotionCode
- status：Completed / Returned（returned 判定 = refundTime 非空）
- 国家由订单 language 推断（countryOf 映射），未知归 Unknown

## 时间与筛选

- 预设：今天 / 近7天 / 近14天 / 近30天 / 自定义区间（**最长 92 天**）
- 订单表：25 行/页分页；可按 类型 / 币种 / 状态 筛选

## 其他既有行为

- CSV 导出两档：当前视图 / 全部订单
- 双语 EN / 中文一键切换；深色模式跟随系统
- 看板自身登录：用户名/密码 → token（对标 `/auth/login`）

## 待业务确认（需求逐步到达时澄清）

- 「处理 → 下游供给」具体规则：哪些订单给哪个供应商、金额是否调整、更新频率
- 静态汇率表的新来源（原表来自 export_orders.py）
- 内部账号体系：单账号还是多账号/角色
