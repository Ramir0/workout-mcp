"""Pytest fixtures and configuration."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, SessionTransaction, sessionmaker

from workout_mcp.config import settings
from workout_mcp.models import Base


@pytest.fixture(autouse=True)
def _reset_webhook_secret() -> Generator[None]:
    """Ensure HEVY_WEBHOOK_SECRET is unset during tests so the signature middleware is bypassed."""
    with patch.object(settings, "hevy_webhook_secret", None):
        yield


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine]:
    """Create a test database engine and schema (once per session)."""
    engine = create_engine(settings.test_database_url)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session]:
    """Yield a database session with automatic transaction rollback."""
    connection = db_engine.connect()
    transaction = connection.begin()

    # Bind the session to the connection (not the engine)
    session = sessionmaker(bind=connection)()

    # Prevent the session from committing externally
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def end_savepoint(session: Session, transaction: SessionTransaction) -> None:
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient]:
    """Create a TestClient with the test database session injected."""
    from workout_mcp.api import app, get_db

    def override_get_db() -> Generator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]
