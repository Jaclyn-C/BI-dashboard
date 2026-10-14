"""聚合引擎测试（真实 PostgreSQL 测试库；REQ-20261012-02 AC-AG* + REQ-20261014-01 新口径）。

黄金夹具：7 笔订单（含 1 笔退款、1 笔缺上游美元、1 个无汇率币种 BHD，tag：
included=O1/O3/O6，excluded=O2/O4/O5/O7）+ 2 天广告收益。

两套口径分开钉住：
- 新口径 KPI（REQ-20261014-01）：基数=上游自报美元、**含退款单**、缺 usd 不计金额
  只计数；全部期望值手工 Decimal 推得（见各断言注释）；
- 旧口径每日/对比/国家卡：复刻 HTML 行为（退款剔除）原样保留为回归护栏。

数据集切换（class=included/excluded）：行集收窄 + 不适用卡片为 None。
"""

from datetime import date
from decimal import Decimal

from app.models import AdRevenueDaily, Order
from app.services.aggregation import build_summary


def add_order(
    db,
    order_id: str,
    day: str,
    stamp: str,
    currency: str,
    amount_minor: str,
    *,
    language: str | None,
    usd_minor: str | None = None,
    refund_time: str | None = None,
    order_class: str | None = None,
) -> None:
    db.add(
        Order(
            order_id=order_id,
            create_time=stamp,
            create_date=date.fromisoformat(day),
            theater_id="TH",
            chapter_id="CH",
            language=language,
            currency_type=currency,
            amount_minor=Decimal(amount_minor),
            usd_order_amount_minor=None if usd_minor is None else Decimal(usd_minor),
            refund_time=refund_time,
            is_returned=refund_time is not None,
            order_class=order_class,
        )
    )


def seed_golden(db) -> None:
    """黄金夹具（期望值推导见各断言注释）。

    tag 分布：included = O1(270) / O3(1500) / O6(453)；excluded = O2(1100) /
    O4(144) / O5(缺 usd) / O7(220，退款)。
    """
    add_order(db, "O1", "2026-10-01", "2026-10-01 10:00:00", "MXN", "5000",
              language="es-MX", usd_minor="270", order_class="included")
    add_order(db, "O2", "2026-10-01", "2026-10-01 11:00:00", "EUR", "1000",
              language="fr-FR", usd_minor="1100", order_class="excluded")
    add_order(db, "O3", "2026-10-01", "2026-10-01 12:00:00", "USD", "1500",
              language="en-US", usd_minor="1500", order_class="included")
    add_order(db, "O4", "2026-10-02", "2026-10-02 09:00:00", "KRW", "200000",
              language="ko-KR", usd_minor="144", order_class="excluded")
    add_order(db, "O5", "2026-10-02", "2026-10-02 10:00:00", "BHD", "700",
              language="ar-BH", order_class="excluded")  # 缺上游美元：金额不计、计数
    add_order(db, "O6", "2026-10-02", "2026-10-02 11:00:00", "MXN", "800",
              language="es-MX", usd_minor="453", order_class="included")
    add_order(db, "O7", "2026-10-01", "2026-10-01 13:00:00", "EUR", "200",
              language="fr-FR", usd_minor="220", refund_time="2026-10-03 09:00:00",
              order_class="excluded")
    db.add_all(
        [
            AdRevenueDaily(date=date(2026, 10, 1), amount_minor=Decimal("17144")),
            AdRevenueDaily(date=date(2026, 10, 2), amount_minor=Decimal("500")),
        ]
    )
    db.commit()


