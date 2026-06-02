"""Authentication and authorization service boundaries."""

from __future__ import annotations

from datetime import datetime
import sqlite3

from app.backend.auth.permissions import Action
from app.backend.auth.users import AuthenticatedActor
from app.backend.persistence.sqlite import (
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
)


class AuthenticationServiceError(ValueError):
    """Raised when an authenticated actor cannot be resolved or authorized."""


def resolve_actor_for_action(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    action: Action,
    timestamp: datetime,
) -> AuthenticatedActor:
    """Resolve an active session to an actor authorized for a regulated action."""
    _require_text(session_id, "Session id")
    if not isinstance(action, Action):
        raise AuthenticationServiceError("Action must be a controlled Action value.")
    _require_timezone_aware(timestamp, "Authentication timestamp")

    user_repository = SQLiteUserAccountRepository(connection)
    session_repository = SQLiteUserSessionRepository(connection)
    session = session_repository.get(session_id)
    if not session.active_at(timestamp):
        raise AuthenticationServiceError("Session is not active.")

    user = user_repository.get(session.user_id)
    if not user.active:
        raise AuthenticationServiceError("User account is inactive.")
    if not user.can_perform(action):
        raise AuthenticationServiceError("User is not authorized for this action.")

    return AuthenticatedActor(
        user_id=user.id,
        display_name=user.display_name,
        roles=user.roles,
    )


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise AuthenticationServiceError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AuthenticationServiceError(f"{field_name} must be timezone-aware.")
