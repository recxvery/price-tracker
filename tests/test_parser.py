from decimal import Decimal

import pytest

from app.services.price_parser import (
    extract_product_data,
    normalize_currency,
    parse_price,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1 299,00 ₽", Decimal("1299.00")),
        ("1,299.50 USD", Decimal("1299.50")),
        ("12.5", Decimal("12.50")),
        ("2 490", Decimal("2490.00")),
        ("1.299", Decimal("1299.00")),
        ("5,000", Decimal("5000.00")),
        ("499,90 руб.", Decimal("499.90")),
        ("цена не указана", None),
    ],
)
def test_parse_price(raw: str, expected: Decimal | None) -> None:
    assert parse_price(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("RUB", "RUB"),
        ("usd", "USD"),
        ("₽", "RUB"),
        ("руб.", "RUB"),
        ("€", "EUR"),
        (None, None),
    ],
)
def test_normalize_currency(raw: str | None, expected: str | None) -> None:
    assert normalize_currency(raw) == expected


def test_extracts_json_ld_product() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Наушники",
            "offers": {"@type": "Offer", "price": "7990.00", "priceCurrency": "RUB"}
          }
        </script>
      </head>
    </html>
    """

    product = extract_product_data(html, "https://shop.example.com/headphones")

    assert product.title == "Наушники"
    assert product.price == Decimal("7990.00")
    assert product.currency == "RUB"


def test_extracts_open_graph_price() -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="Кофеварка" />
        <meta property="product:price:amount" content="4 590,50" />
        <meta property="product:price:currency" content="RUB" />
      </head>
    </html>
    """

    product = extract_product_data(html, "https://shop.example.com/coffee")

    assert product.title == "Кофеварка"
    assert product.price == Decimal("4590.50")
    assert product.currency == "RUB"


def test_extracts_microdata_price() -> None:
    html = """
    <html>
      <body>
        <h1>Товар</h1>
        <div itemscope itemtype="https://schema.org/Product">
          <span itemprop="priceCurrency" content="USD"></span>
          <span itemprop="price" content="149.99"></span>
        </div>
      </body>
    </html>
    """

    product = extract_product_data(html, "https://shop.example.com/item")

    assert product.title == "Товар"
    assert product.price == Decimal("149.99")
    assert product.currency == "USD"


def test_returns_empty_price_when_page_has_no_price() -> None:
    html = "<html><head><title>Каталог</title></head><body></body></html>"

    product = extract_product_data(html, "https://shop.example.com/catalog")

    assert product.title == "Каталог"
    assert product.price is None
