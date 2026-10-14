"""哈希分类器与分成数学单测（REQ-20261014-01）。

- 黄金向量（salt=unit-test-salt，测试内用 hashlib 独立复算，防实现漂移）；
- 确定性 / 盐值敏感 / 仅依赖 order_id；
- 万级合成订单 included 占比 ≈ 80%（确定性哈希，宽界无抖动）；
- share_service 新口径数学（70%/50%，精确 Decimal）；
- 空 salt 响亮失败（宁可同步失败，不落 NULL tag）。
"""

import hashlib
from datetime import date
from decimal import Decimal

import pytest

from app.config import Settings
from app.services.classifier import (
    HashClassifier,
    NormalizedOrder,
    build_default_classifier,
    classify_order_no,
    hash_value,
)
from app.services.share_service import (
    hidden_saving,
    my_upstream_share,
    net_actual,
    net_expected,
    supplier_paid_actual,
    supplier_payable_theoretical,
    total_net_actual,
)

SALT = "unit-test-salt"
KEEP = Decimal("0.8")

#: 黄金向量（digest 前 8 位十六进制与期望类别；独立于实现手工算出）
GOLDEN = [
    ("O1", "1edac7a3", "included"),
    ("O2", "919fd50f", "included"),
    ("X0", "e6f33e82", "excluded"),
    ("X2", "d7dc4eca", "excluded"),
]


def make_order(**overrides) -> NormalizedOrder:
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


# ---------- 分类器（REQ-20261014-01） ----------


def test_hash_value_matches_independent_recompute():
    """value 与 hashlib 独立复算一致（int(hex8)/2^32，全程精确 Decimal）。"""
    for order_no, prefix, _ in GOLDEN:
        digest = hashlib.sha256(f"{SALT}:{order_no}".encode()).hexdigest()
        assert digest[:8] == prefix  # 向量本身防漂移
        assert hash_value(SALT, order_no) == Decimal(int(digest[:8], 16)) / Decimal(1 << 32)


def test_classify_golden_vectors():
    for order_no, _, expected in GOLDEN:
        assert classify_order_no(SALT, order_no, KEEP) == expected


def test_classify_deterministic_and_salt_sensitive():
    assert classify_order_no(SALT, "O1", KEEP) == classify_order_no(SALT, "O1", KEEP)
    # 换盐判定翻转（s0 → excluded，s1 → included；判定依赖私密盐值）
    assert classify_order_no("s0", "O1", KEEP) == "excluded"
    assert classify_order_no("s1", "O1", KEEP) == "included"


def test_classify_only_depends_on_order_id():
    classifier = HashClassifier(salt=SALT, keep_ratio=KEEP)
    first = classifier.classify(make_order())
    same_id = classifier.classify(
        make_order(currency_type="USD", amount_minor=Decimal("1"), is_returned=True)
    )
    assert first == same_id == "included"  # O1 向量


def test_classify_keep_ratio_boundaries():
    """keep_ratio=1 全计入；足够小的阈值把 O1 挤出（0.1205 → excluded）。"""
    assert classify_order_no(SALT, "O1", Decimal("1")) == "included"
    assert classify_order_no(SALT, "O1", Decimal("0.1")) == "excluded"


def test_synthetic_distribution_near_80_percent():
    included = sum(
        1
        for i in range(10000)
        if classify_order_no(SALT, f"ORD{i}", KEEP) == "included"
    )
    assert 0.78 <= included / 10000 <= 0.82


def test_build_default_classifier_empty_salt_raises():
    with pytest.raises(ValueError, match="ORDER_FILTER_SALT"):
        build_default_classifier(Settings(order_filter_salt=""))
    built = build_default_classifier(Settings(order_filter_salt=" s "))
    assert built.salt == "s" and built.keep_ratio == Decimal("0.8")


# ---------- 分成数学（REQ-20261014-01 新口径） ----------


def test_share_math_exact_decimal():
    total = Decimal("100000")  # $1000.00 minor
    included_total = Decimal("80000")  # $800.00 minor
    share = my_upstream_share(total)
    payable = supplier_payable_theoretical(total)
    paid = supplier_paid_actual(included_total)
    assert share == Decimal("70000.00")
    assert payable == Decimal("50000.00")
    assert paid == Decimal("40000.00")
    assert hidden_saving(payable, paid) == Decimal("10000.00")
    assert net_expected(share, payable) == Decimal("20000.00")  # 全部 × 20%
    assert net_actual(share, paid) == Decimal("30000.00")


def test_share_math_uneven_split():
    """真实形态：Σ全部与 Σ已计入不等（剔除单不付供应商）。"""
    total = Decimal("3687")
    included_total = Decimal("2700")
    assert my_upstream_share(total) == Decimal("2580.90")
    assert supplier_payable_theoretical(total) == Decimal("1843.50")
    assert supplier_paid_actual(included_total) == Decimal("1350.00")
    assert hidden_saving(Decimal("1843.50"), Decimal("1350.00")) == Decimal("493.50")
    assert net_actual(Decimal("2580.90"), Decimal("1350.00")) == Decimal("1230.90")
    assert total_net_actual(Decimal("1230.90"), Decimal("17644")) == Decimal("18874.90")
