from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PriceHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    price: Decimal
    currency: str | None
    fetched_at: datetime


class PriceHistoryPage(BaseModel):
    item_id: int
    history: list[PriceHistoryRead]
    total: int
    limit: int
    offset: int
