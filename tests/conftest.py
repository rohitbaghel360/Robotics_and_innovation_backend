import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app.config import Environment, get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    os.environ["ENVIRONMENT"] = Environment.TESTING.value
    os.environ["DEBUG"] = "true"
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
