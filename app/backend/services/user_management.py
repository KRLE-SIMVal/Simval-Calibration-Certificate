"""Audited user and session management services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import sqlite3

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.auth.permissions import Action, Role
from app.backend.auth.users import UserAccount, UserSession
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
)
from app.backend.services.authentication import resolve_actor_for_action


class UserManagementServiceError(ValueError):
    """Raised when audited user-management inputs are incomplete or unsafe."""


@dataclass(frozen=True, slots=True)
class UserAccountManagementResult:
    user: UserAccount
    audit_event_id: int
    audit_event: AuditEvent


@dataclass(frozen=True, slots=True)
class UserSessionManagementResult:
    session: UserSession
    audit_event_id: int
    audit_event: AuditEvent


def create_user_account_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    user: UserAccount,
    software_version: str,
    timestamp: datetime,
) -> UserAccountManagementResult:
    """Create a user account after resolving an authorized admin actor."""
    actor = _resolve_admin_actor(
        connection=connection,
        session_id=session_id,
        timestamp=timestamp,
    )
    _require_text(software_version, "Software version")
    _require_timezone_aware(timestamp, "User-management timestamp")

    with connection:
        user_repository = SQLiteUserAccountRepository(connection, autocommit=False)
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)

        user_repository.add(user)
        audit_event = AuditEvent(
            entity_type="user_account",
            entity_id=user.id,
            action=AuditAction.USER_ACCOUNT_CREATED,
            user_id=actor.user_id,
            timestamp=timestamp,
            new_value={
                "active": user.active,
                "email": user.email,
                "roles": _role_values(user.roles),
            },
            software_version=software_version,
        )
        audit_event_id = audit_repository.append(audit_event)

    return UserAccountManagementResult(
        user=user,
        audit_event_id=audit_event_id,
        audit_event=audit_event,
    )


def change_user_roles_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    target_user_id: str,
    roles: tuple[Role, ...],
    reason: str,
    software_version: str,
    timestamp: datetime,
) -> UserAccountManagementResult:
    """Replace a user's roles with audited previous/new role evidence."""
    actor = _resolve_admin_actor(
        connection=connection,
        session_id=session_id,
        timestamp=timestamp,
    )
    _validate_reasoned_user_change(
        target_user_id=target_user_id,
        reason=reason,
        software_version=software_version,
        timestamp=timestamp,
    )

    with connection:
        user_repository = SQLiteUserAccountRepository(connection, autocommit=False)
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)

        previous = user_repository.get(target_user_id)
        updated = user_repository.update_roles(user_id=target_user_id, roles=roles)
        audit_event = AuditEvent(
            entity_type="user_account",
            entity_id=target_user_id,
            action=AuditAction.USER_ACCOUNT_ROLES_CHANGED,
            user_id=actor.user_id,
            timestamp=timestamp,
            previous_value={"roles": _role_values(previous.roles)},
            new_value={"roles": _role_values(updated.roles)},
            reason=reason,
            software_version=software_version,
        )
        audit_event_id = audit_repository.append(audit_event)

    return UserAccountManagementResult(
        user=updated,
        audit_event_id=audit_event_id,
        audit_event=audit_event,
    )


def deactivate_user_account_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    target_user_id: str,
    reason: str,
    software_version: str,
    timestamp: datetime,
) -> UserAccountManagementResult:
    """Deactivate a user account with audited reason and state change."""
    actor = _resolve_admin_actor(
        connection=connection,
        session_id=session_id,
        timestamp=timestamp,
    )
    _validate_reasoned_user_change(
        target_user_id=target_user_id,
        reason=reason,
        software_version=software_version,
        timestamp=timestamp,
    )

    with connection:
        user_repository = SQLiteUserAccountRepository(connection, autocommit=False)
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)

        previous = user_repository.get(target_user_id)
        updated = user_repository.set_active(user_id=target_user_id, active=False)
        audit_event = AuditEvent(
            entity_type="user_account",
            entity_id=target_user_id,
            action=AuditAction.USER_ACCOUNT_DEACTIVATED,
            user_id=actor.user_id,
            timestamp=timestamp,
            previous_value={"active": previous.active},
            new_value={"active": updated.active},
            reason=reason,
            software_version=software_version,
        )
        audit_event_id = audit_repository.append(audit_event)

    return UserAccountManagementResult(
        user=updated,
        audit_event_id=audit_event_id,
        audit_event=audit_event,
    )


def revoke_user_session_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    target_session_id: str,
    reason: str,
    software_version: str,
    timestamp: datetime,
) -> UserSessionManagementResult:
    """Revoke a user session with audited previous/new revocation evidence."""
    actor = _resolve_admin_actor(
        connection=connection,
        session_id=session_id,
        timestamp=timestamp,
    )
    _require_text(target_session_id, "Target session id")
    _require_text(reason, "User-management reason")
    _require_text(software_version, "Software version")
    _require_timezone_aware(timestamp, "User-management timestamp")

    with connection:
        session_repository = SQLiteUserSessionRepository(connection, autocommit=False)
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)

        previous = session_repository.get(target_session_id)
        updated = session_repository.revoke(
            session_id=target_session_id,
            revoked_at=timestamp,
        )
        audit_event = AuditEvent(
            entity_type="user_session",
            entity_id=target_session_id,
            action=AuditAction.USER_SESSION_REVOKED,
            user_id=actor.user_id,
            timestamp=timestamp,
            previous_value={
                "revoked_at": _optional_datetime_to_text(previous.revoked_at),
            },
            new_value={"revoked_at": _optional_datetime_to_text(updated.revoked_at)},
            reason=reason,
            software_version=software_version,
        )
        audit_event_id = audit_repository.append(audit_event)

    return UserSessionManagementResult(
        session=updated,
        audit_event_id=audit_event_id,
        audit_event=audit_event,
    )


def _resolve_admin_actor(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    timestamp: datetime,
):
    return resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.MANAGE_USERS_AND_ROLES,
        timestamp=timestamp,
    )


def _validate_reasoned_user_change(
    *,
    target_user_id: str,
    reason: str,
    software_version: str,
    timestamp: datetime,
) -> None:
    _require_text(target_user_id, "Target user id")
    _require_text(reason, "User-management reason")
    _require_text(software_version, "Software version")
    _require_timezone_aware(timestamp, "User-management timestamp")


def _role_values(roles: tuple[Role, ...]) -> list[str]:
    if any(not isinstance(role, Role) for role in roles):
        raise UserManagementServiceError("User roles must be controlled Role values.")
    return [role.value for role in roles]


def _optional_datetime_to_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise UserManagementServiceError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise UserManagementServiceError(f"{field_name} must be timezone-aware.")
