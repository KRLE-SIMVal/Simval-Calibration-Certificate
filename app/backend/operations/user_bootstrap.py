"""Controlled first-user bootstrap for a new SIMVal database."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import sqlite3

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.auth.permissions import Role
from app.backend.auth.users import UserAccount, UserSession
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
)


class FirstUserBootstrapError(ValueError):
    """Raised when first-user bootstrap is unsafe or invalid."""


@dataclass(frozen=True, slots=True)
class FirstUserBootstrapEvidence:
    user: UserAccount
    audit_event_id: int
    audit_event: AuditEvent
    session: UserSession | None = None

    def to_payload(self) -> dict:
        payload = {
            "user": {
                "id": self.user.id,
                "display_name": self.user.display_name,
                "email": self.user.email,
                "roles": [role.value for role in self.user.roles],
                "active": self.user.active,
                "signature_label": self.user.signature_label,
                "created_at": self.user.created_at.isoformat(),
            },
            "audit_event_id": self.audit_event_id,
            "audit_action": self.audit_event.action.value,
        }
        if self.session is not None:
            payload["session"] = {
                "id": self.session.id,
                "issued_at": self.session.issued_at.isoformat(),
                "expires_at": self.session.expires_at.isoformat(),
            }
        return payload


def bootstrap_first_user(
    *,
    connection: sqlite3.Connection,
    user: UserAccount,
    software_version: str,
    timestamp: datetime,
    session_id: str | None = None,
    session_expires_at: datetime | None = None,
) -> FirstUserBootstrapEvidence:
    """Create the first user only when no user accounts exist."""
    _require_text(software_version, "Software version")
    _require_timezone_aware(timestamp, "Bootstrap timestamp")
    if (session_id is None) != (session_expires_at is None):
        raise FirstUserBootstrapError(
            "Session id and session expiry must be supplied together."
        )
    if session_expires_at is not None:
        _require_timezone_aware(session_expires_at, "Bootstrap session expiry")
        if session_expires_at <= timestamp:
            raise FirstUserBootstrapError(
                "Bootstrap session expiry must be after bootstrap timestamp."
            )

    with connection:
        if _user_account_count(connection) != 0:
            raise FirstUserBootstrapError(
                "First-user bootstrap is allowed only before any users exist."
            )

        user_repository = SQLiteUserAccountRepository(connection, autocommit=False)
        session_repository = SQLiteUserSessionRepository(connection, autocommit=False)
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)

        user_repository.add(user)
        session: UserSession | None = None
        if session_id is not None and session_expires_at is not None:
            session = UserSession(
                id=session_id,
                user_id=user.id,
                issued_at=timestamp,
                expires_at=session_expires_at,
            )
            session_repository.add(session)

        audit_event = AuditEvent(
            entity_type="user_account",
            entity_id=user.id,
            action=AuditAction.USER_ACCOUNT_CREATED,
            user_id="system-bootstrap",
            timestamp=timestamp,
            new_value={
                "active": user.active,
                "bootstrap": True,
                "email": user.email,
                "roles": _role_values(user.roles),
                "session_issued": session is not None,
            },
            reason="Initial first-user bootstrap; allowed only on an empty user table.",
            software_version=software_version,
        )
        audit_event_id = audit_repository.append(audit_event)

    return FirstUserBootstrapEvidence(
        user=user,
        session=session,
        audit_event_id=audit_event_id,
        audit_event=audit_event,
    )


def _user_account_count(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) AS count FROM user_accounts").fetchone()
    return int(row["count"] if isinstance(row, sqlite3.Row) else row[0])


def _role_values(roles: tuple[Role, ...]) -> list[str]:
    if any(not isinstance(role, Role) for role in roles):
        raise FirstUserBootstrapError("User roles must be controlled Role values.")
    return [role.value for role in roles]


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise FirstUserBootstrapError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FirstUserBootstrapError(f"{field_name} must be timezone-aware.")

