import pytest

from app.core.exceptions import InvalidUrlError
from app.services.price_fetcher import ProductPriceFetcher


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/file",
        "http://localhost/admin",
        "http://127.0.0.1/admin",
        "http://192.168.1.10/admin",
        "http://user:pass@example.com/product",
        "https://example.com:70000/product",
    ],
)
def test_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(InvalidUrlError):
        ProductPriceFetcher().validate_url(url)


def test_normalizes_url() -> None:
    url = ProductPriceFetcher().validate_url(
        "HTTPS://Shop.Example.com/product/42?color=red#reviews"
    )

    assert url == "https://shop.example.com/product/42?color=red"
