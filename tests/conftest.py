"""Pytest fixtures and configuration."""

from collections.abc import Generator

import pytest
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, SessionTransaction, sessionmaker

from workout_mcp.config import TEST_DATABASE_URL
from workout_mcp.models import Base


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine]:
    """Create a test database engine and schema (once per session)."""
    engine = create_engine(TEST_DATABASE_URL)
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
