from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUserDep, ItemServiceDep
from app.schemas.item import (
    TrackedItemCreate,
    TrackedItemRead,
    TrackedItemsPage,
    TrackedItemUpdate,
)
from app.schemas.price import PriceHistoryPage

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", response_model=TrackedItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: TrackedItemCreate,
    user: CurrentUserDep,
    service: ItemServiceDep,
) -> TrackedItemRead:
    item = await service.create(user.id, payload)
    return TrackedItemRead.model_validate(item)


@router.get("", response_model=TrackedItemsPage)
async def list_items(
    user: CurrentUserDep,
    service: ItemServiceDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TrackedItemsPage:
    items, total = await service.list_items(user.id, limit, offset)
    return TrackedItemsPage(
        items=[TrackedItemRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{item_id}", response_model=TrackedItemRead)
async def get_item(
    item_id: int,
    user: CurrentUserDep,
    service: ItemServiceDep,
) -> TrackedItemRead:
    return TrackedItemRead.model_validate(await service.get(item_id, user.id))


@router.patch("/{item_id}", response_model=TrackedItemRead)
async def update_item(
    item_id: int,
    payload: TrackedItemUpdate,
    user: CurrentUserDep,
    service: ItemServiceDep,
) -> TrackedItemRead:
    item = await service.update(item_id, user.id, payload)
    return TrackedItemRead.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: int,
    user: CurrentUserDep,
    service: ItemServiceDep,
) -> None:
    await service.delete(item_id, user.id)


@router.post("/{item_id}/refresh", response_model=TrackedItemRead)
async def refresh_item(
    item_id: int,
    user: CurrentUserDep,
    service: ItemServiceDep,
) -> TrackedItemRead:
    return TrackedItemRead.model_validate(
        await service.refresh_for_user(item_id, user.id)
    )


@router.get("/{item_id}/history", response_model=PriceHistoryPage)
async def item_history(
    item_id: int,
    user: CurrentUserDep,
    service: ItemServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PriceHistoryPage:
    history, total = await service.history(item_id, user.id, limit, offset)
    return PriceHistoryPage(
        item_id=item_id,
        history=history,
        total=total,
        limit=limit,
        offset=offset,
    )
