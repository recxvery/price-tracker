from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_history import PriceHistory


class PriceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, entry: PriceHistory) -> None:
        self.session.add(entry)

    async def list_for_item(
        self,
        item_id: int,
        limit: int,
        offset: int,
    ) -> list[PriceHistory]:
        result = await self.session.execute(
            select(PriceHistory)
            .where(PriceHistory.item_id == item_id)
            .order_by(PriceHistory.fetched_at.desc(), PriceHistory.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_for_item(self, item_id: int) -> int:
        result = await self.session.execute(
            select(func.count(PriceHistory.id)).where(PriceHistory.item_id == item_id)
        )
        return int(result.scalar_one())
