"""Runtime configuration loaded from the environment."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
SQLITE_RELATIVE_PREFIX = "sqlite:///./"


class Settings(BaseSettings):
    """Application settings. Constructor arguments override environment values."""

    database_url: str = "sqlite:///./data/recallflow.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    extraction_provider: str = "baseline"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 60.0

    model_config = SettingsConfigDict(
        env_file=(REPOSITORY_ROOT / ".env", BACKEND_ROOT / ".env"),
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """Browser origins allowed to call the API."""
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


def resolve_sqlite_url(url: str) -> str:
    """Anchor relative SQLite paths at the backend directory."""
    if not url.startswith(SQLITE_RELATIVE_PREFIX):
        return url
    relative = url[len(SQLITE_RELATIVE_PREFIX) :]
    absolute = (BACKEND_ROOT / relative).resolve()
    return "sqlite:///" + absolute.as_posix()


@lru_cache
def get_settings() -> Settings:
    """Return cached settings for the process."""
    settings = Settings()
    return settings.model_copy(update={"database_url": resolve_sqlite_url(settings.database_url)})


def settings_for_tests(database_url: str) -> Settings:
    """Build settings that ignore developer environment files."""
    settings = Settings(
        _env_file=None,
        database_url=database_url,
        extraction_provider="baseline",
        llm_api_key="",
    )
    return settings.model_copy(update={"database_url": resolve_sqlite_url(settings.database_url)})
