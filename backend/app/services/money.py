"""金额工具（DESIGN-20261012-02 §2.5）。

- 库内一律存 minor units（分）为 ``Decimal``；
- API 层输出主单位两位小数字符串（``money_str``），/100 只发生在展示层（RQ-4）；
- 百分比一位小数（``quantize_1``），ROUND_HALF_UP 与 JS toFixed 对齐。
"""

from decimal import ROUND_HALF_UP, Decimal

_CENTS = Decimal("100")
_TWO = Decimal("0.01")
_ONE = Decimal("0.1")


def quantize_2(value: Decimal) -> Decimal:
    """量化两位小数（ROUND_HALF_UP）。"""
    return Decimal(value).quantize(_TWO, rounding=ROUND_HALF_UP)


def quantize_1(value: Decimal) -> Decimal:
    """量化一位小数（ROUND_HALF_UP，对标 JS toFixed(1)）。"""
    return Decimal(value).quantize(_ONE, rounding=ROUND_HALF_UP)


def minor_to_major(value: Decimal) -> Decimal:
    """minor units → 主单位（仅展示层调用，RQ-4）。"""
    return Decimal(value) / _CENTS


def money_str(value: Decimal) -> str:
    """minor units Decimal → 主单位两位小数字符串（API 输出统一出口）。"""
    return str(quantize_2(minor_to_major(value)))


def money_exact(value: Decimal) -> str:
    """minor units Decimal → 主单位**真值**字符串（不四舍五入，REQ-20261014-01）。

    用于分成类卡片：×70%/×50% 会产生「分」以下尾数，取整会破坏卡片间
    显示值可互算性（总净利 = 实际净利 + 广告 要求逐位对上）。输出去掉
    尾随零、保留至少两位小数（如 25.809 / 15549.1635 / 36.87 / 0.00）。
    """
    major = Decimal(value) / _CENTS
    text = format(major.normalize(), "f")
    if "." not in text:
        return f"{text}.00"
    head, _, tail = text.partition(".")
    if len(tail) < 2:
        return f"{head}.{tail.ljust(2, '0')}"
    return text
