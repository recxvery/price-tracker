from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.core.security import get_user_id_from_token
from app.db.session import get_session
from app.models.user import User
from app.repositories.users import UserRepository
from app.services.auth import AuthService
from app.services.items import ItemService
from app.services.price_fetcher import ProductPriceFetcher

bearer_scheme = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_auth_service(session: SessionDep) -> AuthService:
    return AuthService(session)


def get_price_fetcher() -> ProductPriceFetcher:
    return ProductPriceFetcher()


def get_item_service(
    session: SessionDep,
    fetcher: Annotated[ProductPriceFetcher, Depends(get_price_fetcher)],
) -> ItemService:
    return ItemService(session, fetcher)


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> User:
    if credentials is None:
        raise AuthenticationError("Для доступа нужен Bearer-токен")

    user_id = get_user_id_from_token(credentials.credentials)
    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Пользователь не найден или отключен")
    return user


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
