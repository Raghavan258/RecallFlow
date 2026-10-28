"""FastAPI application entrypoint."""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import api_router, health_router
from app.config import Settings, get_settings, resolve_sqlite_url
from app.database import bind_database
from app.errors import AppError

logger = logging.getLogger("recallflow")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API, including tables for the configured database."""
    active = _activate(settings)
    engine, factory = bind_database(active)
    app = FastAPI(
        title="RecallFlow",
        version=__version__,
        summary="Topic-aware conversation memory.",
        description="Import a conversation, extract topics and memories, and explore the resulting graph.",
    )
    app.state.settings = active
    app.state.engine = engine
    app.state.session_factory = factory
    _add_cors(app, active)
    app.include_router(health_router)
    app.include_router(api_router, prefix="/api")
    _add_handlers(app)
    return app


def _activate(settings: Settings | None) -> Settings:
    active = settings or get_settings()
    return active.model_copy(update={"database_url": resolve_sqlite_url(active.database_url)})


def _add_cors(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _add_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(HTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unexpected_error)


def _app_error(_request, exc: Exception) -> JSONResponse:
    error = exc if isinstance(exc, AppError) else AppError(500, "Internal server error")
    return JSONResponse(status_code=error.status_code, content={"detail": error.detail})


def _http_error(_request, exc: Exception) -> JSONResponse:
    status = exc.status_code if isinstance(exc, HTTPException) else 500
    detail = exc.detail if isinstance(exc, HTTPException) and isinstance(exc.detail, str) else "Request failed."
    return JSONResponse(status_code=status, content={"detail": detail})


def _validation_error(_request, exc: Exception) -> JSONResponse:
    message = "Request validation failed."
    if isinstance(exc, RequestValidationError) and exc.errors():
        message = _validation_message(exc.errors()[0])
    return JSONResponse(status_code=422, content={"detail": message})


def _validation_message(error: dict) -> str:
    location = [str(item) for item in error.get("loc", []) if item != "body"]
    prefix = ".".join(location)
    text = str(error.get("msg", "Invalid value."))
    if prefix:
        return f"{prefix}: {text}"
    return text


def _unexpected_error(_request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app = create_app()
