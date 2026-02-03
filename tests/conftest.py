"""Shared test fixtures.

Uses SQLite in-memory with StaticPool so all sessions share one database.
Patches Redis so tests don't need a running Redis instance.
"""

import pytest
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# StaticPool ensures all connections share the same in-memory SQLite database
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)

# Patch database module BEFORE app imports use engine/SessionLocal
import src.core.database as db_module

db_module.engine = TEST_ENGINE
db_module.SessionLocal = TestSession

from src.core.database import Base, get_db
from src.core.models import Tenant  # noqa: F401 — registers tables
from src.main import app


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_tenant(db):
    tenant = Tenant(
        name="Test Tenant",
        api_key="test-api-key",
        rate_limit=100,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


@pytest.fixture
def mock_redis():
    """Patch redis_client in both completions and rate_limiter modules."""
    mock = AsyncMock()
    mock.check_rate_limit = AsyncMock(return_value=(True, 99))
    mock.get_cache = AsyncMock(return_value=None)
    mock.set_cache = AsyncMock()
    mock.generate_cache_key = lambda *a: "test-cache-key"

    with patch("src.api.completions.redis_client", mock), \
         patch("src.middleware.rate_limiter.redis_client", mock):
        yield mock


@pytest.fixture
def client():
    with patch("src.main.redis_client") as mock_rc:
        mock_rc.connect = AsyncMock()
        mock_rc.disconnect = AsyncMock()
        from fastapi.testclient import TestClient

        with TestClient(app) as c:
            yield c