def test_golden_fixture_new_kpis(db_session):
    """新口径 KPI（REQ-20261014-01）：含退款、缺 usd 排除金额。"""
    seed_golden(db_session)
    k = build_summary(db_session, date(2026, 10, 1), date(2026, 10, 2)).kpis

    # 订单总数/完成/退款（含退款单、含缺 usd）
    assert (k.orders_total, k.orders_completed, k.orders_returned) == (7, 6, 1)
    # total = 270+1100+1500+144+453+220(退款O7) = 3687（O5 缺 usd 不计）
    assert k.total_usd == "36.87"
    assert k.no_usd_order_count == 1
    # 分成 = 3687 × 0.7 = 2580.9
    assert k.my_share_usd == "25.81"
    # 应付理论 = 3687 × 0.5 = 1843.5；实付 = 2223 × 0.5 = 1111.5
    assert k.supplier_payable_usd == "18.44"
    assert k.supplier_paid_usd == "11.12"
    # 差值 = 1843.5 − 1111.5 = 732
    assert k.hidden_saving_usd == "7.32"
    # 应得净利 = 2580.9 − 1843.5 = 737.4；实际净利 = 2580.9 − 1111.5 = 1469.4
    assert k.net_expected_usd == "7.37"
    assert k.net_actual_usd == "14.69"
    # 已退款总额 = 220（退款单照常参与全部统计）
    assert k.refunded_usd == "2.20"
    # 合并卡：included 3 笔 2223；excluded 4 笔 1464（O5 无 usd 只计数）
    assert (k.included.count, k.included.usd) == (3, "22.23")
    assert (k.excluded.count, k.excluded.usd) == (4, "14.64")
    # 广告沿用
    assert (k.ad_total, k.ad_days_reported) == ("176.44", 2)
    assert (k.countries, k.top_country) == (4, "US")


def test_golden_fixture_kpis_daily_legacy_caliber(db_session):
    """旧口径每日/对比/国家卡：退款剔除行为不变（回归护栏）。"""
    seed_golden(db_session)
    summary = build_summary(db_session, date(2026, 10, 1), date(2026, 10, 2))

    # 每日双口径（含退款排除 / est 只认静态汇率）
    assert summary.daily.days == ["2026-10-01", "2026-10-02"]
    assert summary.daily.currency_rank == ["USD", "EUR", "MXN", "KRW"]
    usd_d1, usd_d2 = summary.daily.usd
    assert (usd_d1.total, usd_d1.orders) == ("28.70", 3)
    assert [(c.currency, c.amount) for c in usd_d1.by_currency] == [
        ("USD", "15.00"), ("EUR", "11.00"), ("MXN", "2.70")
    ]
    assert (usd_d2.total, usd_d2.orders) == ("5.97", 2)
    assert [(c.currency, c.amount) for c in usd_d2.by_currency] == [
        ("MXN", "4.53"), ("KRW", "1.44")
    ]
    est_d1, est_d2 = summary.daily.est
    assert est_d1.total == "29.40"  # 2.70 + 11.70 + 15.00
    assert [(c.currency, c.amount) for c in est_d1.by_currency] == [
        ("USD", "15.00"), ("EUR", "11.70"), ("MXN", "2.70")
    ]
    assert est_d2.total == "1.87"  # 1.44 + 0.432（BHD 无汇率不计入）
    assert [(a.date, a.amount) for a in summary.daily.ad] == [
        ("2026-10-01", "171.44"), ("2026-10-02", "5.00")
    ]

    # 国家：缺 usd（BH）与退款单不进分布
    countries = summary.countries
    assert [row.key for row in countries.table] == ["US", "FR", "MX", "KR"]
    us, fr, mx, kr = countries.table
    assert (us.usd, us.orders, us.share) == ("15.00", 1, "43.3")
    assert (fr.usd, fr.share) == ("11.00", "31.7")
    assert (mx.usd, mx.orders, mx.share) == ("7.23", 2, "20.9")
    assert (kr.usd, kr.share) == ("1.44", "4.2")


