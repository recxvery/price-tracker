import json
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from bs4 import BeautifulSoup, Tag

CURRENCY_SYMBOLS = {
    "₽": "RUB",
    "руб": "RUB",
    "р.": "RUB",
    "$": "USD",
    "usd": "USD",
    "€": "EUR",
    "eur": "EUR",
    "₸": "KZT",
    "₴": "UAH",
    "£": "GBP",
    "¥": "CNY",
    "cny": "CNY",
}

PRICE_META_KEYS = (
    "product:price:amount",
    "og:price:amount",
    "product:price",
    "price",
)

CURRENCY_META_KEYS = (
    "product:price:currency",
    "og:price:currency",
    "price:currency",
)

PRICE_SELECTORS = (
    "[data-price]",
    "[itemprop='price']",
    ".product-price",
    ".price-value",
    ".price",
    "#price",
)


@dataclass(slots=True)
class ProductData:
    title: str | None
    price: Decimal | None
    currency: str | None


def parse_price(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float, Decimal)):
        text = str(value)
    else:
        text = str(value).strip()

    if not text:
        return None

    text = text.replace("\u00a0", " ").replace("\u202f", " ")
    match = re.search(r"\d[\d\s.,']*", text)
    if match is None:
        return None

    number = re.sub(r"[^\d.,]", "", match.group(0))
    number = number.strip(".,")
    if not number:
        return None

    if "," in number and "." in number:
        if number.rfind(",") > number.rfind("."):
            number = number.replace(".", "").replace(",", ".")
        else:
            number = number.replace(",", "")
    elif "," in number:
        parts = number.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            number = ".".join(parts)
        else:
            number = "".join(parts)
    elif "." in number:
        parts = number.split(".")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            number = ".".join(parts)
        else:
            number = "".join(parts)

    try:
        amount = Decimal(number)
    except InvalidOperation:
        return None

    if not amount.is_finite() or amount < 0:
        return None

    if amount > Decimal("9999999999.99"):
        return None

    try:
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def normalize_currency(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    upper = text.upper()
    if len(upper) == 3 and upper.isalpha():
        return upper

    lower = text.lower()
    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in lower:
            return code

    return None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _meta_content(soup: BeautifulSoup, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        tag = soup.find("meta", attrs={"property": key})
        if tag is None:
            tag = soup.find("meta", attrs={"name": key})
        content = tag.get("content") if isinstance(tag, Tag) else None
        if content:
            return str(content)
    return None


def _walk_json(value: Any):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _has_type(node: dict[str, Any], expected: str) -> bool:
    value = node.get("@type")
    if isinstance(value, str):
        return value.lower() == expected
    if isinstance(value, list):
        return any(str(item).lower() == expected for item in value)
    return False


def _find_product_json(soup: BeautifulSoup) -> dict[str, Any] | None:
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        for node in _walk_json(payload):
            if isinstance(node, dict) and _has_type(node, "product"):
                return node
    return None


def _offers(node: dict[str, Any]):
    offers = node.get("offers")
    if isinstance(offers, dict):
        yield offers
        nested = offers.get("offers")
        if isinstance(nested, (dict, list)):
            yield from _offers(offers)
    elif isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict):
                yield offer
                nested = offer.get("offers")
                if isinstance(nested, (dict, list)):
                    yield from _offers(offer)


def _price_from_product(product: dict[str, Any]) -> tuple[Decimal | None, str | None]:
    for offer in _offers(product):
        price = offer.get("price") or offer.get("lowPrice") or offer.get("highPrice")
        parsed = parse_price(price)
        if parsed is not None:
            return parsed, normalize_currency(offer.get("priceCurrency"))
    return None, None


def _price_from_microdata(soup: BeautifulSoup) -> tuple[Decimal | None, str | None]:
    tag = soup.find(attrs={"itemprop": "price"})
    if not isinstance(tag, Tag):
        return None, None

    raw = tag.get("content") or tag.get("value") or tag.get_text(" ", strip=True)
    price = parse_price(raw)
    if price is None:
        return None, None

    currency_tag = soup.find(attrs={"itemprop": "priceCurrency"})
    currency = None
    if isinstance(currency_tag, Tag):
        raw_currency = currency_tag.get("content") or currency_tag.get_text(
            " ", strip=True
        )
        currency = normalize_currency(raw_currency)
    return price, currency


def _price_from_selectors(soup: BeautifulSoup) -> tuple[Decimal | None, str | None]:
    for selector in PRICE_SELECTORS:
        tag = soup.select_one(selector)
        if not isinstance(tag, Tag):
            continue
        raw = (
            tag.get("content") or tag.get("data-price") or tag.get_text(" ", strip=True)
        )
        price = parse_price(raw)
        if price is not None:
            return price, normalize_currency(raw)
    return None, None


def _page_title(soup: BeautifulSoup) -> str | None:
    title = _meta_content(soup, ("og:title", "twitter:title"))
    if title:
        return _clean_text(title)
    if soup.h1:
        return _clean_text(soup.h1.get_text(" ", strip=True))
    if soup.title:
        return _clean_text(soup.title.get_text(" ", strip=True))
    return None


def extract_product_data(html: str, url: str) -> ProductData:
    soup = BeautifulSoup(html, "html.parser")
    title = _page_title(soup)

    product = _find_product_json(soup)
    price = None
    currency = None

    if product is not None:
        title = _clean_text(product.get("name")) or title
        price, currency = _price_from_product(product)

    if price is None:
        raw_price = _meta_content(soup, PRICE_META_KEYS)
        price = parse_price(raw_price)
        currency = normalize_currency(_meta_content(soup, CURRENCY_META_KEYS))

    if price is None:
        price, currency = _price_from_microdata(soup)

    if price is None:
        price, currency = _price_from_selectors(soup)

    if currency is None:
        raw_currency = _meta_content(soup, CURRENCY_META_KEYS)
        currency = normalize_currency(raw_currency)

    return ProductData(title=title, price=price, currency=currency)
