"""聚合引擎（DESIGN-20261012-02 §4，REQ AC-AG1–AG5、AC-C1–C8、AC-K*；A7）。

Python 内存聚合（S4 决策）：一次载入区间订单行 → Decimal 聚合出 summary
全部口径，与 HTML derive()/convCompareData()/countries map 逐条对照可审计。
B1 语义替换：分成 → 毛额（gross = Σ usd_order_amount_minor，AC-D3 零分成输出）。

折叠派生全部后端预计算（§4.1）：每日图表序列 = 币种按区间毛额（usd 口径）
降序前 6 + __other；对比环图 = 前 7 + __other（RQ-3）；国家条 = 前 9 + __other
（usd/orders/byCurrency 求和合并）。前端零金额求和（AC-U6）。

⚠️ 本模块禁止 import share_service（B1 红线，B-T4/B-T9 grep 断言）。
"""

import re
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.models import AdRevenueDaily, Order
from app.schemas.dashboard import (
    AdEntry,
    ConvOut,
    ConvRow,
    ConvSlice,
    CountriesOut,
    CountryRow,
    CurrencyAmount,
    DailyEntry,
    DailyOut,
    Degraded,
    KpisOut,
    RangeOut,
    SeriesAmount,
    SummaryMeta,
    SummaryResponse,
)
from app.services import sync_service
from app.services.fx_legacy import legacy_usd_rate
from app.services.money import money_str, quantize_1

#: 未知国家哨兵（订单行 country_key 与 summary 国家条目同一枚值，m12）
UNKNOWN_COUNTRY_KEY = "__unknown"

#: 折叠序列键（图例「其他」）
OTHER_KEY = "__other"

#: 每日图表币种序列上限：前 6 + __other = 7（HTML MAX_CURRENCY_SERIES，AC-E3）
MAX_CURRENCY_SERIES = 7

#: 对比环图切片上限：前 7 + __other = 8（RQ-3 决议 = HTML:1632-1635，AC-C2）
MAX_CONV_SLICES = 7

#: 国家条形上限：前 9 + __other = 10（HTML MAXROWS，AC-N1）
MAX_COUNTRY_ROWS = 10

#: Δ 行高亮阈值：|Δ| ≥ $1（100 minor）且 ≥ 行基数 1%（AC-C3）
_DELTA_FLAG_MINOR = Decimal(100)
_DELTA_FLAG_RATIO = Decimal("0.01")

#: 新旧合计一致阈值 0.5%（AC-C5）
_AGREE_RATIO = Decimal("0.005")

_REGION_RE = re.compile(r"[_-]([A-Za-z]{2})$")


def country_key(language: str | None) -> str:
    """language → 稳定国家 key（AC-AG4/N2）。

    区域子标签（`_-XX$`）取 XX 大写；无子标签 = 原语种串；空 = __unknown。
    展示名由前端 Intl / CSV 侧 babel 按 key 本地化（聚合 key 不随语言变）。
    """
    lang = str(language or "").strip()
    if not lang:
        return UNKNOWN_COUNTRY_KEY
    match = _REGION_RE.search(lang)
    if not match:
        return lang
    return match.group(1).upper()


def iter_range_days(date_from: date, date_to: date) -> list[date]:
    """区间内逐日列表（含两端）。"""
    return [date_from + timedelta(days=i) for i in range((date_to - date_from).days + 1)]


def _signed_pct(value: Decimal) -> str:
    """百分比 1 位小数带符号（正加 +，负自带 −，0 不加）。"""
    pct = quantize_1(value)
    return f"+{pct}" if pct > 0 else str(pct)


def _fold_series(
    by_currency: dict[str, Decimal], main: list[str], folded: set[str]
) -> list[SeriesAmount]:
    """单日序列：主序列非零项 + __other（尾部币种求和，非零才出）。"""
    series = [
        SeriesAmount(key=cur, amount=money_str(by_currency[cur]))
        for cur in main
        if by_currency.get(cur, Decimal("0")) > 0
    ]
    if folded:
        other = sum(
            (by_currency[cur] for cur in folded if cur in by_currency), Decimal("0")
        )
        if other > 0:
            series.append(SeriesAmount(key=OTHER_KEY, amount=money_str(other)))
    return series


