from httpx import AsyncClient

from tests.conftest import register_user


async def test_register_login_and_profile(client: AsyncClient) -> None:
    headers = await register_user(client, email="user@example.com")

    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "USER@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


async def test_duplicate_email_is_rejected(client: AsyncClient) -> None:
    await register_user(client)

    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "student@example.com", "password": "password123"},
    )

    assert response.status_code == 409


async def test_login_with_wrong_password_fails(client: AsyncClient) -> None:
    await register_user(client)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_private_routes_require_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/items")

    assert response.status_code == 401
