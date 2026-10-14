"""同步管道（DESIGN-20261012-02 §3.3，REQ AC-S3/S8/U3；A2）。

编排一次同步（trigger ∈ scheduled / manual / backfill）：
1. 建 sync_runs 行（running）；
2. orders 阶段：日窗并发拉取（ThreadPoolExecutor，HTTP 并行）→ 汇集后
   单会话串行 upsert（会话非线程安全；分批 500 行 on_conflict_do_update，
   以 orderId 去重，AC-S3 幂等）→ 规范化映射（AC-U3）→ 独立 commit；
3. ad 阶段：fetch_ad_summary → 按日 upsert ad_revenue_daily → 独立 commit
   （AC-S9：广告失败不回滚订单）；
4. 收尾更新 run 行（status/truncated_dates/counts/errors/finished_at）。

其他职责：手动插队（§3.3.2，全区间重拉 RQ-2、服务端钳制）、覆盖自愈
（§3.3.3：lookback ∪ 未覆盖期望域，首次部署自动等价 92 天回填 D3）、
单飞锁、进度态（CurrentRun）、孤儿 running 行清理（m9）。

单进程假设：内存锁与进度态依赖 compose 单 uvicorn worker（§8.1 风险表）。
"""

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select, update

from app.config import Settings, get_settings
from app.db import SessionLocal
from app.models import AdRevenueDaily, Order, SyncRun
from app.schemas.dashboard import MAX_RANGE_DAYS, SyncStatusResponse
from app.services.classifier import (
    NormalizedOrder,
    OrderClassifier,
    build_default_classifier,
)
from app.upstream.client import UpstreamClient, UpstreamError
from app.upstream.fetcher import fetch_ad_summary, fetch_day

logger = logging.getLogger("app.sync")

#: 单飞锁：scheduled 跳过本轮 / manual 返回 accepted=false（DESIGN §3.4）
_sync_lock = threading.Lock()

#: 进度态（HTTP 状态端点直读；持久态以 sync_runs 为准）
_state_lock = threading.Lock()
_current_run: "CurrentRun | None" = None

#: upsert 更新集（DESIGN §2.1：create_time/create_date/theater/chapter 视为不可变；
#: order_class 同样不可变——tag 入库算一次、永不改变，REQ-20261014-01 §3.5）
_ORDER_UPDATE_COLUMNS = (
    "amount_minor",
    "usd_order_amount_minor",
    "language",
    "currency_type",
    "refund_time",
    "is_returned",
    "promotion_code",
)

_UPSERT_BATCH_SIZE = 500


class CurrentRun:
    """进行中同步的进度快照（days 粒度，对齐 AC-S1 loadingDays）。"""

    def __init__(
        self,
        run_id: int,
        trigger: str,
        window_start: date,
        window_end: date,
        days_total: int,
    ) -> None:
        self.run_id = run_id
        self.trigger = trigger
        self.window_start = window_start
        self.window_end = window_end
        self.days_total = days_total
        self.days_done = 0
        self.phase = "orders"

    def snapshot(self) -> "CurrentRun":
        copy = CurrentRun(
            self.run_id, self.trigger, self.window_start, self.window_end, self.days_total
        )
        copy.days_done = self.days_done
        copy.phase = self.phase
        return copy


# ---------- 规范化（AC-U3） ----------


def _to_decimal(value: object) -> Decimal | None:
    """防御式 Decimal 解析（§8.1：字段契约缺失，坏值 → None + 由调用方记日志）。"""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def normalize_order(
    row: dict, classifier: OrderClassifier | None = None
) -> NormalizedOrder | None:
    """上游原始行 → NormalizedOrder；不可入库（缺主键/日期）返回 None 并记日志。

    映射：orderAmount→usd_order_amount_minor、amount→amount_minor（最小单位，
    原值精度无损）、create_date=create_time[:10]、is_returned=refund_time 非空白、
    order_class=classifier.classify(row)（哈希判定，REQ-20261014-01；tag 永有值）。
    """
    order_id = str(row.get("orderId") or "").strip()
    create_time = str(row.get("createTime") or "").strip()
    if not order_id or len(order_id) > 64 or not create_time or len(create_time) > 32:
        logger.warning("skip order with missing/oversized id or createTime: %r", order_id[:16])
        return None
    try:
        create_date = date.fromisoformat(create_time[:10])
    except ValueError:
        logger.warning("skip order with unparsable createTime: %r", create_time[:32])
        return None

    amount = _to_decimal(row.get("amount"))
    if amount is None:
        logger.warning("order %s has invalid amount %r, storing 0", order_id, row.get("amount"))
        amount = Decimal("0")
    usd = _to_decimal(row.get("orderAmount"))  # 缺失/坏值 → None（新口径排除+计数）

    refund_time = str(row.get("refundTime") or "").strip()[:32] or None
    language = str(row.get("language") or "").strip()[:16] or None
    normalized = NormalizedOrder(
        order_id=order_id,
        create_time=create_time,
        create_date=create_date,
        theater_id=str(row.get("theaterId") or "")[:64],
        chapter_id=str(row.get("chapterId") or "")[:64],
        language=language,
        currency_type=str(row.get("currencyType") or "?").strip().upper()[:8] or "?",
        amount_minor=amount,
        usd_order_amount_minor=usd,
        refund_time=refund_time,
        is_returned=refund_time is not None,
        promotion_code=str(row.get("promotionCode") or "").strip()[:64] or None,
        order_class=None,
    )
    if classifier is None:
        classifier = build_default_classifier(get_settings())
    normalized.order_class = classifier.classify(normalized)
    return normalized


