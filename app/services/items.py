import logging
from urllib.parse import urlsplit

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, PriceFetchError
from app.db.base import utc_now
from app.models.price_history import PriceHistory
from app.models.tracked_item import TrackedItem
from app.repositories.items import ItemRepository
from app.repositories.prices import PriceRepository
from app.schemas.item import TrackedItemCreate, TrackedItemUpdate
from app.services.price_fetcher import ProductPriceFetcher
from app.services.price_parser import ProductData

logger = logging.getLogger(__name__)


class ItemService:
    def __init__(self, session: AsyncSession, fetcher: ProductPriceFetcher) -> None:
        self.session = session
        self.fetcher = fetcher
        self.items = ItemRepository(session)
        self.prices = PriceRepository(session)

    async def create(self, user_id: int, payload: TrackedItemCreate) -> TrackedItem:
        url = self.fetcher.validate_url(str(payload.url))
        if await self.items.get_by_url(user_id, url) is not None:
            raise ConflictError("Эта ссылка уже отслеживается")

        await self.session.commit()
        product = await self._fetch_initial_data(url)
        now = utc_now()
        title = (
            (payload.title or "").strip()
            or (product.title if product else None)
            or urlsplit(url).netloc
        )

        item = TrackedItem(
            user_id=user_id,
            url=url,
            title=title[:500],
            current_price=product.price if product else None,
            currency=product.currency if product else None,
            target_price=payload.target_price,
            last_checked_at=now if product else None,
        )
        self.items.add(item)

        try:
            await self.session.flush()
            if product is not None and product.price is not None:
                self.prices.add(
                    PriceHistory(
                        item_id=item.id,
                        price=product.price,
                        currency=product.currency,
                        fetched_at=now,
                    )
                )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Эта ссылка уже отслеживается") from exc

        await self.session.refresh(item)
        return item

    async def list_items(
        self,
        user_id: int,
        limit: int,
        offset: int,
    ) -> tuple[list[TrackedItem], int]:
        items = await self.items.list_for_user(user_id, limit, offset)
        total = await self.items.count_for_user(user_id)
        return items, total

    async def get(self, item_id: int, user_id: int) -> TrackedItem:
        item = await self.items.get_for_user(item_id, user_id)
        if item is None:
            raise NotFoundError("Товар не найден")
        return item

    async def update(
        self,
        item_id: int,
        user_id: int,
        payload: TrackedItemUpdate,
    ) -> TrackedItem:
        item = await self.get(item_id, user_id)
        changes = payload.model_dump(exclude_unset=True)

        if "title" in changes and changes["title"] is not None:
            item.title = changes["title"].strip()
        if "target_price" in changes:
            item.target_price = changes["target_price"]
        if "is_active" in changes and changes["is_active"] is not None:
            item.is_active = changes["is_active"]

        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def delete(self, item_id: int, user_id: int) -> None:
        item = await self.get(item_id, user_id)
        await self.items.delete(item)
        await self.session.commit()

    async def refresh_for_user(self, item_id: int, user_id: int) -> TrackedItem:
        item = await self.get(item_id, user_id)
        return await self._refresh(item)

    async def refresh(self, item_id: int) -> TrackedItem:
        item = await self.items.get_by_id(item_id)
        if item is None:
            raise NotFoundError("Товар не найден")
        return await self._refresh(item)

    async def history(
        self,
        item_id: int,
        user_id: int,
        limit: int,
        offset: int,
    ) -> tuple[list[PriceHistory], int]:
        await self.get(item_id, user_id)
        history = await self.prices.list_for_item(item_id, limit, offset)
        total = await self.prices.count_for_item(item_id)
        return history, total

    async def _refresh(self, item: TrackedItem) -> TrackedItem:
        now = utc_now()
        await self.session.commit()
        try:
            product = await self.fetcher.fetch(item.url)
        except PriceFetchError:
            item.last_checked_at = now
            await self.session.commit()
            raise

        item.current_price = product.price
        item.currency = product.currency or item.currency
        item.last_checked_at = now
        if product.price is not None:
            self.prices.add(
                PriceHistory(
                    item_id=item.id,
                    price=product.price,
                    currency=item.currency,
                    fetched_at=now,
                )
            )

        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def _fetch_initial_data(self, url: str) -> ProductData | None:
        try:
            return await self.fetcher.fetch(url)
        except PriceFetchError as exc:
            logger.warning("Initial price fetch failed for %s: %s", url, exc.detail)
            return None
