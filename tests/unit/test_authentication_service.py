import sqlite3
from datetime import datetime, timezone

import pytest

from app.backend.auth.permissions import Action, Role
from app.backend.auth.users import UserAccount, UserSession
from app.backend.persistence.sqlite import (
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    initialize_schema,
)
from app.backend.services.authentication import (
    AuthenticationServiceError,
    resolve_actor_for_action,
)


def _connection_with_user_and_session(
    *,
    user: UserAccount | None = None,
    session: UserSession | None = None,
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteUserAccountRepository(connection).add(user or _operator())
    SQLiteUserSessionRepository(connection).add(session or _active_session())
    return connection


def test_resolve_actor_for_action_returns_authorized_active_actor():
    connection = _connection_with_user_and_session()

    actor = resolve_actor_for_action(
        connection=connection,
        session_id="session-001",
        action=Action.RUN_CALCULATION,
        timestamp=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
    )

    assert actor.user_id == "user-001"
    assert actor.display_name == "Operator User"
    assert actor.roles == (Role.OPERATOR,)


def test_resolve_actor_for_action_rejects_expired_session():
    connection = _connection_with_user_and_session()

    with pytest.raises(AuthenticationServiceError):
        resolve_actor_for_action(
            connection=connection,
            session_id="session-001",
            action=Action.RUN_CALCULATION,
            timestamp=datetime(2026, 6, 1, 16, 1, tzinfo=timezone.utc),
        )


def test_resolve_actor_for_action_rejects_revoked_session():
    connection = _connection_with_user_and_session(
        session=UserSession(
            id="session-001",
            user_id="user-001",
            issued_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
            expires_at=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
            revoked_at=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
        )
    )

    with pytest.raises(AuthenticationServiceError):
        resolve_actor_for_action(
            connection=connection,
            session_id="session-001",
            action=Action.RUN_CALCULATION,
            timestamp=datetime(2026, 6, 1, 11, 0, tzinfo=timezone.utc),
        )


def test_resolve_actor_for_action_rejects_inactive_user():
    inactive_user = UserAccount(
        id="user-001",
        display_name="Inactive User",
        email="inactive@example.com",
        roles=(Role.ADMIN,),
        active=False,
        created_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
    )
    connection = _connection_with_user_and_session(user=inactive_user)

    with pytest.raises(AuthenticationServiceError):
        resolve_actor_for_action(
            connection=connection,
            session_id="session-001",
            action=Action.MANAGE_USERS_AND_ROLES,
            timestamp=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        )


def test_resolve_actor_for_action_rejects_unauthorized_action():
    connection = _connection_with_user_and_session()

    with pytest.raises(AuthenticationServiceError):
        resolve_actor_for_action(
            connection=connection,
            session_id="session-001",
            action=Action.RELEASE_CERTIFICATE,
            timestamp=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        )


def test_resolve_actor_for_action_rejects_naive_timestamp():
    connection = _connection_with_user_and_session()

    with pytest.raises(AuthenticationServiceError):
        resolve_actor_for_action(
            connection=connection,
            session_id="session-001",
            action=Action.RUN_CALCULATION,
            timestamp=datetime(2026, 6, 1, 9, 0),
        )


def _operator() -> UserAccount:
    return UserAccount(
        id="user-001",
        display_name="Operator User",
        email="operator@example.com",
        roles=(Role.OPERATOR,),
        active=True,
        created_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
    )


def _active_session() -> UserSession:
    return UserSession(
        id="session-001",
        user_id="user-001",
        issued_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
    )
