# DESIGN-20261014-01 订单哈希打标与新分成口径 — 技术方案

> 对应 REQ：REQ-20261014-01 ｜ 日期：2026-10-14 ｜ 状态：已实施

## 1. 架构落点

分类器仍是「唯一的缝」（planning/02）：接入点仅同步管道规范化一处；迁移复用同一纯函数；聚合/接口/前端只读 tag 列。无数据库 schema 变更（`orders.order_class` + CHECK 在 0002 已就位），仅数据迁移。

## 2. 关键实现

### 2.1 分类器（app/services/classifier.py）
- `hash_value(salt, order_no)`：`Decimal(int(sha256(f"{salt}:{order_no}").hexdigest()[:8], 16)) / Decimal(2**32)`——全程精确 Decimal，禁 float；`classify_order_no` 比较 `value < keep_ratio`（0.8 在 /2³² 网格上不可精确命中，无等值歧义）。
- `HashClassifier` 实现既有 `OrderClassifier` Protocol；`build_default_classifier(settings)` 空 salt 抛 `ValueError`。

### 2.2 tag 永不改变（app/services/sync_service.py）
- `_ORDER_UPDATE_COLUMNS` 移除 `order_class`：upsert `on_conflict_do_update` 的 set_ 不含该列 → 重同步（lookback 重拉/手动全区间/回填）永不覆盖；新行走 INSERT values 照常写入。
- `execute_run`：默认分类器解析失败 → run=failed、零拉取零写入；规范化后 None 守卫（分类器回归防御）。
- 写入路径审计：全仓库写 orders 的只有 `upsert_orders`；退款状态流转不触碰 tag。

### 2.3 回填迁移（alembic/versions/0003_order_tag_backfill.py）
- salt 从 `get_settings()` 读取（与运行时同源；alembic env.py 本就用 Settings 连库）；迁移文件零盐字面量；空盐 RuntimeError 中止（事务回滚无半写）。
- 只更新 `order_class IS NULL` 行（SQL 侧双条件），1000/批 executemany；后置 NULL=0 检查；downgrade 全置 NULL（仅开发用，会连带清掉迁移后同步写入的 tag——docstring 已注明）。

### 2.4 聚合与契约（aggregation.py / schemas/dashboard.py）
- `build_summary(db, from, to, order_class="all")`：非 all 时行集先按 tag 过滤，旧口径每日/对比/国家随之收窄（复刻行为不变）。
- 主循环前置新口径累加（含退款、缺 usd 不计金额）：`total_usd / included_usd / excluded_usd / refunded_usd / included_count / excluded_count / no_usd_order_count`。
- 分成数学全部走 share_service（70%/50% 配置化）；卡片适用性按「公式输入是否全部在数据集内」置 None。
- `KpisOut` 重构如 REQ §4；`Degraded` 移除（已核实前端无消费方）；金额卡字段 `str|None`。

### 2.5 接口与 CSV
- summary/orders/orders.csv 新增 `class` 参数（`Query(alias="class")`，Literal all/included/excluded）。
- CSV class 列冻结词表（与 STATUS_WORDS 同模式）；revShare/earningsUsd 死列留空。

### 2.6 前端
- `DashboardPage` 持有 `dataset` 状态；`effectiveClass = 表格类别筛选 ≠ all ? 表格值 : dataset`，透传 orders/CSV；summary 直传 dataset。切换数据集重置页码。
- `KpiSection`：主值 null 的卡不渲染（数据集隐藏逻辑由后端 null 驱动，前端零口径判断）；`HelpDot`（灰色「?」文字字形）hover + `:focus-within` 出 tip，CSS-only 无依赖。
- DatasetBar 三档启用（复用 `.seg` 既有样式与 data-ds 激活态）；OrdersCard 类别筛选启用、剔除行复用 `.row-excluded` 斜纹。
- mock fixtures 为「模拟后端」：伪哈希打标（hash01 < 0.8）+ 同一适用性规则 + CSV class 填值。

## 3. 测试策略

- test_classifier_share：黄金向量（独立 hashlib 复算 + digest 前缀钉死）、确定性/盐敏感、万级分布 [0.78, 0.82]、分成精确 Decimal、空盐抛错。
- test_sync_service：make_settings 注入盐；**tag 不可变测试**（换相反分类器重 upsert，tag 不变）；空盐 run=failed 零拉取零写入。
- test_aggregation：黄金夹具 O1–O7 指定 tag，新口径逐卡断言（退款计入、缺 usd 排除）；旧口径每日/国家原样保留为回归护栏；三档数据集用例（值 + null 适用性 + 范围收窄）。
- test_dashboard_api / test_csv_export：summary?class=、orders?class=、CSV class 列词表。
- test_redlines：B1 import 隔离断言移除（REQ 依据）；新增「真实盐值不得出现在源码/迁移/测试/模板」检查。

## 4. 风险与运维事实

| 风险 | 缓解 |
|---|---|
| 盐值丢失/误改 → 新订单分类漂移且不可回滚 | .env 永久保存并离线备份；.env.example 警示注释；不提供改 tag 工具 |
| 迁移与运行时用不同盐 | 同一 get_settings() 来源；迁移零字面量 |
| NULL tag 静默落库 | 空盐响亮失败 + None 守卫 + 迁移后置检查 + test_redlines 盐值检查 |
| 新旧口径混淆（新卡含退款 vs 旧卡剔退款） | 两套累加器并存、各自测试钉住、每卡 tip 写明口径 |
| 上游 adSummary 故障（2026-10-14 实测「系统异常」） | 与本期无关；AC-S9 降级路径已覆盖，等上游恢复自动自愈 |