def build_summary(db, date_from: date, date_to: date) -> SummaryResponse:
    """聚合区间全口径 summary（DESIGN §5.2 契约）。"""
    rows = db.execute(
        select(
            Order.create_date,
            Order.currency_type,
            Order.language,
            Order.amount_minor,
            Order.usd_order_amount_minor,
            Order.is_returned,
        )
        .where(Order.create_date >= date_from, Order.create_date <= date_to)
    ).all()

    zero = Decimal("0")
    days = iter_range_days(date_from, date_to)
    day_keys = [day.isoformat() for day in days]

    # ---- 主循环（usd 口径，对标 HTML derive 主 pass；退款单不进任何金额聚合 AC-AG2）----
    gross_usd_minor = zero
    usd_daily: dict[str, dict] = {}
    currency_totals_usd: dict[str, Decimal] = {}
    countries: dict[str, dict] = {}
    conv_rows: dict[str, dict] = {}
    no_usd_currencies: set[str] = set()
    no_usd_order_count = 0
    orders_completed = 0
    orders_returned = 0
    orders_total = 0

    for (
        create_date,
        currency_type,
        language,
        amount_minor,
        usd_minor,
        is_returned,
    ) in rows:
        orders_total += 1
        if is_returned:
            orders_returned += 1
            continue
        orders_completed += 1
        currency = str(currency_type or "?").upper()

        # ---- 对比卡（全部已完成订单，含缺 usd / 缺汇率，AC-C7）----
        conv = conv_rows.get(currency)
        if conv is None:
            conv = {
                "orders": 0,
                "native": zero,
                "legacy": zero,
                "server": zero,
                "has_rate": legacy_usd_rate(currency) is not None,
            }
            conv_rows[currency] = conv
        conv["orders"] += 1
        conv["native"] += amount_minor if amount_minor is not None else zero
        rate = legacy_usd_rate(currency)
        if rate is not None:
            conv["legacy"] += amount_minor * rate
        if usd_minor is not None:
            conv["server"] += usd_minor
        else:
            no_usd_order_count += 1
            no_usd_currencies.add(currency)

        # ---- usd 口径（缺 usd 的订单不计入，AC-AG3）----
        if usd_minor is None:
            continue
        gross_usd_minor += usd_minor
        currency_totals_usd[currency] = currency_totals_usd.get(currency, zero) + usd_minor

        day_key = create_date.isoformat()
        entry = usd_daily.get(day_key)
        if entry is None:
            entry = {"total": zero, "count": 0, "by_cur": {}}
            usd_daily[day_key] = entry
        entry["total"] += usd_minor
        entry["count"] += 1
        entry["by_cur"][currency] = entry["by_cur"].get(currency, zero) + usd_minor

        ckey = country_key(language)
        country = countries.get(ckey)
        if country is None:
            country = {"usd": zero, "count": 0, "by_cur": {}}
            countries[ckey] = country
        country["usd"] += usd_minor
        country["count"] += 1
        country["by_cur"][currency] = country["by_cur"].get(currency, zero) + amount_minor

    # ---- est 口径（原币 × 静态汇率；无汇率不计入，订单数独立计，AC-AG3）----
    est_daily: dict[str, dict] = {}
    for (
        create_date,
        currency_type,
        _language,
        amount_minor,
        _usd_minor,
        is_returned,
    ) in rows:
        if is_returned:
            continue
        currency = str(currency_type or "?").upper()
        rate = legacy_usd_rate(currency)
        if rate is None or amount_minor is None:
            continue
        est_usd = amount_minor * rate
        day_key = create_date.isoformat()
        entry = est_daily.get(day_key)
        if entry is None:
            entry = {"total": zero, "count": 0, "by_cur": {}}
            est_daily[day_key] = entry
        entry["total"] += est_usd
        entry["count"] += 1
        entry["by_cur"][currency] = entry["by_cur"].get(currency, zero) + est_usd

    # ---- 广告（区间内 ad_revenue_daily，AC-K4）----
    ad_rows = db.execute(
        select(AdRevenueDaily.date, AdRevenueDaily.amount_minor)
        .where(AdRevenueDaily.date >= date_from, AdRevenueDaily.date <= date_to)
        .order_by(AdRevenueDaily.date)
    ).all()
    ad_total_minor = sum((amount for _, amount in ad_rows), zero)
    ad_entries = [
        AdEntry(date=day.isoformat(), amount=money_str(amount)) for day, amount in ad_rows
    ]

    # ---- 每日双口径输出（含零值日）+ 序列折叠（前 6 + __other）----
    currency_rank = [
        currency
        for currency, _ in sorted(
            currency_totals_usd.items(), key=lambda item: item[1], reverse=True
        )
    ]
    if len(currency_rank) > MAX_CURRENCY_SERIES:
        main_currencies = currency_rank[: MAX_CURRENCY_SERIES - 1]
        folded_currencies = set(currency_rank[MAX_CURRENCY_SERIES - 1 :])
    else:
        main_currencies = currency_rank
        folded_currencies = set()

    def _daily_out(daily_map: dict[str, dict]) -> list[DailyEntry]:
        out = []
        for day_key in day_keys:
            entry = daily_map.get(day_key)
            if entry is None:
                out.append(
                    DailyEntry(
                        date=day_key, orders=0, total="0.00",
                        by_currency=[], series=[],
                    )
                )
                continue
            by_currency = [
                CurrencyAmount(currency=cur, amount=money_str(amount))
                for cur, amount in sorted(
                    entry["by_cur"].items(), key=lambda item: item[1], reverse=True
                )
            ]
            out.append(
                DailyEntry(
                    date=day_key,
                    orders=entry["count"],
                    total=money_str(entry["total"]),
                    by_currency=by_currency,
                    series=_fold_series(entry["by_cur"], main_currencies, folded_currencies),
                )
            )
        return out

    # ---- 对比卡（§4.1 规则；排序 max(server, legacy) 降序）----
    conv_list = sorted(
        conv_rows.items(), key=lambda item: max(item[1]["server"], item[1]["legacy"]), reverse=True
    )
    legacy_total_minor = zero
    server_total_minor = zero
    conv_out_rows: list[ConvRow] = []
    for currency, conv in conv_list:
        legacy_total_minor += conv["legacy"]
        server_total_minor += conv["server"]
        delta = conv["server"] - conv["legacy"]
        base = conv["server"] if conv["server"] != 0 else conv["legacy"]
        rate = legacy_usd_rate(currency)
        flagged = (
            abs(delta) >= _DELTA_FLAG_MINOR
            and base > 0
            and abs(delta) >= base * _DELTA_FLAG_RATIO
        )
        conv_out_rows.append(
            ConvRow(
                currency=currency,
                has_rate=conv["has_rate"],
                rate=str(rate) if rate is not None else None,
                orders=conv["orders"],
                native=money_str(conv["native"]),
                legacy_usd=money_str(conv["legacy"]),
                server_usd=money_str(conv["server"]),
                delta=money_str(delta),
                delta_pct=_signed_pct(delta / base * 100) if base > 0 else None,
                flagged=flagged,
            )
        )
    delta_total_minor = server_total_minor - legacy_total_minor
    total_base = (
        server_total_minor if server_total_minor != 0 else legacy_total_minor
    )
    agree = total_base > 0 and abs(delta_total_minor) < total_base * _AGREE_RATIO
    no_rate_currencies = sorted(cur for cur, conv in conv_rows.items() if not conv["has_rate"])

    # 环图切片：前 7 + __other（双口径值都给，≤8 切片，RQ-3）
    conv_slices: list[ConvSlice] = [
        ConvSlice(
            key=cur,
            legacy_usd=money_str(conv["legacy"]),
            server_usd=money_str(conv["server"]),
        )
        for cur, conv in conv_list[:MAX_CONV_SLICES]
    ]
    conv_tail = conv_list[MAX_CONV_SLICES:]
    if conv_tail:
        conv_slices.append(
            ConvSlice(
                key=OTHER_KEY,
                legacy_usd=money_str(sum((conv["legacy"] for _, conv in conv_tail), zero)),
                server_usd=money_str(sum((conv["server"] for _, conv in conv_tail), zero)),
            )
        )
    conv_empty = not conv_out_rows or (legacy_total_minor <= 0 and server_total_minor <= 0)

    # ---- 国家（按毛额 USD 降序；bars 前 9 + __other 求和合并，HTML:1725-1729）----
    country_sorted = sorted(countries.items(), key=lambda item: item[1]["usd"], reverse=True)
    total_country_usd = sum((entry["usd"] for _, entry in country_sorted), zero)
    table_rows: list[CountryRow] = []
    for key, entry in country_sorted:
        share = (
            str(quantize_1(entry["usd"] / total_country_usd * 100))
            if total_country_usd > 0
            else None
        )
        table_rows.append(
            CountryRow(
                key=key,
                usd=money_str(entry["usd"]),
                orders=entry["count"],
                share=share,
                by_currency=[
                    CurrencyAmount(currency=cur, amount=money_str(amount))
                    for cur, amount in sorted(
                        entry["by_cur"].items(), key=lambda item: item[1], reverse=True
                    )
                ],
            )
        )
    bar_rows = table_rows[: MAX_COUNTRY_ROWS - 1]
    tail = country_sorted[MAX_COUNTRY_ROWS - 1 :]
    if tail:
        other_usd = sum((entry["usd"] for _, entry in tail), zero)
        other_orders = sum(entry["count"] for _, entry in tail)
        other_by_cur: dict[str, Decimal] = {}
        for _, entry in tail:
            for cur, amount in entry["by_cur"].items():
                other_by_cur[cur] = other_by_cur.get(cur, zero) + amount
        share = (
            str(quantize_1(other_usd / total_country_usd * 100))
            if total_country_usd > 0
            else None
        )
        bar_rows.append(
            CountryRow(
                key=OTHER_KEY,
                usd=money_str(other_usd),
                orders=other_orders,
                share=share,
                by_currency=[
                    CurrencyAmount(currency=cur, amount=money_str(amount))
                    for cur, amount in sorted(
                        other_by_cur.items(), key=lambda item: item[1], reverse=True
                    )
                ],
            )
        )

    # ---- meta（同步状态，§3.5 降级映射）----
    sync_status, latest_sync_at, latest_covered = sync_service.orders_sync_state(db)
    ad_available, ad_error = sync_service.latest_ad_state(db)

    return SummaryResponse(
        range=RangeOut(from_=date_from, to=date_to),
        meta=SummaryMeta(
            orders_total=orders_total,
            latest_orders_sync_at=latest_sync_at.isoformat() if latest_sync_at else None,
            sync_status=sync_status,
            latest_covered_date=latest_covered.isoformat() if latest_covered else None,
            incomplete_tail=latest_covered is None or date_to >= latest_covered,
            truncated_days=sync_service.truncated_days_in_range(db, date_from, date_to),
            ad_available=ad_available,
            ad_error=ad_error,
        ),
        degraded=Degraded(share_rules_pending=True),
        kpis=KpisOut(
            total_revenue=money_str(gross_usd_minor + ad_total_minor),
            orders_gross_usd=money_str(gross_usd_minor),
            ad_total=money_str(ad_total_minor),
            included_revenue=None,  # B1（AC-K2）
            excluded_revenue=None,  # B1（AC-K3）
            gross_usd=money_str(gross_usd_minor),
            orders_completed=orders_completed,
            orders_returned=orders_returned,
            countries=len(countries),
            top_country=table_rows[0].key if table_rows else None,
            ad_days_reported=len(ad_rows),
        ),
        daily=DailyOut(
            days=day_keys,
            currency_rank=currency_rank,
            est=_daily_out(est_daily),
            usd=_daily_out(usd_daily),
            ad=ad_entries,
        ),
        conv=ConvOut(
            empty=conv_empty,
            rows=conv_out_rows,
            slices=conv_slices,
            legacy_total=money_str(legacy_total_minor),
            server_total=money_str(server_total_minor),
            delta_total=money_str(delta_total_minor),
            delta_pct=_signed_pct(delta_total_minor / total_base * 100)
            if total_base > 0
            else None,
            agree=agree,
            no_rate_currencies=no_rate_currencies,
            no_usd_order_count=no_usd_order_count,
            no_usd_currencies=sorted(no_usd_currencies),
        ),
        countries=CountriesOut(table=table_rows, bars=bar_rows),
    )