# ---------- upsert（幂等，AC-S3） ----------


def _order_values(order: NormalizedOrder) -> dict:
    return {
        "order_id": order.order_id,
        "create_time": order.create_time,
        "create_date": order.create_date,
        "theater_id": order.theater_id,
        "chapter_id": order.chapter_id,
        "language": order.language,
        "currency_type": order.currency_type,
        "amount_minor": order.amount_minor,
        "usd_order_amount_minor": order.usd_order_amount_minor,
        "refund_time": order.refund_time,
        "is_returned": order.is_returned,
        "promotion_code": order.promotion_code,
        "order_class": order.order_class,
    }


def upsert_orders(
    db, orders: list[NormalizedOrder], *, batch_size: int = _UPSERT_BATCH_SIZE
) -> int:
    """批量 upsert（on_conflict_do_update 目标 = uq_orders_order_id）。

    批内按 order_id 去重（后写胜出，与上游窗口重叁时以最新行为准）。
    返回实际入库行数。commit 由调用方负责（阶段独立提交）。
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    unique: dict[str, NormalizedOrder] = {}
    for order in orders:
        unique[order.order_id] = order
    values = [_order_values(order) for order in unique.values()]
    for start in range(0, len(values), batch_size):
        chunk = values[start : start + batch_size]
        stmt = pg_insert(Order).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Order.order_id],
            set_={col: getattr(stmt.excluded, col) for col in _ORDER_UPDATE_COLUMNS}
            | {"updated_at": func.now()},
        )
        db.execute(stmt)
    return len(values)


def upsert_ad_revenue(db, summary: dict[date, Decimal]) -> int:
    """按日 upsert 广告收益（date 主键幂等，AC-U4）。commit 由调用方负责。"""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    count = 0
    values = [
        {"date": day, "amount_minor": amount} for day, amount in sorted(summary.items())
    ]
    for start in range(0, len(values), _UPSERT_BATCH_SIZE):
        chunk = values[start : start + _UPSERT_BATCH_SIZE]
        stmt = pg_insert(AdRevenueDaily).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=[AdRevenueDaily.date],
            set_={"amount_minor": stmt.excluded.amount_minor, "updated_at": func.now()},
        )
        db.execute(stmt)
        count += len(chunk)
    return count


# ---------- 覆盖自愈（§3.3.3） ----------


def _covered_dates(db, *, floor: date) -> set[date]:
    """成功运行（status ∈ success/partial 且 orders_error 空）覆盖日期的并集。"""
    rows = db.execute(
        select(SyncRun.window_start, SyncRun.window_end).where(
            SyncRun.status.in_(("success", "partial")),
            SyncRun.orders_error.is_(None),
            SyncRun.window_end >= floor,
        )
    ).all()
    covered: set[date] = set()
    for window_start, window_end in rows:
        day = window_start
        while day <= window_end:
            covered.add(day)
            day += timedelta(days=1)
    return covered


def scheduled_days(db, today: date, *, settings: Settings | None = None) -> tuple[list[date], str]:
    """计算本轮 scheduled 应拉的日期集合与实际 trigger。

    days = 最近 lookback_days 天（含当日）∪ 期望域 [today-backfill_days+1, today]
    中未被成功运行覆盖的日期（首次部署无运行记录 → 等价 92 天回填，D3/RQ-5）。
    含补拉日期时 trigger 记 backfill，否则 scheduled。
    """
    cfg = settings or get_settings()
    lookback = {today - timedelta(days=i) for i in range(max(1, cfg.sync_lookback_days))}
    expected = {today - timedelta(days=i) for i in range(max(1, cfg.sync_backfill_days))}
    covered = _covered_dates(db, floor=min(expected) - timedelta(days=1))
    missing = expected - covered
    days = sorted(lookback | missing)
    trigger = "backfill" if missing - lookback else "scheduled"
    return days, trigger


# ---------- 进度态 ----------


def _set_current(run: CurrentRun | None) -> None:
    global _current_run
    with _state_lock:
        _current_run = run


def _bump_days_done() -> None:
    with _state_lock:
        if _current_run is not None:
            _current_run.days_done += 1


def _set_phase(phase: str) -> None:
    with _state_lock:
        if _current_run is not None:
            _current_run.phase = phase


def is_running() -> bool:
    """当前是否有同步在进行（summary meta.sync_status='running' 的数据源）。"""
    with _state_lock:
        return _current_run is not None


# ---------- 运行记录查询 ----------


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def status_snapshot(db) -> SyncStatusResponse:
    """GET /dashboard/sync/status 的数据源：进度态 + 最近一条非 running 运行。"""
    from app.schemas.dashboard import SyncCurrent, SyncLastRun

    with _state_lock:
        current = _current_run.snapshot() if _current_run is not None else None
    last = db.scalar(
        select(SyncRun).where(SyncRun.status != "running").order_by(SyncRun.id.desc()).limit(1)
    )
    current_model = (
        SyncCurrent(
            id=current.run_id,
            trigger=current.trigger,
            window_start=current.window_start.isoformat(),
            window_end=current.window_end.isoformat(),
            days_done=current.days_done,
            days_total=current.days_total,
            phase=current.phase,
        )
        if current is not None
        else None
    )
    last_model = (
        SyncLastRun(
            id=last.id,
            trigger=last.trigger,
            window_start=last.window_start.isoformat(),
            window_end=last.window_end.isoformat(),
            status=last.status,
            started_at=_iso(last.started_at),
            finished_at=_iso(last.finished_at),
            truncated_days=list(last.truncated_dates or []),
            orders_upserted=last.orders_upserted,
            orders_error=last.orders_error,
            ad_error=last.ad_error,
        )
        if last is not None
        else None
    )
    return SyncStatusResponse(
        state="running" if current is not None else "idle",
        current=current_model,
        last_run=last_model,
    )


def orders_sync_state(db) -> tuple[str, datetime | None, date | None]:
    """summary meta 的同步状态三元组：(sync_status, latest_orders_sync_at, latest_covered_date)。

    - sync_status ∈ ok|failed|running|never（订单阶段视角）；
    - latest_orders_sync_at = 最近 orders_error IS NULL 行的 finished_at（AC-S2）；
    - latest_covered_date = 最近成功运行 window_end（incomplete_tail 判据，D5）。
    """
    if is_running():
        latest_success = db.scalar(
            select(SyncRun)
            .where(SyncRun.orders_error.is_(None), SyncRun.finished_at.isnot(None))
            .order_by(SyncRun.id.desc())
            .limit(1)
        )
        return "running", getattr(latest_success, "finished_at", None), getattr(
            latest_success, "window_end", None
        )
    last = db.scalar(select(SyncRun).order_by(SyncRun.id.desc()).limit(1))
    if last is None:
        return "never", None, None
    latest_success = db.scalar(
        select(SyncRun)
        .where(SyncRun.orders_error.is_(None), SyncRun.finished_at.isnot(None))
        .order_by(SyncRun.id.desc())
        .limit(1)
    )
    status = "failed" if last.orders_error else "ok"
    return status, getattr(latest_success, "finished_at", None), getattr(
        latest_success, "window_end", None
    )


def truncated_days_in_range(db, date_from: date, date_to: date) -> list[str]:
    """查询区间内的截断日期（AC-S7 横幅数据源，按日精确呈现）。

    候选 = 与区间相交的运行行；再按「运行窗口 ∩ 查询区间」双夹取日。
    """
    rows = db.execute(
        select(SyncRun.truncated_dates, SyncRun.window_start, SyncRun.window_end).where(
            SyncRun.window_start <= date_to,
            SyncRun.window_end >= date_from,
        )
    ).all()
    days: set[str] = set()
    for truncated, window_start, window_end in rows:
        for day in truncated or []:
            if (
                max(window_start, date_from).isoformat()
                <= day
                <= min(window_end, date_to).isoformat()
            ):
                days.add(day)
    return sorted(days)


def latest_ad_state(db) -> tuple[bool, str | None]:
    """(ad_available, ad_error)：最近一次订单成功运行的广告阶段状态（AC-S9）。"""
    run = db.scalar(
        select(SyncRun)
        .where(SyncRun.orders_error.is_(None), SyncRun.status.in_(("success", "partial")))
        .order_by(SyncRun.id.desc())
        .limit(1)
    )
    if run is None:
        return False, None
    return run.ad_error is None, run.ad_error


def cleanup_orphan_runs(db=None) -> int:
    """孤儿 running 行清理（m9）：进程崩溃/重启遗留行改判 failed。

    lifespan 启动时（先于调度器）执行一次，保证状态行/last_run 永不悬挂。
    """
    owns = db is None
    db = db or SessionLocal()
    try:
        result = db.execute(
            update(SyncRun)
            .where(SyncRun.status == "running")
            .values(
                status="failed",
                orders_error=func.coalesce(SyncRun.orders_error, "orphaned: process restarted"),
                finished_at=func.now(),
            )
        )
        db.commit()
        return result.rowcount or 0
    finally:
        if owns:
            db.close()


# ---------- 管道本体 ----------


def execute_run(
    trigger: str,
    days: list[date],
    *,
    db,
    client_factory: Callable[[], UpstreamClient] | None = None,
    classifier: OrderClassifier | None = None,
    settings: Settings | None = None,
) -> SyncRun:
    """执行一次同步（调用方须持单飞锁）。两阶段独立 commit，run 行收尾定稿。"""
    cfg = settings or get_settings()
    days = sorted(days)
    if classifier is None:
        # 空盐 = 响亮失败（REQ-20261014-01）：tag 入库后永不改变，落 NULL 只能
        # 人工回填——宁可本轮同步失败，也不静默写空标签。零拉取、零写入。
        try:
            classifier = build_default_classifier(cfg)
        except ValueError as exc:
            logger.error("sync aborted: %s", exc)
            run = SyncRun(
                trigger=trigger,
                window_start=days[0],
                window_end=days[-1],
                status="failed",
                orders_error=f"order classifier unavailable: {exc}",
                finished_at=datetime.now(UTC),
            )
            db.add(run)
            db.commit()
            return run
    run = SyncRun(trigger=trigger, window_start=days[0], window_end=days[-1], status="running")
    db.add(run)
    db.commit()  # running 状态先行可见（状态行/轮询）
    _set_current(
        CurrentRun(run.id, trigger, days[0], days[-1], days_total=len(days))
    )

    orders_error: str | None = None
    ad_error: str | None = None
    truncated: set[date] = set()
    fetched_rows: list[dict] = []
    orders_upserted = 0

    client: UpstreamClient = (client_factory or UpstreamClient)()
    try:
        try:
            # ---- orders 阶段：日窗并发拉取 + 单会话串行 upsert ----
            _set_phase("orders")
            with ThreadPoolExecutor(max_workers=max(1, cfg.upstream_concurrency)) as pool:
                futures = {pool.submit(fetch_day, client, day, settings=cfg): day for day in days}
                for future in as_completed(futures):
                    day = futures[future]
                    try:
                        result = future.result()
                        fetched_rows.extend(result.rows)
                        if result.truncated:
                            truncated.add(day)
                    except UpstreamError as exc:
                        # 失败窗口留给下一轮 30 分钟同步或手动刷新自愈（AC-U7）
                        logger.warning("fetch_day %s failed: %s", day, exc)
                        if orders_error is None:
                            orders_error = f"{day.isoformat()}: {exc}"
                    _bump_days_done()
            normalized = [
                order
                for row in fetched_rows
                if (order := normalize_order(row, classifier)) is not None
            ]
            if any(order.order_class is None for order in normalized):
                # 不变量守卫：分类器必须给出 tag，NULL 落库后同步路径永不回填
                raise ValueError("classifier returned NULL order_class for some orders")
            orders_upserted = upsert_orders(db, normalized)
            db.commit()  # orders 阶段独立 commit
        except Exception as exc:  # noqa: BLE001 - 阶段失败统一降级，不裸抛 500
            db.rollback()
            logger.exception("orders phase failed")
            orders_error = orders_error or f"orders phase failed: {exc}"

        # ---- ad 阶段：逐日拉取 + 按日 upsert（AC-S9：失败不连坐订单） ----
        _set_phase("ad")
        try:
            ad_result = fetch_ad_summary(client, days[0], days[-1], settings=cfg)
            upsert_ad_revenue(db, ad_result.summary)
            db.commit()
            if ad_result.failed_days:
                # 单日失败：成功日已落库（下一轮 lookback 自愈失败日），本轮记 partial
                shown = ", ".join(day.isoformat() for day in ad_result.failed_days[:10])
                suffix = "" if len(ad_result.failed_days) <= 10 else " ..."
                ad_error = (
                    f"ad sync failed on {len(ad_result.failed_days)} day(s): {shown}{suffix}"
                )
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.warning("ad phase failed: %s", exc)
            ad_error = f"ad sync failed: {exc}"
    finally:
        client.close()

    status = (
        "failed"
        if orders_error
        else ("partial" if (ad_error or truncated) else "success")
    )
    run.status = status
    run.orders_fetched = len(fetched_rows)
    run.orders_upserted = orders_upserted
    run.truncated_dates = sorted(day.isoformat() for day in truncated)
    run.orders_error = orders_error
    run.ad_error = ad_error
    run.finished_at = datetime.now(UTC)
    db.commit()
    _set_current(None)
    logger.info(
        "sync run %s (%s, %s..%s) finished: status=%s fetched=%d upserted=%d truncated=%d",
        run.id, trigger, days[0], days[-1], status, run.orders_fetched,
        run.orders_upserted, len(run.truncated_dates),
    )
    return run


def run_scheduled(
    *,
    db=None,
    client_factory: Callable[[], UpstreamClient] | None = None,
    today: date | None = None,
    settings: Settings | None = None,
) -> SyncRun | None:
    """定时（含覆盖自愈/回填）入口；单飞锁被占则跳过本轮并返回 None。"""
    if not _sync_lock.acquire(blocking=False):
        logger.info("scheduled sync skipped: another run is in flight")
        return None
    try:
        cfg = settings or get_settings()
        today = today or datetime.now(UTC).date()
        owns = db is None
        db = db or SessionLocal()
        try:
            days, trigger = scheduled_days(db, today, settings=cfg)
            if not days:
                return None
            return execute_run(trigger, days, db=db, client_factory=client_factory, settings=cfg)
        finally:
            if owns:
                db.close()
    finally:
        _sync_lock.release()


def clamp_manual_window(date_from: date, date_to: date, *, today: date) -> tuple[date, date]:
    """手动区间服务端钳制（§3.3.2）：to ≤ 今天(UTC)、跨度 ≤ 92 天、from ≤ to。"""
    date_to = min(date_to, today)
    date_from = min(date_from, today)
    date_from = max(date_from, date_to - timedelta(days=MAX_RANGE_DAYS - 1))
    return (date_from, date_to) if date_from <= date_to else (date_to, date_to)


def run_manual_blocking(
    date_from: date,
    date_to: date,
    *,
    db=None,
    client_factory: Callable[[], UpstreamClient] | None = None,
    today: date | None = None,
    settings: Settings | None = None,
) -> SyncRun | None:
    """手动同步（阻塞形态，测试与脚本用）：全区间重拉（RQ-2）。锁被占返回 None。"""
    if not _sync_lock.acquire(blocking=False):
        return None
    try:
        cfg = settings or get_settings()
        today = today or datetime.now(UTC).date()
        date_from, date_to = clamp_manual_window(date_from, date_to, today=today)
        days = [
            date_from + timedelta(days=i)
            for i in range((date_to - date_from).days + 1)
        ]
        owns = db is None
        db = db or SessionLocal()
        try:
            return execute_run(
                "manual", days, db=db, client_factory=client_factory, settings=cfg
            )
        finally:
            if owns:
                db.close()
    finally:
        _sync_lock.release()


def _manual_worker(date_from: date, date_to: date) -> None:
    """手动同步的后台线程体（start_manual 拉起；锁已由 start_manual 持有）。"""
    try:
        cfg = get_settings()
        today = datetime.now(UTC).date()
        date_from, date_to = clamp_manual_window(date_from, date_to, today=today)
        days = [date_from + timedelta(days=i) for i in range((date_to - date_from).days + 1)]
        db = SessionLocal()
        try:
            execute_run("manual", days, db=db, settings=cfg)
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        logger.exception("manual sync worker crashed")
    finally:
        _sync_lock.release()


def start_manual(date_from: date, date_to: date) -> bool:
    """↻ 手动插队（D4/AC-S4）：后台线程执行当前区间同步（全区间重拉）。

    单飞锁被占 → 返回 False（accepted=false，前端继续轮询进度）。
    """
    if not _sync_lock.acquire(blocking=False):
        return False
    threading.Thread(
        target=_manual_worker, args=(date_from, date_to), daemon=True, name="sync-manual"
    ).start()
    return True
