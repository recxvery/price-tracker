from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tracked_item import TrackedItem


class ItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, item_id: int) -> TrackedItem | None:
        return await self.session.get(TrackedItem, item_id)

    async def get_for_user(self, item_id: int, user_id: int) -> TrackedItem | None:
        result = await self.session.execute(
            select(TrackedItem).where(
                TrackedItem.id == item_id,
                TrackedItem.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_url(self, user_id: int, url: str) -> TrackedItem | None:
        result = await self.session.execute(
            select(TrackedItem).where(
                TrackedItem.user_id == user_id,
                TrackedItem.url == url,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: int,
        limit: int,
        offset: int,
    ) -> list[TrackedItem]:
        result = await self.session.execute(
            select(TrackedItem)
            .where(TrackedItem.user_id == user_id)
            .order_by(TrackedItem.created_at.desc(), TrackedItem.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_for_user(self, user_id: int) -> int:
        result = await self.session.execute(
            select(func.count(TrackedItem.id)).where(TrackedItem.user_id == user_id)
        )
        return int(result.scalar_one())

    async def list_active_ids(self, limit: int = 1000) -> list[int]:
        result = await self.session.execute(
            select(TrackedItem.id)
            .where(TrackedItem.is_active.is_(True))
            .order_by(TrackedItem.last_checked_at.asc().nullsfirst())
            .limit(limit)
        )
        return list(result.scalars().all())

    def add(self, item: TrackedItem) -> None:
        self.session.add(item)

    async def delete(self, item: TrackedItem) -> None:
        await self.session.delete(item)
