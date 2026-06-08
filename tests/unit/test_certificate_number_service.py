import sqlite3
from datetime import datetime, timezone

import pytest

from app.backend.audit.events import AuditAction
from app.backend.auth.permissions import Role
from app.backend.auth.users import UserAccount, UserSession
from app.backend.persistence.sqlite import (
    PersistenceError,
    SQLiteAuditEventRepository,
    SQLiteCertificateNumberAllocator,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    initialize_schema,
)
from app.backend.services.authentication import AuthenticationServiceError
from app.backend.services.certificate_numbers import (
    allocate_certificate_number_for_session,
    create_certificate_number_sequence_for_session,
    retire_certificate_number_sequence_for_session,
)


def test_create_certificate_number_sequence_for_session_records_audit_evidence():
    connection = _connection_with_user()

    result = create_certificate_number_sequence_for_session(
        connection=connection,
        session_id="session-001",
        prefix="SIMVAL-CAL",
        next_value=1,
        software_version="app-0.1.0",
        timestamp=_fixed_now(),
    )

    assert result.prefix == "SIMVAL-CAL"
    assert result.next_value == 1
    assert result.status == "active"
    assert result.audit_event_id == 1
    assert result.audit_event.action is AuditAction.CERTIFICATE_NUMBER_SEQUENCE_CHANGED
    assert result.audit_event.user_id == "admin-001"
    assert result.audit_event.new_value == {
        "prefix": "SIMVAL-CAL",
        "next_value": 1,
        "status": "active",
    }
    assert SQLiteCertificateNumberAllocator(connection).next_value("SIMVAL-CAL") == 1
    assert SQLiteCertificateNumberAllocator(connection).status("SIMVAL-CAL") == (
        "active"
    )


def test_allocate_certificate_number_for_session_increments_and_audits():
    connection = _connection_with_user()
    SQLiteCertificateNumberAllocator(connection).create_sequence(
        prefix="SIMVAL-CAL",
        next_value=7,
    )

    result = allocate_certificate_number_for_session(
        connection=connection,
        session_id="session-001",
        prefix="SIMVAL-CAL",
        padding=4,
        software_version="app-0.1.0",
        timestamp=_fixed_now(),
    )

    assert result.certificate_number == "SIMVAL-CAL-0007"
    assert result.next_value_after == 8
    assert result.audit_event.action is AuditAction.CERTIFICATE_NUMBER_ALLOCATED
    assert result.audit_event.new_value == {
        "prefix": "SIMVAL-CAL",
        "certificate_number": "SIMVAL-CAL-0007",
        "next_value_after": 8,
    }
    assert SQLiteCertificateNumberAllocator(connection).next_value("SIMVAL-CAL") == 8


def test_retire_certificate_number_sequence_for_session_records_audit_evidence():
    connection = _connection_with_user()
    SQLiteCertificateNumberAllocator(connection).create_sequence(
        prefix="SIMVAL-CAL",
        next_value=7,
    )

    result = retire_certificate_number_sequence_for_session(
        connection=connection,
        session_id="session-001",
        prefix="SIMVAL-CAL",
        reason="Prefix replaced by new annual sequence.",
        software_version="app-0.1.0",
        timestamp=_fixed_now(),
    )

    assert result.prefix == "SIMVAL-CAL"
    assert result.next_value == 7
    assert result.previous_status == "active"
    assert result.status == "retired"
    assert result.audit_event_id == 1
    assert result.audit_event.action is (
        AuditAction.CERTIFICATE_NUMBER_SEQUENCE_RETIRED
    )
    assert result.audit_event.reason == "Prefix replaced by new annual sequence."
    assert result.audit_event.previous_value == {
        "prefix": "SIMVAL-CAL",
        "next_value": 7,
        "status": "active",
    }
    assert result.audit_event.new_value == {
        "prefix": "SIMVAL-CAL",
        "next_value": 7,
        "status": "retired",
    }
    allocator = SQLiteCertificateNumberAllocator(connection)
    assert allocator.status("SIMVAL-CAL") == "retired"
    assert allocator.next_value("SIMVAL-CAL") == 7
    with pytest.raises(PersistenceError, match="not active"):
        allocator.allocate_next(prefix="SIMVAL-CAL", padding=4)


def test_allocate_certificate_number_rejects_non_admin_before_increment_or_audit():
    connection = _connection_with_user(roles=(Role.OPERATOR,))
    SQLiteCertificateNumberAllocator(connection).create_sequence(
        prefix="SIMVAL-CAL",
        next_value=7,
    )

    with pytest.raises(AuthenticationServiceError):
        allocate_certificate_number_for_session(
            connection=connection,
            session_id="session-001",
            prefix="SIMVAL-CAL",
            padding=4,
            software_version="app-0.1.0",
            timestamp=_fixed_now(),
        )

    assert SQLiteCertificateNumberAllocator(connection).next_value("SIMVAL-CAL") == 7
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "certificate_number",
        "SIMVAL-CAL-0007",
    ) == ()


def _connection_with_user(
    *,
    roles: tuple[Role, ...] = (Role.ADMIN,),
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteUserAccountRepository(connection).add(_user(roles))
    SQLiteUserSessionRepository(connection).add(_session())
    return connection


def _user(roles: tuple[Role, ...]) -> UserAccount:
    return UserAccount(
        id="admin-001",
        display_name="Admin User",
        email="admin@example.com",
        roles=roles,
        created_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
    )


def _session() -> UserSession:
    return UserSession(
        id="session-001",
        user_id="admin-001",
        issued_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
    )


def _fixed_now() -> datetime:
    return datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc)