def test_golden_fixture_conv_card(db_session):
    seed_golden(db_session)
    conv = build_summary(db_session, date(2026, 10, 1), date(2026, 10, 2)).conv

    assert conv.empty is False
    # 排序：max(server, legacy) 降序 → USD 1500 / EUR 1170 / MXN 723 / KRW 144 / BHD 0
    assert [row.currency for row in conv.rows] == ["USD", "EUR", "MXN", "KRW", "BHD"]
    usd, eur, mxn, krw, bhd = conv.rows
    assert (usd.legacy_usd, usd.server_usd, usd.delta, usd.delta_pct, usd.flagged) == (
        "15.00", "15.00", "0.00", "0.0", False
    )
    # EUR：1100 vs 1170 → -0.70（|Δ|=70 分 < $1 阈值 → 不标红，AC-C3）
    assert (eur.legacy_usd, eur.server_usd, eur.delta, eur.delta_pct, eur.flagged) == (
        "11.70", "11.00", "-0.70", "-6.4", False
    )
    # MXN：723 vs 313.2 → Δ=409.8 分（≥$1 且 ≥1%）→ 标红（AC-C3）
    assert (mxn.legacy_usd, mxn.server_usd, mxn.delta, mxn.delta_pct, mxn.flagged) == (
        "3.13", "7.23", "4.10", "+56.7", True
    )
    assert mxn.native == "58.00" and mxn.orders == 2 and mxn.rate == "0.054"
    assert (krw.legacy_usd, krw.server_usd) == ("1.44", "1.44")
    # BHD：无汇率 + 缺 usd → 全零行、无百分比（base=0）
    assert (bhd.has_rate, bhd.rate, bhd.legacy_usd, bhd.server_usd, bhd.delta_pct) == (
        False, None, "0.00", "0.00", None
    )
    # 合计：34.67 vs 31.27 → Δ 3.40（9.8%）> 0.5% → 不一致（AC-C5）
    assert (conv.legacy_total, conv.server_total, conv.delta_total, conv.delta_pct) == (
        "31.27", "34.67", "3.40", "+9.8"
    )
    assert conv.agree is False
    assert conv.no_rate_currencies == ["BHD"]
    assert conv.no_usd_order_count == 1  # O5（已完成口径）
    assert conv.no_usd_currencies == ["BHD"]
    # 环图切片：5 币 ≤ 7 → 全量、无 __other
    assert [s.key for s in conv.slices] == ["USD", "EUR", "MXN", "KRW", "BHD"]
    assert (conv.slices[2].legacy_usd, conv.slices[2].server_usd) == ("3.13", "7.23")


def test_dataset_included_scopes_rows_and_cards(db_session):
    """class=included：行集只剩已计入；应付理论/差值/应得净利/合并卡 → None。"""
    seed_golden(db_session)
    summary = build_summary(
        db_session, date(2026, 10, 1), date(2026, 10, 2), "included"
    )
    k = summary.kpis
    # 行集 = O1/O3/O6：total = 270+1500+453 = 2223
    assert (k.orders_total, k.orders_completed, k.orders_returned) == (3, 3, 0)
    assert k.total_usd == "22.23"
    assert k.my_share_usd == "15.56"  # 2223 × 0.7 = 1556.1
    assert k.supplier_paid_usd == "11.12"  # 2223 × 0.5 = 1111.5
    assert k.net_actual_usd == "4.45"  # 1556.1 − 1111.5 = 444.6
    assert k.refunded_usd == "0.00"
    assert k.no_usd_order_count == 0
    # 不适用卡片
    assert k.supplier_payable_usd is None
    assert k.hidden_saving_usd is None
    assert k.net_expected_usd is None
    assert k.included is None and k.excluded is None
    # 广告照常（渠道级，不随数据集收窄）
    assert k.ad_total == "176.44"
    # 旧口径卡随数据集收窄：每日只剩已计入的 3 笔
    assert summary.daily.usd[0].orders == 2  # O1 + O3
    assert summary.daily.usd[1].orders == 1  # O6
    assert summary.countries.table[0].key == "US"


def test_dataset_excluded_scopes_rows_and_cards(db_session):
    """class=excluded：供应商侧全部不适用（净利=分成，不重复展示）。"""
    seed_golden(db_session)
    summary = build_summary(
        db_session, date(2026, 10, 1), date(2026, 10, 2), "excluded"
    )
    k = summary.kpis
    # 行集 = O2/O4/O5/O7：total = 1100+144+220 = 1464（O5 缺 usd）
    assert (k.orders_total, k.orders_completed, k.orders_returned) == (4, 3, 1)
    assert k.total_usd == "14.64"
    assert k.my_share_usd == "10.25"  # 1464 × 0.7 = 1024.8
    assert k.refunded_usd == "2.20"  # O7
    assert k.no_usd_order_count == 1  # O5
    for none_card in (
        k.supplier_payable_usd,
        k.supplier_paid_usd,
        k.hidden_saving_usd,
        k.net_expected_usd,
        k.net_actual_usd,
        k.included,
        k.excluded,
    ):
        assert none_card is None
    # 每日只剩剔除单中的已完成：10-01 O2、10-02 O4
    assert summary.daily.usd[0].orders == 1
    assert summary.daily.usd[1].orders == 1


