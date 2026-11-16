class AppError(Exception):
    status_code = 400

    def __init__(self, detail: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.headers = headers


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class AuthenticationError(AppError):
    status_code = 401

    def __init__(self, detail: str = "Не удалось проверить учетные данные") -> None:
        super().__init__(detail, headers={"WWW-Authenticate": "Bearer"})


class InvalidUrlError(AppError):
    status_code = 422

    def __init__(self, detail: str = "URL не подходит для отслеживания") -> None:
        super().__init__(detail)


class PriceFetchError(AppError):
    status_code = 502

    def __init__(self, detail: str = "Не удалось получить цену со страницы") -> None:
        super().__init__(detail)
