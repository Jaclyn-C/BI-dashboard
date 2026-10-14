"""CSV 导出测试（REQ AC-X1–X4；HTML csvCell/ordersToCsv 逐条对齐）。

覆盖：防公式注入、BOM/CRLF/无行尾 CRLF、en/zh 冻结表头、B1 三空列、
babel 国名本地化、状态冻结词、两档同名文件名、scope=view/all 行为。
"""

import csv
import io
from datetime import date
from decimal import Decimal

import pytest

from app.services.csv_export import (
    CSV_HEADERS,
    UNKNOWN_COUNTRY_LABEL,
    country_display,
    csv_cell,
    csv_filename,
)

API = "/api/v1/dashboard/orders.csv"
RANGE = {"from": "2026-10-01", "to": "2026-10-02"}


@pytest.fixture
def auth(db_session):
    from app.models import User
    from app.services import token_service

    user = User(email="csv@example.com", nickname="csv", password_hash="x")
    db_session.add(user)
    db_session.commit()
    token, _ = token_service.create_access_token(user.id, user.credential_version)
    return {"Authorization": f"Bearer {token}"}


def add_order(
    db,
    order_id: str,
    stamp: str,
    currency: str,
    amount_minor: str,
    *,
    language: str | None = "es-MX",
    usd_minor: str | None = "100",
    refund_time: str | None = None,
    theater_id: str = "TH",
    promotion_code: str | None = None,
    order_class: str | None = None,
) -> None:
    from app.models import Order

    db.add(
        Order(
            order_id=order_id,
            create_time=stamp,
            create_date=date.fromisoformat(stamp[:10]),
            theater_id=theater_id,
            chapter_id="CH",
            language=language,
            currency_type=currency,
            amount_minor=Decimal(amount_minor),
            usd_order_amount_minor=None if usd_minor is None else Decimal(usd_minor),
            refund_time=refund_time,
            is_returned=refund_time is not None,
            promotion_code=promotion_code,
            order_class=order_class,
        )
    )


def seed_csv_orders(db) -> None:
    add_order(db, "A", "2026-10-01 10:00:00", "MXN", "5000",
              usd_minor="270", promotion_code="=SUM(A1)", order_class="included")
    add_order(db, "B", "2026-10-01 11:00:00", "EUR", "1000",
              usd_minor="1100", language="fr-FR", theater_id="a,b",
              order_class="excluded")  # 逗号探针
    add_order(db, "C", "2026-10-02 09:00:00", "BHD", "700",
              usd_minor=None, language=None, order_class="excluded")  # 缺 usd + 未知国家
    add_order(db, "D", "2026-10-02 10:00:00", "USD", "900",
              usd_minor="900", language="en-US", refund_time="2026-10-03 09:00:00",
              order_class="included")
    db.commit()


# ---------- csv_cell（HTML csvCell 逐条移植） ----------


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, ""),
        ("", ""),
        ("plain", "plain"),
        ("=cmd()", "'=cmd()"),
        ("+1", "'+1"),
        ("-1", "'-1"),
        ("@x", "'@x"),
        ("\ttab", "'\ttab"),
        ("\rcr", '"\'\rcr"'),  # 注入前缀 + 含 \r → 引号包裹叠加
        ("a,b", '"a,b"'),
        ('a"b', '"a""b"'),
        ("a\nb", '"a\nb"'),
        ("a\rb", '"a\rb"'),
        ("'=already", "'=already"),  # 已带引号前缀的值原样直通
        (123, "123"),
    ],
)
def test_csv_cell_rules(value, expected):
    assert csv_cell(value) == expected


def test_country_display_localization():
    assert country_display("MX", "en") == "Mexico"
    assert country_display("MX", "zh") == "墨西哥"
    assert country_display("US", "zh") == "美国"
    assert country_display("__unknown", "en") == UNKNOWN_COUNTRY_LABEL["en"] == "Unknown"
    assert country_display("__unknown", "zh") == "未知"
    assert country_display("pt", "en") == "pt"  # 非区域 key → 原样回退


def test_frozen_headers_match_html():
    assert CSV_HEADERS["en"] == [
        "orderId", "createTime", "theaterId", "chapterId", "country", "language",
        "currency", "amount", "estUsd", "class", "revShare", "earningsUsd",
        "status", "promotionCode",
    ]
    assert CSV_HEADERS["zh"] == [
        "订单编号", "创建时间", "短剧ID", "章节ID", "国家/地区", "语种",
        "币种", "金额", "预估美元", "类别", "分成比例", "分成收入(美元)",
        "状态", "推广码",
    ]


def test_csv_filename_shared_between_scopes():
    assert csv_filename(date(2026, 10, 1), date(2026, 10, 2)) == (
        "orders_all_2026-10-01_to_2026-10-02.csv"
    )


# ---------- 端到端（经由 /dashboard/orders.csv） ----------


