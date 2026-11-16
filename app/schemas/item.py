from datetime import datetime
from decimal import Decimal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class TrackedItemCreate(BaseModel):
    url: AnyHttpUrl
    title: str | None = Field(default=None, max_length=500)
    target_price: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )


class TrackedItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    target_price: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    is_active: bool | None = None


class TrackedItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    title: str
    current_price: Decimal | None
    currency: str | None
    target_price: Decimal | None
    is_active: bool
    last_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TrackedItemsPage(BaseModel):
    items: list[TrackedItemRead]
    total: int
    limit: int
    offset: int
