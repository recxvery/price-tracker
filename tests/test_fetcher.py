import httpx
import pytest

from app.core.exceptions import PriceFetchError
from app.services.price_fetcher import ProductPriceFetcher

PRODUCT_HTML = """
<html>
  <head>
    <meta property="product:price:amount" content="1499.00" />
    <meta property="product:price:currency" content="RUB" />
    <title>Товар</title>
  </head>
</html>
"""


async def test_fetch_retries_server_error() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(200, text=PRODUCT_HTML, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = ProductPriceFetcher(client)
        fetcher.settings.http_retry_delay_seconds = 0

        product = await fetcher.fetch("https://93.184.216.34/product")

    assert calls == 2
    assert product.title == "Товар"
    assert str(product.price) == "1499.00"


async def test_fetch_fails_after_retries() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        fetcher = ProductPriceFetcher(client)
        fetcher.settings.http_retry_delay_seconds = 0

        with pytest.raises(PriceFetchError):
            await fetcher.fetch("https://93.184.216.34/product")
