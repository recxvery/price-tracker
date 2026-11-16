# Price Tracker API

Сервис для отслеживания цен на товары. Пользователь регистрируется, добавляет ссылку на товар, а фоновая задача раз в час перепроверяет страницу и сохраняет историю цен.

## Стек

- FastAPI + Pydantic v2
- PostgreSQL, SQLAlchemy 2.0 (async), Alembic
- httpx + BeautifulSoup4
- APScheduler
- JWT, Argon2
- Docker Compose
- Pytest, pytest-asyncio

## Что умеет

- Регистрация и вход по email и паролю, JWT-авторизация
- Добавление товара по ссылке с целевой ценой
- Получение текущей цены сразу при добавлении и по ручному запросу
- История изменений цены
- Периодическая проверка всех активных товаров
- Изоляция данных: пользователь видит только свои товары
- Защита от запросов к локальным и служебным адресам (SSRF)
- Swagger-документация

## Запуск через Docker

```bash
docker compose up --build
```

Миграции применяются автоматически при старте API.

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Healthcheck: http://localhost:8000/api/v1/health

Для своего секрета создайте `.env` на основе `.env.example` и задайте `JWT_SECRET`.

## Локальный запуск

Нужен Python 3.12+ и запущенный PostgreSQL.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
docker compose up db -d
alembic upgrade head
uvicorn app.main:app --reload
```

На Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
docker compose up db -d
alembic upgrade head
uvicorn app.main:app --reload
```

## Тесты

Тесты используют SQLite в памяти и не требуют PostgreSQL.

```bash
pytest
```

## API

| Метод | Путь | Назначение |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | Регистрация |
| POST | `/api/v1/auth/login` | Вход |
| GET | `/api/v1/auth/me` | Текущий пользователь |
| POST | `/api/v1/items` | Добавить товар |
| GET | `/api/v1/items` | Список товаров |
| GET | `/api/v1/items/{id}` | Товар |
| PATCH | `/api/v1/items/{id}` | Изменить название, целевую цену или активность |
| DELETE | `/api/v1/items/{id}` | Удалить товар |
| POST | `/api/v1/items/{id}/refresh` | Проверить цену сейчас |
| GET | `/api/v1/items/{id}/history` | История цен |
| GET | `/api/v1/health` | Проверка доступности |

Пример:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123"}'
```

```bash
curl -X POST http://localhost:8000/api/v1/items \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://shop.example.com/product/42","target_price":4990}'
```

## Структура

```text
app/
  api/            роуты, зависимости FastAPI
  core/           настройки, безопасность, доменные ошибки
  db/             подключение к БД, базовый класс моделей
  models/         SQLAlchemy-модели
  repositories/   запросы к БД
  schemas/        Pydantic-схемы
  services/       бизнес-логика, парсинг, планировщик
migrations/       Alembic
tests/            тесты API и парсера
```

Слои разделены по ответственности: роуты валидируют запрос и вызывают сервис, сервисы содержат бизнес-логику, репозитории работают с SQLAlchemy. Сетевые запросы не выполняются внутри транзакции с открытой сессией БД дольше необходимого.

## Как определяется цена

Парсер проверяет источники по приоритету:

1. JSON-LD (`schema.org/Product`, `Offer`)
2. Open Graph и `product:price:*`
3. Microdata (`itemprop="price"`)
4. Типовые CSS-классы и `data-price`

Поддерживаются цены с пробелами, запятыми и точками: `1 299,00 ₽`, `1,299.50 USD`, `499.90`. Если цену найти не удалось, товар всё равно сохраняется, а следующая фоновая проверка попробует снова.

## Фоновая проверка

APScheduler запускает задачу каждые `PRICE_CHECK_INTERVAL_HOURS` часов. Активные товары обрабатываются конкурентно, но с ограничением `MAX_CONCURRENT_CHECKS`. Ошибка на одной странице логируется и не прерывает проверку остальных. Одновременный запуск двух проверок запрещён.

Таймауты, сетевые ошибки, ответы `429` и `5xx` повторяются с экспоненциальной задержкой. Количество попыток задаётся `HTTP_MAX_RETRIES`. Если страница так и не ответила, проверка этого товара завершается ошибкой, а остальные товары продолжают обрабатываться.

Планировщик встроен в процесс API и рассчитан на один экземпляр приложения. При запуске нескольких воркеров его нужно вынести в отдельный процесс или защитить распределённой блокировкой.

## Ограничения

- Крупные маркетплейсы могут отдавать капчу или страницу без цены. Для них надёжнее официальный API.
- Scheduler работает внутри API-процесса и не предназначен для горизонтального масштабирования без доработки.
- Уведомления при достижении целевой цены не отправляются: поле хранится для дальнейшего развития.
- Парсер ориентирован на стандартную разметку карточек товаров и не использует браузер для исполнения JavaScript.
