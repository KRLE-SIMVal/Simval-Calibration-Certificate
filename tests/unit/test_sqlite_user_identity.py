import sqlite3
from datetime import datetime, timezone

import pytest

from app.backend.auth.permissions import Role
from app.backend.auth.users import UserAccount, UserSession
from app.backend.persistence.sqlite import (
    PersistenceError,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    initialize_schema,
)


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    return connection


def test_sqlite_user_account_repository_round_trips_user_identity():
    connection = _connection()
    repository = SQLiteUserAccountRepository(connection)
    user = _user()

    repository.add(user)

    assert repository.get("user-001") == user
    assert repository.list_active() == (user,)


def test_sqlite_user_account_repository_rejects_duplicate_email():
    connection = _connection()
    repository = SQLiteUserAccountRepository(connection)
    repository.add(_user())

    with pytest.raises(PersistenceError):
        repository.add(
            UserAccount(
                id="user-002",
                display_name="Duplicate Email",
                email="operator@example.com",
                roles=(Role.TECHNICAL_REVIEWER,),
                created_at=datetime(2026, 6, 1, 8, 1, tzinfo=timezone.utc),
            )
        )


def test_sqlite_user_account_repository_lists_only_active_users():
    connection = _connection()
    repository = SQLiteUserAccountRepository(connection)
    active = _user()
    inactive = UserAccount(
        id="user-002",
        display_name="Inactive User",
        email="inactive@example.com",
        roles=(Role.ADMIN,),
        active=False,
        created_at=datetime(2026, 6, 1, 8, 1, tzinfo=timezone.utc),
    )

    repository.add(inactive)
    repository.add(active)

    assert repository.list_active() == (active,)


def test_sqlite_user_session_repository_round_trips_session():
    connection = _connection()
    SQLiteUserAccountRepository(connection).add(_user())
    repository = SQLiteUserSessionRepository(connection)
    session = _session()

    repository.add(session)

    assert repository.get("session-001") == session


def test_sqlite_user_session_repository_rejects_unknown_user():
    connection = _connection()
    repository = SQLiteUserSessionRepository(connection)

    with pytest.raises(PersistenceError):
        repository.add(_session())


def test_sqlite_user_session_repository_revokes_session():
    connection = _connection()
    SQLiteUserAccountRepository(connection).add(_user())
    repository = SQLiteUserSessionRepository(connection)
    repository.add(_session())
    revoked_at = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    revoked = repository.revoke(session_id="session-001", revoked_at=revoked_at)

    assert revoked.revoked_at == revoked_at
    assert repository.get("session-001").revoked_at == revoked_at


def test_sqlite_user_session_repository_rejects_double_revocation():
    connection = _connection()
    SQLiteUserAccountRepository(connection).add(_user())
    repository = SQLiteUserSessionRepository(connection)
    repository.add(_session())
    repository.revoke(
        session_id="session-001",
        revoked_at=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(PersistenceError):
        repository.revoke(
            session_id="session-001",
            revoked_at=datetime(2026, 6, 1, 12, 1, tzinfo=timezone.utc),
        )


def _user() -> UserAccount:
    return UserAccount(
        id="user-001",
        display_name="Operator User",
        email="operator@example.com",
        roles=(Role.OPERATOR,),
        active=True,
        signature_label="OPR",
        created_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
    )


def _session() -> UserSession:
    return UserSession(
        id="session-001",
        user_id="user-001",
        issued_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
    )
