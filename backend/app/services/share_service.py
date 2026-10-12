"""分成计算能力（DESIGN-20261012-02 §4.4，REQ AC-AG5 / D13）。

⚠️ B1 红线：本模块实现「配置化分成比例」能力并配套单测，但 **不得被聚合 /
API / CSV 任何输出路径 import**（DESIGN B-T4 验收含 grep 断言；AC-D3 分成
金额零输出）。B1 恢复（规则确认）后再接线。

比例从 Settings 读取（SHARE_INCLUDED / SHARE_EXCLUDED，D13/B2）。
"""

from decimal import Decimal

from app.config import get_settings
from app.services.classifier import NormalizedOrder


def share_ratio(order_class: str) -> Decimal:
    """按订单类别取分成比例（included=20% / excluded=70%，配置化）。"""
    settings = get_settings()
    if order_class == "included":
        return settings.share_included
    if order_class == "excluded":
        return settings.share_excluded
    raise ValueError(f"unknown order class: {order_class!r}")


def share_amount(usd_minor: Decimal, order_class: str) -> Decimal:
    """分成金额 = 上游美元毛额（最小单位）× 分成比例。

    输入应为已完成订单的上游自报美元金额；结果保持最小单位精度
    （展示层再走 money_str 的两位小数量化）。
    """
    return usd_minor * share_ratio(order_class)


def share_amount_for(order: NormalizedOrder) -> Decimal | None:
    """便捷形态：订单缺上游美元（None）或类别未知时返回 None（B1 恒 None）。"""
    if order.usd_order_amount_minor is None or order.order_class is None:
        return None
    return share_amount(order.usd_order_amount_minor, order.order_class)