def test_golden_fixture_meta_and_zero_day_padding(db_session):
    seed_golden(db_session)
    summary = build_summary(db_session, date(2026, 9, 30), date(2026, 10, 1))
    # 区间内无 9-30 数据 → 零值日补齐（前端不必补零）
    assert summary.daily.days == ["2026-09-30", "2026-10-01"]
    empty_day = summary.daily.usd[0]
    assert (empty_day.orders, empty_day.total, empty_day.by_currency) == (0, "0.00", [])
    assert summary.meta.sync_status == "never"
    assert summary.meta.latest_orders_sync_at is None
    assert summary.meta.latest_covered_date is None
    assert summary.meta.incomplete_tail is True
    assert summary.meta.truncated_days == []
    assert summary.meta.ad_available is False


def test_empty_range_shape(db_session):
    summary = build_summary(db_session, date(2026, 10, 1), date(2026, 10, 1))
    k = summary.kpis
    assert k.total_usd == "0.00"
    assert k.my_share_usd == "0.00"
    assert k.supplier_payable_usd == "0.00"
    assert k.orders_completed == 0
    assert k.included is not None and k.included.count == 0 and k.included.usd == "0.00"
    assert summary.conv.empty is True
    assert summary.countries.table == []
    assert k.top_country is None


# ---------- 折叠派生（§4.1：全部后端预计算，前端零金额求和） ----------


def seed_many(db, count: int) -> None:
    """单日 count 个币种/国家，usd = (count-i)*100 minor 递减。"""
    letters = "ABCDEFGHIJK"
    for i in range(count):
        cur = f"{letters[i]}{letters[i]}{letters[i]}"
        add_order(
            db, f"M{i}", "2026-10-01", f"2026-10-01 {i:02d}:00:00", cur,
            str((count - i) * 100),  # 原币面额同额（native 排序同序）
            language=f"xx-{letters[i]}{letters[i]}",
            usd_minor=str((count - i) * 100),
            order_class="included" if i % 2 == 0 else "excluded",
        )
    db.commit()


def test_daily_series_folds_to_six_plus_other(db_session):
    seed_many(db_session, 9)
    daily = build_summary(db_session, date(2026, 10, 1), date(2026, 10, 1)).daily
    assert len(daily.currency_rank) == 9
    series = daily.usd[0].series
    # 前 6 主序列 + __other（尾部 3 币种后端求和 = 300+200+100 = 600 分）
    assert [s.key for s in series] == ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "__other"]
    assert series[-1].amount == "6.00"
    assert series[0].amount == "9.00"


def test_conv_slices_fold_to_seven_plus_other(db_session):
    seed_many(db_session, 9)
    conv = build_summary(db_session, date(2026, 10, 1), date(2026, 10, 1)).conv
    keys = [s.key for s in conv.slices]
    assert keys[:7] == ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG"]
    assert keys[7] == "__other"
    assert conv.slices[7].server_usd == "3.00"  # HHH 200 + III 100（尾 2 币求和）


def test_country_bars_fold_to_nine_plus_other(db_session):
    seed_many(db_session, 11)
    countries = build_summary(db_session, date(2026, 10, 1), date(2026, 10, 1)).countries
    assert len(countries.table) == 11  # 表格不折叠
    bar_keys = [b.key for b in countries.bars]
    assert bar_keys[:9] == ["AA", "BB", "CC", "DD", "EE", "FF", "GG", "HH", "II"]
    assert bar_keys[9] == "__other"
    other = countries.bars[9]
    assert (other.usd, other.orders) == ("3.00", 2)  # JJ 200 + KK 100；表 11 行只取前 9


def test_country_key_variants():
    from app.services.aggregation import UNKNOWN_COUNTRY_KEY, country_key

    assert country_key("es-MX") == "MX"
    assert country_key("en_US") == "US"  # 下划线子标签同样取区域
    assert country_key("zh-Hant-TW") == "TW"  # 只认末位两字母区域
    assert country_key("en-GB-x-lpicker") == "en-GB-x-lpicker"  # 末位非两字母 → 原串
    assert country_key("pt") == "pt"  # 无子标签 → 原语种串
    assert country_key("") == UNKNOWN_COUNTRY_KEY
    assert country_key(None) == UNKNOWN_COUNTRY_KEY
    assert country_key("  ") == UNKNOWN_COUNTRY_KEY
