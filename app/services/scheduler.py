import asyncio
import logging

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.db.session import session_context
from app.repositories.items import ItemRepository
from app.services.items import ItemService
from app.services.price_fetcher import ProductPriceFetcher

logger = logging.getLogger(__name__)


def create_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        check_tracked_items,
        IntervalTrigger(hours=settings.price_check_interval_hours),
        id="price-check",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    return scheduler


async def check_tracked_items() -> None:
    settings = get_settings()

    async with session_context() as session:
        item_ids = await ItemRepository(session).list_active_ids()

    if not item_ids:
        logger.info("Price check skipped: no active items")
        return

    semaphore = asyncio.Semaphore(settings.max_concurrent_checks)
    async with httpx.AsyncClient(
        timeout=settings.http_timeout_seconds,
        follow_redirects=False,
    ) as client:
        fetcher = ProductPriceFetcher(client)

        async def refresh_item(item_id: int) -> bool:
            async with semaphore, session_context() as session:
                service = ItemService(session, fetcher)
                try:
                    await service.refresh(item_id)
                except Exception:
                    logger.exception("Price check failed for item %s", item_id)
                    return False
                return True

        results = await asyncio.gather(*(refresh_item(item_id) for item_id in item_ids))

    failed = results.count(False)
    logger.info(
        "Price check finished: %s checked, %s failed",
        len(results) - failed,
        failed,
    )
