"""Audited Microsoft Entra ID session issuance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import sqlite3

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.auth.entra import EntraTokenValidationError, EntraTokenVerifier
from app.backend.auth.users import UserAccount, UserSession
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
)
from app.backend.services.authentication import AuthenticationFailureError


class EntraAuthenticationServiceError(ValueError):
    """Raised when Entra-backed local session issuance fails."""


@dataclass(frozen=True, slots=True)
class EntraSessionIssuance:
    user: UserAccount
    session: UserSession
    audit_event_id: int
    audit_event: AuditEvent


def issue_entra_session(
    *,
    connection: sqlite3.Connection,
    bearer_token: str,
    token_verifier: EntraTokenVerifier,
    session_id: str,
    software_version: str,
    timestamp: datetime,
    max_session_duration: timedelta,
) -> EntraSessionIssuance:
    """Exchange a verified Entra token for a short audited local session."""
    _require_text(bearer_token, "Entra bearer token")
    _require_text(session_id, "Session id")
    _require_text(software_version, "Software version")
    _require_timezone_aware(timestamp, "Entra session timestamp")
    if max_session_duration.total_seconds() <= 0:
        raise EntraAuthenticationServiceError(
            "Maximum Entra session duration must be positive."
        )

    try:
        verified_token = token_verifier.verify(bearer_token, timestamp=timestamp)
    except EntraTokenValidationError as exc:
        raise AuthenticationFailureError("Entra token is not valid.") from exc

    user = _active_user_for_email(
        connection=connection,
        email=verified_token.email,
    )
    expires_at = min(verified_token.expires_at, timestamp + max_session_duration)
    if expires_at <= timestamp:
        raise AuthenticationFailureError("Entra token is expired.")
    session = UserSession(
        id=session_id,
        user_id=user.id,
        issued_at=timestamp,
        expires_at=expires_at,
    )

    with connection:
        session_repository = SQLiteUserSessionRepository(connection, autocommit=False)
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)

        session_repository.add(session)
        audit_event = AuditEvent(
            entity_type="user_session",
            entity_id=session.id,
            action=AuditAction.USER_SESSION_CREATED,
            user_id=user.id,
            timestamp=timestamp,
            new_value={
                "auth_provider": "entra_id_free",
                "entra_subject_id": verified_token.subject_id,
                "entra_tenant_id": verified_token.tenant_id,
                "email": user.email,
                "expires_at": session.expires_at.isoformat(),
            },
            reason="Microsoft Entra ID Free token verified.",
            software_version=software_version,
        )
        audit_event_id = audit_repository.append(audit_event)

    return EntraSessionIssuance(
        user=user,
        session=session,
        audit_event_id=audit_event_id,
        audit_event=audit_event,
    )


def _active_user_for_email(
    *,
    connection: sqlite3.Connection,
    email: str,
) -> UserAccount:
    _require_text(email, "Entra email")
    users = [
        user
        for user in SQLiteUserAccountRepository(connection).list_active()
        if user.email == email.lower()
    ]
    if len(users) == 0:
        raise AuthenticationFailureError(
            "No active local SIMVal user is linked to the Entra account."
        )
    if len(users) > 1:
        raise AuthenticationFailureError(
            "Multiple active local SIMVal users match the Entra account."
        )
    return users[0]


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise EntraAuthenticationServiceError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise EntraAuthenticationServiceError(f"{field_name} must be timezone-aware.")
