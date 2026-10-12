"""旧口径静态汇率表单测（REQ D12 / AC-AG3）。

27 键逐值对齐 HTML:764-768（冻结常量）：改任何一键/值都必须先走 REQ 修订。
"""

from decimal import Decimal

import pytest

from app.services.fx_legacy import LEGACY_USD_RATES, legacy_usd_rate

#: HTML:764-768 逐值冻结的期望表（单测再抄一份做交叉校验，防止实现被顺手改）
EXPECTED = {
    "AED": "0.272", "AUD": "0.65", "BRL": "0.185", "CAD": "0.73", "CHF": "1.24",
    "CLP": "0.00105", "CZK": "0.048", "EUR": "1.17", "GBP": "1.35", "HKD": "0.128",
    "IDR": "0.000061", "INR": "0.0114", "JPY": "0.0068", "KRW": "0.00072",
    "MXN": "0.054", "MYR": "0.24", "NGN": "0.00065", "PHP": "0.0175", "QAR": "0.275",
    "SAR": "0.267", "SGD": "0.78", "THB": "0.031", "TRY": "0.024", "TWD": "0.033",
    "USD": "1", "VND": "0.000038", "ZAR": "0.056",
}


def test_exactly_27_keys():
    assert len(LEGACY_USD_RATES) == 27
    assert set(LEGACY_USD_RATES) == set(EXPECTED)


@pytest.mark.parametrize("currency", sorted(EXPECTED))
def test_rate_values_frozen(currency: str):
    assert LEGACY_USD_RATES[currency] == Decimal(EXPECTED[currency])


def test_legacy_usd_rate_lookup():
    assert legacy_usd_rate("MXN") == Decimal("0.054")
    assert legacy_usd_rate("mxn") == Decimal("0.054")  # 大小写不敏感
    assert legacy_usd_rate(None) is None
    assert legacy_usd_rate("") is None
    assert legacy_usd_rate("BHD") is None  # 无汇率 = 不计入旧合计