def test_orders_csv_en(client, auth, db_session):
    seed_csv_orders(db_session)
    resp = client.get(f"{API}", params=RANGE, headers=auth)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert resp.headers["content-disposition"] == (
        'attachment; filename="orders_all_2026-10-01_to_2026-10-02.csv"'
    )
    raw = resp.content
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM 首块（AC-X2）
    text = raw.decode("utf-8")
    assert not text.endswith("\r\n")  # 行连接 CRLF、无行尾 CRLF
    lines = text.split("\r\n")
    assert len(lines) == 5  # 表头 + 4 行
    assert lines[0] == "\ufeff" + ",".join(CSV_HEADERS["en"])
    assert '"a,b"' in lines[3]  # B 行（date desc 序）：含逗号值被引号包裹（原始字节层面）
    parsed = list(csv.reader(io.StringIO(text)))
    rows = {row[0]: row for row in parsed[1:]}
    assert all(len(row) == 14 for row in parsed)
    # class 列填冻结词；revShare/earningsUsd 仍空（REQ-20261014-01）
    assert rows["A"][9] == "Included" and rows["B"][9] == "Excluded"
    for cols in rows.values():
        assert cols[10:12] == ["", ""]
    # 金额两位小数；estUsd = usd 主单位、缺失空（AC-X2）
    assert rows["A"][7] == "50.00" and rows["A"][8] == "2.70"
    assert rows["C"][8] == ""  # 缺 usd
    # 状态冻结词
    assert rows["D"][12] == "Returned" and rows["A"][12] == "Completed"
    # 国名 babel 本地化 / 未知
    assert rows["A"][4] == "Mexico" and rows["C"][4] == "Unknown"
    # 注入防护：promotion 前置 '；theater 含逗号经 csv 解析后还原原值
    assert rows["A"][13] == "'=SUM(A1)"
    assert rows["B"][2] == "a,b"


def test_orders_csv_zh_words_and_headers(client, auth, db_session):
    seed_csv_orders(db_session)
    resp = client.get(f"{API}", params={**RANGE, "lang": "zh"}, headers=auth)
    lines = resp.content.decode("utf-8").split("\r\n")
    assert lines[0] == "\ufeff" + ",".join(CSV_HEADERS["zh"])
    rows = {row[0]: row for row in list(csv.reader(io.StringIO("\r\n".join(lines))))[1:]}
    assert rows["D"][12] == "已退款" and rows["A"][12] == "已完成"
    assert rows["A"][4] == "墨西哥" and rows["C"][4] == "未知"


def test_scope_view_applies_filters_and_sort(client, auth, db_session):
    seed_csv_orders(db_session)
    resp = client.get(
        f"{API}",
        params={**RANGE, "scope": "view", "currency": "MXN", "sort": "amount", "dir": "asc"},
        headers=auth,
    )
    lines = resp.content.decode("utf-8").split("\r\n")
    assert [line.split(",")[0] for line in lines[1:]] == ["A"]  # 仅 MXN


def test_class_filter_scopes_view_csv(client, auth, db_session):
    """class 参数收窄行集（REQ-20261014-01 §六）；class 列输出对应冻结词。"""
    seed_csv_orders(db_session)
    resp = client.get(
        f"{API}", params={**RANGE, "scope": "view", "class": "included"}, headers=auth
    )
    parsed = list(csv.reader(io.StringIO(resp.content.decode("utf-8"))))
    rows = {row[0]: row for row in parsed[1:]}  # 首行 = BOM + 表头
    assert set(rows) == {"A", "D"}  # A/D = included；B/C = excluded
    assert all(rows[o][9] == "Included" for o in ("A", "D"))


def test_scope_all_keeps_dataset_class_filter(client, auth, db_session):
    """scope=all 保留数据集 class 外层范围（REQ §3.4），只忽略表格级筛选。"""
    seed_csv_orders(db_session)
    resp = client.get(
        f"{API}", params={**RANGE, "scope": "all", "class": "excluded"}, headers=auth
    )
    lines = resp.content.decode("utf-8").split("\r\n")
    # 区间内剔除单 = C(10-02 09) + B(10-01 11)，create_time desc 固定序
    assert [line.split(",")[0] for line in lines[1:]] == ["C", "B"]


def test_scope_all_ignores_filters_fixed_order(client, auth, db_session):
    """scope=all：区间全量、忽略筛选、create_time desc 固定序（AC-X1）。"""
    seed_csv_orders(db_session)
    resp = client.get(
        f"{API}", params={**RANGE, "scope": "all", "currency": "MXN", "sort": "amount"},
        headers=auth,
    )
    lines = resp.content.decode("utf-8").split("\r\n")
    assert [line.split(",")[0] for line in lines[1:]] == ["D", "C", "B", "A"]
    # 两档同名（差异只在内容，AC-X2 / §4.6-4）
    assert resp.headers["content-disposition"].endswith('orders_all_2026-10-01_to_2026-10-02.csv"')


def test_orders_csv_empty_range_header_only(client, auth, db_session):
    resp = client.get(f"{API}", params=RANGE, headers=auth)
    assert resp.status_code == 200
    text = resp.content.decode("utf-8")
    assert text.count("\r\n") == 0  # 只剩表头一行
    assert text.startswith("\ufefforderId,")


def test_orders_csv_range_validation(client, auth, db_session):
    resp = client.get(
        f"{API}", params={"from": "2026-10-05", "to": "2026-10-01"}, headers=auth
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
