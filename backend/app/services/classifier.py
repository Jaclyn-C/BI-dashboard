"""可插拔订单分类器（DESIGN-20261012-02 §4.4，REQ AC-CL1/CL2，A6）。

B1 红线：订单分类规则（20%/70% 归属）是黑盒（research/01 §5，依赖两边接口
都不暴露的隐藏属性）——本期交付空实现（classify 恒返回 None，不猜规则），
class 标签未知的订单在全链路以「待规则确认」形态呈现（UI 占位、CSV 空值）。

接入点唯一：同步管道规范化时调用（sync_service），写入 orders.order_class；
其余模块只读标签列，不关心来源（planning/02「唯一的缝」）。
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, Protocol, runtime_checkable

#: 分类标签（B1 恢复后出值；本期恒 None）
OrderClass = Literal["included", "excluded"]


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


@runtime_checkable
class OrderClassifier(Protocol):
    """分类器接口：给定规范化订单，返回 included / excluded，未知返回 None。"""

    def classify(self, order: NormalizedOrder) -> OrderClass | None: ...  # pragma: no cover


class UnknownClassifier:
    """本期唯一实现：恒返回 None（AC-CL1——不得猜测规则，宁缺毋错）。"""

    def classify(self, order: NormalizedOrder) -> OrderClass | None:
        return None
