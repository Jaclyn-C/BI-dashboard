"""分类器与分成能力单测（REQ AC-CL1/CL2、AC-AG5/D13）。

B1 红线验证点：UnknownClassifier 恒 None（不猜规则）；share_service 的
比例/金额数学正确（能力在位）；输出路径 import 隔离断言见 test_redlines。
"""

from decimal import Decimal

import pytest

from app.services.classifier import NormalizedOrder, UnknownClassifier
from app.services.share_service import share_amount, share_amount_for, share_ratio


def make_order(**overrides) -> NormalizedOrder:
    from datetime import date

    base = dict(
        order_id="O1",
        create_time="2026-10-01 10:00:00",
        create_date=date(2026, 10, 1),
        theater_id="T",
        chapter_id="C",
        language="es-MX",
        currency_type="MXN",
        amount_minor=Decimal("5000"),
        usd_order_amount_minor=Decimal("270"),
        refund_time=None,
        is_returned=False,
        promotion_code=None,
        order_class=None,
    )
    base.update(overrides)
    return NormalizedOrder(**base)


# ---------- 分类器（B1 空实现） ----------


def test_unknown_classifier_always_none():
    """AC-CL1：规则未确认，classify 恒 None——宁缺毋错。"""
    classifier = UnknownClassifier()
    assert classifier.classify(make_order()) is None
    assert classifier.classify(make_order(is_returned=True)) is None
    assert classifier.classify(make_order(currency_type="USD")) is None


def test_classifier_protocol_runtime_checkable():
    assert isinstance(UnknownClassifier(), object)


# ---------- 分成能力（B1 不接线，仅数学单测） ----------


def test_share_ratio_from_settings():
    assert share_ratio("included") == Decimal("0.20")
    assert share_ratio("excluded") == Decimal("0.70")
    with pytest.raises(ValueError, match="unknown order class"):
        share_ratio("mystery")


def test_share_amount_math():
    """金额 = 上游美元毛额 × 比例，保持最小单位精度。"""
    assert share_amount(Decimal("1000"), "included") == Decimal("200.0")
    assert share_amount(Decimal("1000"), "excluded") == Decimal("700.0")
    assert share_amount(Decimal("270"), "included") == Decimal("54.0")


def test_share_amount_for_requires_class_and_usd():
    """缺 usd 或类别未知 → None（B1 期间恒 None）。"""
    assert share_amount_for(make_order()) is None  # order_class None
    assert share_amount_for(make_order(order_class="included")) == Decimal("54.0")
    assert (
        share_amount_for(
            make_order(order_class="included", usd_order_amount_minor=None)
        )
        is None
    )
