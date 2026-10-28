"""SQLAlchemy engine and session factory."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import Settings


class Base(DeclarativeBase):
    """Declarative base shared by every table."""


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _ensure_sqlite_parent(url: str) -> None:
    if not url.startswith("sqlite:///"):
        return
    path = url.removeprefix("sqlite:///")
    if path == ":memory:" or path.startswith("file:"):
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def build_engine(database_url: str) -> Engine:
    """Create an engine. SQLite foreign keys are enabled on each connection."""
    _ensure_sqlite_parent(database_url)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args, future=True)
    if database_url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a session factory bound to `engine`."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True, expire_on_commit=False)


def init_database(engine: Engine) -> None:
    """Create tables that are not already present."""
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def session_scope(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Yield a session and always close it."""
    session = factory()
    try:
        yield session
    finally:
        session.close()


def bind_database(settings: Settings) -> tuple[Engine, sessionmaker[Session]]:
    """Create the engine, tables, and session factory for these settings."""
    engine = build_engine(settings.database_url)
    init_database(engine)
    return engine, build_session_factory(engine)
