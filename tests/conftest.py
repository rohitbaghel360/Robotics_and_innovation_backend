import os

os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

import app.main as app_main  # noqa: E402
import app.modules.health.router as health_router  # noqa: E402
from app.main import create_app  # noqa: E402


async def _noop_create_tables() -> None:
    """Skip schema creation in tests (models target a MySQL-only schema)."""
    return None


@pytest.fixture
def client(monkeypatch):
    # The real models are bound to a MySQL `ri_web_auth` schema, so we never
    # touch a live database in CI. Skip table creation on startup...
    monkeypatch.setattr(app_main, "create_tables", _noop_create_tables)

    # ...and point the health/readiness probe at an in-memory SQLite engine so
    # `SELECT 1` succeeds without a running MySQL server.
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(health_router, "engine", test_engine)

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
