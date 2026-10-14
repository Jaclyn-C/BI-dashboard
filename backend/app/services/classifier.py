"""订单分类器（DESIGN-20261012-02 §4.4；规则由 REQ-20261014-01 业务重定义）。

规则（需求《建议版本需求》§3，2026-10-14 用户确认）：
``sha256(f"{salt}:{order_no}")`` 前 8 位十六进制 → [0,1) 小数 value；
``value < keep_ratio(0.8)`` → included（已计入，下发供应商），否则 excluded（剔除）。

- 判定是 order_no 的纯确定性函数：同一订单号永远同一结果（需求 §3.5）；
- salt 是私密配置（.env），不入库、不入代码、不泄露给下游；
- 接入点唯一：同步管道规范化时调用（sync_service），写入 orders.order_class，
  其余模块只读标签列（planning/02「唯一的缝」）。
"""

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, Protocol, runtime_checkable

from app.config import Settings

#: 分类标签（语义 = 下游可见性：included=已计入/下发；excluded=剔除/不下发）
OrderClass = Literal["included", "excluded"]

#: 8 位十六进制的值域上限（0x1_0000_0000），除法保持 [0,1) 且全程 Decimal
_TWO_POW_32 = Decimal(1 << 32)


@dataclass
class NormalizedOrder:
    """上游订单行的规范化形态（DESIGN §3.3.1 规范化层输出，AC-U3）。

    字段映射：orderAmount → usd_order_amount_minor（上游自报美元·最小单位）、
    amount → amount_minor（原币·最小单位）、create_date = create_time[:10]、
    is_returned = refund_time 非空白。createTime 原值（零换算，AC-S8）。
    """

    order_id: str
    create_time: str
    create_date: date
    theater_id: str
    chapter_id: str
    language: str | None
    currency_type: str
    amount_minor: Decimal
    usd_order_amount_minor: Decimal | None
    refund_time: str | None
    is_returned: bool
    promotion_code: str | None
    order_class: OrderClass | None


def hash_value(salt: str, order_no: str) -> Decimal:
    """sha256(salt:order_no) 前 8 位十六进制 → [0,1) 的精确 Decimal。"""
    digest = hashlib.sha256(f"{salt}:{order_no}".encode()).hexdigest()
    return Decimal(int(digest[:8], 16)) / _TWO_POW_32


def classify_order_no(salt: str, order_no: str, keep_ratio: Decimal) -> OrderClass:
    """value < keep_ratio → included（已计入），否则 excluded（剔除）。"""
    return "included" if hash_value(salt, order_no) < keep_ratio else "excluded"


@runtime_checkable
class OrderClassifier(Protocol):
    """分类器接口：给定规范化订单，返回 included / excluded。"""

    def classify(self, order: NormalizedOrder) -> OrderClass: ...  # pragma: no cover


class HashClassifier:
    """规则实现（REQ-20261014-01）：salt + keep_ratio 的稳定哈希判定。"""

    def __init__(self, *, salt: str, keep_ratio: Decimal) -> None:
        self.salt = salt
        self.keep_ratio = keep_ratio

    def classify(self, order: NormalizedOrder) -> OrderClass:
        return classify_order_no(self.salt, order.order_id, self.keep_ratio)


def build_default_classifier(settings: Settings) -> HashClassifier:
    """按配置构建默认分类器；salt 未配置 → 响亮失败。

    tag 入库后永不改变（sync_service upsert 不更新该列），落 NULL 只能人工
    回填——所以宁可让本轮同步失败，也不静默落空标签。
    """
    salt = settings.order_filter_salt.strip()
    if not salt:
        raise ValueError(
            "ORDER_FILTER_SALT 未配置：拒绝同步打标（盐值一经使用不可更换，见 REQ-20261014-01）"
        )
    return HashClassifier(salt=salt, keep_ratio=settings.order_keep_ratio)
