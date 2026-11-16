from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest


@dataclass(slots=True)
class AuthResult:
    user: User
    access_token: str


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def register(self, payload: RegisterRequest) -> AuthResult:
        email = str(payload.email).lower()
        if await self.users.get_by_email(email) is not None:
            raise ConflictError("Пользователь с таким email уже зарегистрирован")

        user = User(
            email=email,
            hashed_password=hash_password(payload.password),
        )
        self.users.add(user)

        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError(
                "Пользователь с таким email уже зарегистрирован"
            ) from exc

        await self.session.refresh(user)
        return AuthResult(user=user, access_token=create_access_token(user.id))

    async def login(self, payload: LoginRequest) -> AuthResult:
        email = str(payload.email).lower()
        user = await self.users.get_by_email(email)
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise AuthenticationError("Неверный email или пароль")
        if not user.is_active:
            raise AuthenticationError("Учетная запись отключена")

        return AuthResult(user=user, access_token=create_access_token(user.id))
