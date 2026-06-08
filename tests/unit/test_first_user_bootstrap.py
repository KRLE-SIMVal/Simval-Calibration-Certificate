import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app.backend.audit.events import AuditAction
from app.backend.auth.permissions import Role
from app.backend.auth.users import UserAccount
from app.backend.operations.user_bootstrap import (
    FirstUserBootstrapError,
    bootstrap_first_user,
)
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
    initialize_schema,
)
from scripts.maintenance.bootstrap_first_user import main as bootstrap_cli_main


def test_bootstrap_first_user_creates_admin_session_and_audit_evidence():
    connection = _connection()
    timestamp = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    user = _admin_user(created_at=timestamp)

    evidence = bootstrap_first_user(
        connection=connection,
        user=user,
        software_version="app-0.1.0",
        timestamp=timestamp,
        session_id="local-session-001",
        session_expires_at=timestamp + timedelta(hours=12),
    )

    assert evidence.user == user
    assert evidence.session is not None
    assert evidence.session.id == "local-session-001"
    assert evidence.audit_event_id == 1
    assert evidence.audit_event.action is AuditAction.USER_ACCOUNT_CREATED
    assert evidence.audit_event.user_id == "system-bootstrap"
    assert evidence.audit_event.new_value == {
        "active": True,
        "bootstrap": True,
        "email": "krle@simval.dk",
        "roles": ["admin"],
        "session_issued": True,
    }
    assert SQLiteUserAccountRepository(connection).get("krle-simval") == user
    assert SQLiteUserSessionRepository(connection).get("local-session-001").user_id == (
        "krle-simval"
    )
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "user_account",
        "krle-simval",
    ) == (evidence.audit_event,)


def test_bootstrap_first_user_rejects_existing_user_without_writing_new_evidence():
    connection = _connection()
    timestamp = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)
    SQLiteUserAccountRepository(connection).add(_admin_user(created_at=timestamp))

    with pytest.raises(FirstUserBootstrapError, match="before any users exist"):
        bootstrap_first_user(
            connection=connection,
            user=UserAccount(
                id="second-admin",
                display_name="Second Admin",
                email="second@example.com",
                roles=(Role.ADMIN,),
                created_at=timestamp,
            ),
            software_version="app-0.1.0",
            timestamp=timestamp,
        )

    assert SQLiteUserAccountRepository(connection).list_active() == (
        _admin_user(created_at=timestamp),
    )
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "user_account",
        "second-admin",
    ) == ()


def test_bootstrap_first_user_requires_session_id_and_expiry_together():
    with pytest.raises(FirstUserBootstrapError, match="supplied together"):
        bootstrap_first_user(
            connection=_connection(),
            user=_admin_user(),
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc),
            session_id="local-session-001",
        )


def test_bootstrap_first_user_rejects_naive_timestamp():
    with pytest.raises(FirstUserBootstrapError, match="timezone-aware"):
        bootstrap_first_user(
            connection=_connection(),
            user=_admin_user(),
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 8, 12, 0),
        )


def test_bootstrap_first_user_cli_writes_json_evidence_and_session(tmp_path):
    database_path = tmp_path / "simval.sqlite3"
    evidence_path = tmp_path / "first-user-evidence.json"

    result = bootstrap_cli_main(
        [
            "--database-path",
            str(database_path),
            "--user-id",
            "krle-simval",
            "--display-name",
            "KRLE-SIMVal",
            "--email",
            "krle@simval.dk",
            "--role",
            "admin",
            "--software-version",
            "app-0.1.0",
            "--issue-session",
            "--session-id",
            "local-session-001",
            "--evidence-output",
            str(evidence_path),
        ]
    )

    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["user"]["id"] == "krle-simval"
    assert payload["user"]["roles"] == ["admin"]
    assert payload["session"]["id"] == "local-session-001"
    with sqlite3.connect(database_path) as connection:
        initialize_schema(connection)
        assert SQLiteUserAccountRepository(connection).get("krle-simval").email == (
            "krle@simval.dk"
        )
        assert SQLiteUserSessionRepository(connection).get("local-session-001").user_id == (
            "krle-simval"
        )


def test_bootstrap_first_user_cli_rejects_nonpositive_session_hours(tmp_path):
    with pytest.raises(SystemExit, match="session-hours"):
        bootstrap_cli_main(
            [
                "--database-path",
                str(tmp_path / "simval.sqlite3"),
                "--user-id",
                "krle-simval",
                "--display-name",
                "KRLE-SIMVal",
                "--email",
                "krle@simval.dk",
                "--software-version",
                "app-0.1.0",
                "--issue-session",
                "--session-hours",
                "0",
            ]
        )


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    return connection


def _admin_user(
    *,
    created_at: datetime = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc),
) -> UserAccount:
    return UserAccount(
        id="krle-simval",
        display_name="KRLE-SIMVal",
        email="krle@simval.dk",
        roles=(Role.ADMIN,),
        created_at=created_at,
    )

