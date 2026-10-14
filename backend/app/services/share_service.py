"""分成计算（REQ-20261014-01 新口径，全部 Decimal、比例从 Settings 读取）。

口径（计算基数 = 上游自报美元 usd_order_amount_minor）：
- 你的上游分成 = Σ 全部订单 × 70%（upstream_share_ratio）
- 供应商应付（理论）= Σ 全部订单 × 50%（supplier_share_ratio，假设不隐藏）
- 供应商实付（实际）= Σ 已计入订单 × 50%
- 差值 = 应付 − 实付（被剔除订单对应的金额）
- 应得净利润 = 分成 − 应付（理论）
- 实际净利润 = 分成 − 实付

B1 说明：旧 20%/70% 双档口径及其输出隔离红线随本 REQ 解除（业务重定义
规则为哈希过滤，见 classifier.py 与 docs/requirements/REQ-20261014-01）。
"""

from decimal import Decimal

from app.config import get_settings


def my_upstream_share(usd_total_minor: Decimal) -> Decimal:
    """你的分成 = Σ 全部订单原金额（最小单位）× 70%。"""
    return usd_total_minor * get_settings().upstream_share_ratio


def supplier_payable_theoretical(usd_total_minor: Decimal) -> Decimal:
    """供应商应付（理论）= Σ 全部订单原金额 × 50%（假设不隐藏任何订单）。"""
    return usd_total_minor * get_settings().supplier_share_ratio


def supplier_paid_actual(included_usd_total_minor: Decimal) -> Decimal:
    """供应商实付（实际）= Σ 已计入订单原金额 × 50%。"""
    return included_usd_total_minor * get_settings().supplier_share_ratio


def hidden_saving(
    payable_theoretical_minor: Decimal, paid_actual_minor: Decimal
) -> Decimal:
    """差值 = 应付（理论）− 实付（实际），即被剔除订单对应的金额。"""
    return payable_theoretical_minor - paid_actual_minor


def net_expected(
    my_share_minor: Decimal, payable_theoretical_minor: Decimal
) -> Decimal:
    """应得净利润 = 你的分成 − 供应商应付（理论）= 全部 × 20%。"""
    return my_share_minor - payable_theoretical_minor


def net_actual(my_share_minor: Decimal, paid_actual_minor: Decimal) -> Decimal:
    """实际净利润 = 你的分成 − 供应商实付。"""
    return my_share_minor - paid_actual_minor
