from decimal import Decimal

from httpx import AsyncClient

from tests.conftest import FakeFetcher, register_user


async def test_item_lifecycle(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_fetcher: FakeFetcher,
) -> None:
    response = await client.post(
        "/api/v1/items",
        headers=auth_headers,
        json={"url": "https://shop.example.com/product/42", "target_price": 1000},
    )

    assert response.status_code == 201
    item = response.json()
    assert item["title"] == "Test product"
    assert Decimal(item["current_price"]) == Decimal("1299.00")
    assert item["currency"] == "RUB"
    item_id = item["id"]

    response = await client.get("/api/v1/items", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1

    fake_fetcher.price = Decimal("999.00")
    response = await client.post(
        f"/api/v1/items/{item_id}/refresh",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert Decimal(response.json()["current_price"]) == Decimal("999.00")

    response = await client.get(
        f"/api/v1/items/{item_id}/history",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert Decimal(body["history"][0]["price"]) == Decimal("999.00")

    response = await client.patch(
        f"/api/v1/items/{item_id}",
        headers=auth_headers,
        json={"target_price": None, "is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["target_price"] is None
    assert response.json()["is_active"] is False

    response = await client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert response.status_code == 204

    response = await client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert response.status_code == 404


async def test_duplicate_item_is_rejected(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    payload = {"url": "https://shop.example.com/product/42"}
    first = await client.post("/api/v1/items", headers=auth_headers, json=payload)
    second = await client.post("/api/v1/items", headers=auth_headers, json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


async def test_item_is_created_when_price_parsing_fails(
    client: AsyncClient,
    auth_headers: dict[str, str],
    fake_fetcher: FakeFetcher,
    fetch_error,
) -> None:
    fake_fetcher.error = fetch_error

    response = await client.post(
        "/api/v1/items",
        headers=auth_headers,
        json={"url": "https://shop.example.com/product/42"},
    )

    assert response.status_code == 201
    assert response.json()["current_price"] is None
    assert response.json()["title"] == "shop.example.com"


async def test_local_url_is_rejected(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/api/v1/items",
        headers=auth_headers,
        json={"url": "http://localhost/admin"},
    )

    assert response.status_code == 422


async def test_user_cannot_access_foreign_item(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/api/v1/items",
        headers=auth_headers,
        json={"url": "https://shop.example.com/product/42"},
    )
    item_id = response.json()["id"]

    other_headers = await register_user(client, email="other@example.com")
    response = await client.get(f"/api/v1/items/{item_id}", headers=other_headers)

    assert response.status_code == 404
