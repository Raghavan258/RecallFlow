"""Exceptions that are safe to show to API clients."""


class AppError(Exception):
    """Expected application failure with an HTTP status and public message."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ExtractionError(AppError):
    """The extractor failed or returned data that cannot be stored."""

    def __init__(self, detail: str, status_code: int = 422) -> None:
        super().__init__(status_code, detail)
