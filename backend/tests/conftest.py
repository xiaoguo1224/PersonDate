from __future__ import annotations

# MUST be first: override DATABASE_URL before any app imports
# ruff: noqa: E402, I001
import os

TEST_DB_NAME = f"schedule_agent_test_{os.getpid()}"
DB_URL = f"postgresql+psycopg://postgres:postgres@localhost:5432/{TEST_DB_NAME}"
ADMIN_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"

os.environ["DATABASE_URL"] = DB_URL

from collections.abc import Generator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.routes import api_router
from app.core.config import get_settings
from app.schemas.auth import LoginRequest
from app.schemas.setup import OwnerInitRequest
from app.services.auth_service import AuthService
from app.services.setup_service import SetupService

def _create_test_database() -> None:
    admin_engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE datname = :db_name AND pid <> pg_backend_pid()"
            ),
            {"db_name": TEST_DB_NAME},
        )
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    admin_engine.dispose()


def _drop_test_database() -> None:
    admin_engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE datname = :db_name AND pid <> pg_backend_pid()"
            ),
            {"db_name": TEST_DB_NAME},
        )
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
    admin_engine.dispose()


def _run_migrations() -> None:
    """Create all tables from model definitions.

    Uses Base.metadata.create_all directly instead of alembic upgrade
    because the migration chain has a pre-existing issue: 0001 uses
    create_all (which creates columns from current models) and 0002 tries
    to add_column for columns that already exist.

    For test/scratch databases this is the correct approach - there is no
    legacy data to migrate.
    """
    from app.db.base import Base

    engine = create_engine(DB_URL, future=True)
    Base.metadata.create_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _test_db() -> Generator[None, None, None]:
    _create_test_database()
    _run_migrations()
    yield
    _drop_test_database()


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(DB_URL, future=True)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, autoflush=False, autocommit=False)
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, trans) -> None:  # noqa: ANN001
        nonlocal nested
        if trans.nested and not getattr(trans.parent, "nested", False):
            if connection.closed:
                return
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        if nested.is_active:
            nested.rollback()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture()
def app(db_session: Session) -> FastAPI:
    _app = FastAPI()
    _app.include_router(api_router)

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    _app.dependency_overrides[get_db] = _override_get_db
    return _app


@pytest.fixture()
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def owner(db_session: Session) -> Any:
    setup = SetupService(db_session)
    o = setup.create_owner(
        OwnerInitRequest(display_name="主用户", email="owner@example.com")
    )
    db_session.commit()
    db_session.refresh(o)
    return o


@pytest.fixture()
def admin_token(owner: Any, db_session: Session) -> str:
    settings = get_settings()
    auth = AuthService(db_session)
    _, token, _ = auth.login(
        LoginRequest(username="admin", password=settings.admin_password)
    )
    db_session.commit()
    return token


@pytest.fixture()
def member(db_session: Session) -> Any:
    from app.services.user_service import UserService

    m = UserService(db_session).create_user(
        username="member1",
        password="member123",
        role="member",
        display_name="成员一号",
    )
    db_session.commit()
    db_session.refresh(m)
    return m


@pytest.fixture()
def member_token(member: Any, db_session: Session) -> str:
    auth = AuthService(db_session)
    _, token, _ = auth.login(LoginRequest(username="member1", password="member123"))
    db_session.commit()
    return token


from app.agent.graph import SchedulePlanningGraph  # noqa: E402


@pytest.fixture()
def graph(db_session: Session) -> SchedulePlanningGraph:
    return SchedulePlanningGraph(db_session)
