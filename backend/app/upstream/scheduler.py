"""定时同步调度器（DESIGN-20261012-02 §3.4，S2 决策）。

FastAPI lifespan 启动的 asyncio 循环任务：同步管道本体为同步代码，经
asyncio.to_thread 执行（DB 是同步 SQLAlchemy，不阻塞事件循环）。
启动条件双保险：sync_enabled=false 或上游凭据未配置均不启动（m7）。
"""

import asyncio
import logging

from app.config import Settings, get_settings
from app.services import sync_service

logger = logging.getLogger("app.upstream")


def scheduler_should_start(settings: Settings) -> bool:
    """调度器启动判定：总开关 + 凭据已配置（DESIGN §3.4，双保险）。"""
    return settings.sync_enabled and settings.upstream_credentials_configured


async def scheduler_loop() -> None:
    """循环：立即跑一轮（含回填判定）→ 每 sync_interval_minutes 一轮。"""
    settings = get_settings()
    while True:
        try:
            await asyncio.to_thread(sync_service.run_scheduled)
        except Exception:  # noqa: BLE001 - 单轮失败不终止调度（下一轮自愈）
            logger.exception("scheduled sync run crashed")
        await asyncio.sleep(settings.sync_interval_minutes * 60)
