"""pytest fixtures for OpenPROM"""

import pytest
from fastapi.testclient import TestClient
from openprom.api import app
from openprom.infrastructure.database import get_db_manager


@pytest.fixture(scope="session", autouse=True)
def _ensure_db_tables():
    """Ensure database tables exist before any test runs."""
    try:
        get_db_manager().create_tables()
    except Exception:
        pass
    yield


@pytest.fixture
def client():
    """FastAPI TestClient fixture"""
    return TestClient(app)
