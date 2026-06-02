import sqlite3
from datetime import datetime, timezone

import pytest

from app.backend.audit.events import AuditAction
from app.backend.auth.permissions import Role
from app.backend.auth.users import UserAccount, UserSession
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    initialize_schema,
)
from app.backend.services.authentication import AuthenticationServiceError
from app.backend.services.user_management import (
    UserManagementServiceError,
    change_user_roles_for_session,
    create_user_account_for_session,
    deactivate_user_account_for_session,
    revoke_user_session_for_session,
)


def test_create_user_account_for_session_requires_admin_and_audits_creation():
    connection = _connection_with_admin()
    new_user = UserAccount(
        id="operator-002",
        display_name="Second Operator",
        email="operator2@example.com",
        roles=(Role.OPERATOR,),
        created_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
    )

    result = create_user_account_for_session(
        connection=connection,
        session_id="admin-session",
        user=new_user,
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
    )

    assert result.user == new_user
    assert result.audit_event_id == 1
    assert result.audit_event.action is AuditAction.USER_ACCOUNT_CREATED
    assert result.audit_event.user_id == "admin-001"
    assert result.audit_event.new_value == {
        "active": True,
        "email": "operator2@example.com",
        "roles": ["operator"],
    }
    assert SQLiteUserAccountRepository(connection).get("operator-002") == new_user
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "user_account",
        "operator-002",
    ) == (result.audit_event,)


def test_create_user_account_for_session_rejects_non_admin_before_write():
    connection = _connection_with_admin(actor_roles=(Role.OPERATOR,))

    with pytest.raises(AuthenticationServiceError):
        create_user_account_for_session(
            connection=connection,
            session_id="admin-session",
            user=UserAccount(
                id="operator-002",
                display_name="Second Operator",
                email="operator2@example.com",
                roles=(Role.OPERATOR,),
                created_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
            ),
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
        )

    assert SQLiteUserAccountRepository(connection).list_active() == (_admin_user((Role.OPERATOR,)),)
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "user_account",
        "operator-002",
    ) == ()


def test_change_user_roles_for_session_records_previous_and_new_roles():
    connection = _connection_with_admin()
    SQLiteUserAccountRepository(connection).add(_operator_user())

    result = change_user_roles_for_session(
        connection=connection,
        session_id="admin-session",
        target_user_id="operator-001",
        roles=(Role.OPERATOR, Role.TECHNICAL_REVIEWER),
        reason="Operator now performs technical review.",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 10, 5, tzinfo=timezone.utc),
    )

    assert result.user.roles == (Role.OPERATOR, Role.TECHNICAL_REVIEWER)
    assert result.audit_event.action is AuditAction.USER_ACCOUNT_ROLES_CHANGED
    assert result.audit_event.previous_value == {"roles": ["operator"]}
    assert result.audit_event.new_value == {
        "roles": ["operator", "technical_reviewer"]
    }
    assert result.audit_event.reason == "Operator now performs technical review."
    assert SQLiteUserAccountRepository(connection).get("operator-001").roles == (
        Role.OPERATOR,
        Role.TECHNICAL_REVIEWER,
    )


def test_deactivate_user_account_for_session_records_reason_and_active_state():
    connection = _connection_with_admin()
    SQLiteUserAccountRepository(connection).add(_operator_user())

    result = deactivate_user_account_for_session(
        connection=connection,
        session_id="admin-session",
        target_user_id="operator-001",
        reason="User left SIMVal.",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 10, 10, tzinfo=timezone.utc),
    )

    assert result.user.active is False
    assert result.audit_event.action is AuditAction.USER_ACCOUNT_DEACTIVATED
    assert result.audit_event.previous_value == {"active": True}
    assert result.audit_event.new_value == {"active": False}
    assert result.audit_event.reason == "User left SIMVal."
    assert SQLiteUserAccountRepository(connection).get("operator-001").active is False


def test_deactivate_user_account_for_session_rejects_blank_reason():
    connection = _connection_with_admin()
    SQLiteUserAccountRepository(connection).add(_operator_user())

    with pytest.raises(UserManagementServiceError):
        deactivate_user_account_for_session(
            connection=connection,
            session_id="admin-session",
            target_user_id="operator-001",
            reason=" ",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 10, 10, tzinfo=timezone.utc),
        )

    assert SQLiteUserAccountRepository(connection).get("operator-001").active is True
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "user_account",
        "operator-001",
    ) == ()


def test_revoke_user_session_for_session_records_session_audit_event():
    connection = _connection_with_admin()
    SQLiteUserAccountRepository(connection).add(_operator_user())
    SQLiteUserSessionRepository(connection).add(_operator_session())

    result = revoke_user_session_for_session(
        connection=connection,
        session_id="admin-session",
        target_session_id="operator-session",
        reason="Lost workstation.",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 10, 15, tzinfo=timezone.utc),
    )

    assert result.session.revoked_at == datetime(
        2026,
        6,
        1,
        10,
        15,
        tzinfo=timezone.utc,
    )
    assert result.audit_event.action is AuditAction.USER_SESSION_REVOKED
    assert result.audit_event.previous_value == {"revoked_at": None}
    assert result.audit_event.new_value == {
        "revoked_at": "2026-06-01T10:15:00+00:00"
    }
    assert SQLiteUserSessionRepository(connection).get("operator-session").revoked_at
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "user_session",
        "operator-session",
    ) == (result.audit_event,)


def _connection_with_admin(
    *,
    actor_roles: tuple[Role, ...] = (Role.ADMIN,),
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteUserAccountRepository(connection).add(_admin_user(actor_roles))
    SQLiteUserSessionRepository(connection).add(_admin_session())
    return connection


def _admin_user(roles: tuple[Role, ...]) -> UserAccount:
    return UserAccount(
        id="admin-001",
        display_name="Admin User",
        email="admin@example.com",
        roles=roles,
        created_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
    )


def _admin_session() -> UserSession:
    return UserSession(
        id="admin-session",
        user_id="admin-001",
        issued_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
    )


def _operator_user() -> UserAccount:
    return UserAccount(
        id="operator-001",
        display_name="Operator User",
        email="operator@example.com",
        roles=(Role.OPERATOR,),
        created_at=datetime(2026, 6, 1, 8, 30, tzinfo=timezone.utc),
    )


def _operator_session() -> UserSession:
    return UserSession(
        id="operator-session",
        user_id="operator-001",
        issued_at=datetime(2026, 6, 1, 8, 30, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
    )
