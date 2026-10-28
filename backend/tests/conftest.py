"""Shared API fixtures."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings_for_tests
from app.main import create_app

SAMPLE_PATH = Path(__file__).resolve().parents[1] / "app" / "sample_data" / "nimbus_launch.json"


@pytest.fixture
def sample_payload() -> dict:
    """Bundled conversation used by the API and the dashboard."""
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def client(tmp_path):
    """API client bound to a temporary SQLite database."""
    database = tmp_path / "recallflow.db"
    application = create_app(settings_for_tests(f"sqlite:///{database.as_posix()}"))
    with TestClient(application) as test_client:
        yield test_client
    application.state.engine.dispose()
