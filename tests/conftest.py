"""pytest fixtures for OpenPROM"""

import pytest
from fastapi.testclient import TestClient
from openprom.api import app


@pytest.fixture
def client():
    """FastAPI TestClient fixture"""
    return TestClient(app)
