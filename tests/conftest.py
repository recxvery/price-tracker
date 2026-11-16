import os
from collections.abc import AsyncIterator
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["SCHEDULER_ENABLED"] = "false"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_price_fetcher
from app.core.exceptions import PriceFetchError
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.services.price_fetcher import ProductPriceFetcher
from app.services.price_parser import ProductData


class FakeFetcher:
    def __init__(self) -> None:
        self.title = "Test product"
        self.price = Decimal("1299.00")
        self.currency = "RUB"
        self.error: Exception | None = None
        self.validator = ProductPriceFetcher()

    def validate_url(self, url: str) -> str:
        return self.validator.validate_url(url)

    async def fetch(self, url: str) -> ProductData:
        if self.error is not None:
            raise self.error
        return ProductData(
            title=self.title,
            price=self.price,
            currency=self.currency,
        )


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@pytest_asyncio.fixture
async def fake_fetcher() -> FakeFetcher:
    return FakeFetcher()


@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
    fake_fetcher: FakeFetcher,
) -> AsyncIterator[AsyncClient]:
    async def override_session():
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_price_fetcher] = lambda: fake_fetcher

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()


async def register_user(
    client: AsyncClient,
    email: str = "student@example.com",
    password: str = "password123",
) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    return await register_user(client)


@pytest.fixture
def fetch_error() -> PriceFetchError:
    return PriceFetchError("Сайт недоступен")
