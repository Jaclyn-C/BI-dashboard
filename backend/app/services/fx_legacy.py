"""旧口径静态汇率表（DESIGN-20261012-02 §4.5，REQ D12 / AC-AG3）。

HTML:764-768 的 27 个币种 **逐值冻结**（1 单位原币 → USD，2026-08 估值，
源自 export_orders.py 的 USD_RATES）。仅「新旧美元口径对比卡」使用；其余
一切金额用上游自报美元。无汇率 = 键缺失 → 不计入旧合计（与旧导出逻辑一致）。

口径变更（增删键或改值）必须走需求流程（REQ 修订）——本表是冻结常量。
"""

from decimal import Decimal

#: 冻结的旧口径汇率表（键数 = 27，单测逐值断言与 HTML 相等）
LEGACY_USD_RATES: dict[str, Decimal] = {
    "AED": Decimal("0.272"),
    "AUD": Decimal("0.65"),
    "BRL": Decimal("0.185"),
    "CAD": Decimal("0.73"),
    "CHF": Decimal("1.24"),
    "CLP": Decimal("0.00105"),
    "CZK": Decimal("0.048"),
    "EUR": Decimal("1.17"),
    "GBP": Decimal("1.35"),
    "HKD": Decimal("0.128"),
    "IDR": Decimal("0.000061"),
    "INR": Decimal("0.0114"),
    "JPY": Decimal("0.0068"),
    "KRW": Decimal("0.00072"),
    "MXN": Decimal("0.054"),
    "MYR": Decimal("0.24"),
    "NGN": Decimal("0.00065"),
    "PHP": Decimal("0.0175"),
    "QAR": Decimal("0.275"),
    "SAR": Decimal("0.267"),
    "SGD": Decimal("0.78"),
    "THB": Decimal("0.031"),
    "TRY": Decimal("0.024"),
    "TWD": Decimal("0.033"),
    "USD": Decimal("1"),
    "VND": Decimal("0.000038"),
    "ZAR": Decimal("0.056"),
}


def legacy_usd_rate(currency: str) -> Decimal | None:
    """取旧口径汇率；无该币种返回 None（不计入旧合计）。"""
    return LEGACY_USD_RATES.get(str(currency or "").upper())
