import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app.backend.audit.events import AuditAction
from app.backend.auth.entra import EntraTokenValidationError, VerifiedEntraToken
from app.backend.auth.permissions import Role
from app.backend.auth.users import UserAccount
from app.backend.persistence.sqlite import (
    RecordNotFoundError,
    SQLiteAuditEventRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    initialize_schema,
)
from app.backend.services.authentication import AuthenticationFailureError
from app.backend.services.entra_authentication import issue_entra_session


def test_issue_entra_session_stores_session_and_audit_evidence():
    connection = _connection_with_users(_user())
    verifier = _Verifier(
        VerifiedEntraToken(
            subject_id="entra-subject-001",
            tenant_id="tenant-001",
            email="operator@example.com",
            display_name="Operator User",
            expires_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        )
    )

    result = issue_entra_session(
        connection=connection,
        bearer_token="verified-token",
        token_verifier=verifier,
        session_id="entra-session-001",
        software_version="0.1.0",
        timestamp=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        max_session_duration=timedelta(hours=8),
    )

    assert result.user.id == "user-001"
    assert result.session.user_id == "user-001"
    assert result.session.expires_at == datetime(
        2026, 6, 1, 9, 0, tzinfo=timezone.utc
    )
    assert SQLiteUserSessionRepository(connection).get("entra-session-001") == (
        result.session
    )
    event = SQLiteAuditEventRepository(connection).list_for_entity(
        "user_session",
        "entra-session-001",
    )[0]
    assert event.action is AuditAction.USER_SESSION_CREATED
    assert event.user_id == "user-001"
    assert event.new_value == {
        "auth_provider": "entra_id_free",
        "entra_subject_id": "entra-subject-001",
        "entra_tenant_id": "tenant-001",
        "email": "operator@example.com",
        "expires_at": "2026-06-01T09:00:00+00:00",
    }


def test_issue_entra_session_limits_session_to_configured_duration():
    connection = _connection_with_users(_user())
    verifier = _Verifier(
        VerifiedEntraToken(
            subject_id="entra-subject-001",
            tenant_id="tenant-001",
            email="operator@example.com",
            display_name="Operator User",
            expires_at=datetime(2026, 6, 1, 18, 0, tzinfo=timezone.utc),
        )
    )

    result = issue_entra_session(
        connection=connection,
        bearer_token="verified-token",
        token_verifier=verifier,
        session_id="entra-session-001",
        software_version="0.1.0",
        timestamp=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        max_session_duration=timedelta(hours=2),
    )

    assert result.session.expires_at == datetime(
        2026, 6, 1, 10, 0, tzinfo=timezone.utc
    )


def test_issue_entra_session_rejects_unknown_local_user_before_writes():
    connection = _connection_with_users(_user())
    verifier = _Verifier(
        VerifiedEntraToken(
            subject_id="entra-subject-001",
            tenant_id="tenant-001",
            email="missing@example.com",
            display_name="Missing User",
            expires_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        )
    )

    with pytest.raises(AuthenticationFailureError):
        issue_entra_session(
            connection=connection,
            bearer_token="verified-token",
            token_verifier=verifier,
            session_id="entra-session-001",
            software_version="0.1.0",
            timestamp=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
            max_session_duration=timedelta(hours=8),
        )

    with pytest.raises(RecordNotFoundError):
        SQLiteUserSessionRepository(connection).get("entra-session-001")
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "user_session",
        "entra-session-001",
    ) == ()


def test_issue_entra_session_rejects_invalid_entra_token_before_writes():
    connection = _connection_with_users(_user())

    with pytest.raises(AuthenticationFailureError):
        issue_entra_session(
            connection=connection,
            bearer_token="invalid-token",
            token_verifier=_RejectingVerifier(),
            session_id="entra-session-001",
            software_version="0.1.0",
            timestamp=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
            max_session_duration=timedelta(hours=8),
        )

    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "user_session",
        "entra-session-001",
    ) == ()


def _connection_with_users(*users: UserAccount) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    repository = SQLiteUserAccountRepository(connection)
    for user in users:
        repository.add(user)
    return connection


def _user() -> UserAccount:
    return UserAccount(
        id="user-001",
        display_name="Operator User",
        email="operator@example.com",
        roles=(Role.OPERATOR,),
        created_at=datetime(2026, 6, 1, 7, 0, tzinfo=timezone.utc),
    )


class _Verifier:
    def __init__(self, token: VerifiedEntraToken) -> None:
        self._token = token

    def verify(self, token: str, *, timestamp: datetime) -> VerifiedEntraToken:
        assert token == "verified-token"
        assert timestamp == datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)
        return self._token


class _RejectingVerifier:
    def verify(self, token: str, *, timestamp: datetime) -> VerifiedEntraToken:
        raise EntraTokenValidationError("Invalid token.")
