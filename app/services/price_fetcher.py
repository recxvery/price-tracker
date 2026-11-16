import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from app.core.config import get_settings
from app.core.exceptions import InvalidUrlError, PriceFetchError
from app.services.price_parser import ProductData, extract_product_data

REDIRECT_STATUSES = {301, 302, 303, 307, 308}
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
MAX_REDIRECTS = 5

REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


class ProductPriceFetcher:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.settings = get_settings()
        self.client = client

    def validate_url(self, url: str) -> str:
        try:
            parsed = urlsplit(url.strip())
        except ValueError as exc:
            raise InvalidUrlError("Не удалось разобрать URL") from exc

        if parsed.scheme.lower() not in {"http", "https"}:
            raise InvalidUrlError("Поддерживаются только ссылки http и https")

        if not parsed.hostname:
            raise InvalidUrlError("В ссылке отсутствует домен")

        if parsed.username or parsed.password:
            raise InvalidUrlError("Ссылки с логином и паролем не поддерживаются")

        host = parsed.hostname.rstrip(".").lower()
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise InvalidUrlError("Некорректное имя домена") from exc

        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise InvalidUrlError("Локальные адреса недоступны для проверки")

        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None

        if address is not None and not address.is_global:
            raise InvalidUrlError("Локальные адреса недоступны для проверки")

        try:
            port = parsed.port
        except ValueError as exc:
            raise InvalidUrlError("Некорректный порт в ссылке") from exc

        netloc = f"[{host}]" if ":" in host else host
        default_ports = {"http": 80, "https": 443}
        if port is not None and port != default_ports[parsed.scheme.lower()]:
            netloc = f"{netloc}:{port}"

        path = parsed.path or "/"
        normalized = urlunsplit((parsed.scheme.lower(), netloc, path, parsed.query, ""))
        if len(normalized) > 2048:
            raise InvalidUrlError("Слишком длинная ссылка")
        return normalized

    async def fetch(self, url: str) -> ProductData:
        normalized_url = self.validate_url(url)
        await self._ensure_public_host(normalized_url)

        if self.client is not None:
            html = await self._download(self.client, normalized_url)
        else:
            async with self._client() as client:
                html = await self._download(client, normalized_url)

        product = extract_product_data(html, normalized_url)
        if product.price is None:
            raise PriceFetchError("На странице не удалось найти цену товара")

        return product

    async def _download(self, client: httpx.AsyncClient, url: str) -> str:
        current_url = url

        for _ in range(MAX_REDIRECTS + 1):
            await self._ensure_public_host(current_url)
            response = await self._get_with_retries(client, current_url)

            if response.status_code in REDIRECT_STATUSES:
                location = response.headers.get("location")
                if not location:
                    raise PriceFetchError("Сайт вернул пустое перенаправление")
                current_url = self.validate_url(urljoin(current_url, location))
                continue

            if response.status_code >= 400:
                raise PriceFetchError(
                    f"Сайт вернул ошибку со статусом {response.status_code}"
                )

            if len(response.content) > self.settings.max_response_bytes:
                raise PriceFetchError("Страница товара слишком большая")

            content_type = response.headers.get("content-type", "").lower()
            if (
                content_type
                and "html" not in content_type
                and "text" not in content_type
            ):
                raise PriceFetchError("Ссылка ведет не на HTML-страницу")

            await self._ensure_public_host(str(response.url))
            return response.text

        raise PriceFetchError("Слишком много перенаправлений")

    async def _get_with_retries(
        self,
        client: httpx.AsyncClient,
        url: str,
    ) -> httpx.Response:
        attempts = max(1, self.settings.http_max_retries + 1)
        last_error = "Не удалось загрузить страницу товара"

        for attempt in range(attempts):
            try:
                response = await client.get(url, headers=REQUEST_HEADERS)
            except httpx.TimeoutException:
                last_error = "Сайт не ответил за отведенное время"
            except httpx.HTTPError:
                last_error = "Не удалось загрузить страницу товара"
            else:
                if response.status_code not in RETRYABLE_STATUSES:
                    return response
                await response.aclose()
                if response.status_code == 429:
                    last_error = "Сайт ограничил частоту запросов"
                else:
                    last_error = (
                        f"Сайт вернул ошибку со статусом {response.status_code}"
                    )

            if attempt < attempts - 1:
                delay = self.settings.http_retry_delay_seconds * (2**attempt)
                await asyncio.sleep(delay)

        raise PriceFetchError(last_error)

    async def _ensure_public_host(self, url: str) -> None:
        host = urlsplit(url).hostname
        if not host:
            raise InvalidUrlError("В ссылке отсутствует домен")

        try:
            ipaddress.ip_address(host)
            return
        except ValueError:
            pass

        try:
            addresses = await asyncio.to_thread(
                socket.getaddrinfo,
                host,
                None,
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise PriceFetchError("Не удалось определить адрес сайта") from exc

        for entry in addresses:
            raw_address = entry[4][0].split("%", 1)[0]
            if not ipaddress.ip_address(raw_address).is_global:
                raise InvalidUrlError("Домен указывает на локальный адрес")

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.settings.http_timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": self.settings.user_agent},
        )
