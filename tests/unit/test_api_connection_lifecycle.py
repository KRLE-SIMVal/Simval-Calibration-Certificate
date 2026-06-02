import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from app.backend.api.app import create_app
from app.backend.auth.permissions import Role
from app.backend.auth.users import UserAccount, UserSession
from app.backend.persistence.sqlite import (
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    initialize_schema,
)
from tests.unit.test_api_app import _api_request


def test_api_connection_provider_is_opened_and_closed_per_request():
    opened = 0
    closed = 0

    @contextmanager
    def connection_provider():
        nonlocal opened, closed
        opened += 1
        connection = sqlite3.connect(":memory:")
        initialize_schema(connection)
        SQLiteUserAccountRepository(connection).add(_user())
        SQLiteUserSessionRepository(connection).add(_session())
        try:
            yield connection
        finally:
            connection.close()
            closed += 1

    response = _api_request(
        create_app(
            connection_provider=connection_provider,
            clock=_fixed_now,
        ),
        "GET",
        "/me",
        headers={"X-Session-Id": "session-001"},
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == "user-001"
    assert opened == 1
    assert closed == 1


def _fixed_now() -> datetime:
    return datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)


def _user() -> UserAccount:
    return UserAccount(
        id="user-001",
        display_name="Operator User",
        email="operator@example.com",
        roles=(Role.OPERATOR,),
        created_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
    )


def _session() -> UserSession:
    return UserSession(
        id="session-001",
        user_id="user-001",
        issued_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
    )
