"""Authentication and authorization service boundaries."""

from __future__ import annotations

from datetime import datetime
import sqlite3

from app.backend.auth.permissions import Action
from app.backend.auth.users import AuthenticatedActor, UserAccount
from app.backend.persistence.sqlite import (
    RecordNotFoundError,
    SQLiteUserAccountRepository,
    SQLiteUserSessionRepository,
)


class AuthenticationServiceError(ValueError):
    """Raised when an authenticated actor cannot be resolved or authorized."""


class AuthenticationFailureError(AuthenticationServiceError):
    """Raised when a session cannot authenticate an active user."""


class AuthorizationServiceError(AuthenticationServiceError):
    """Raised when an authenticated user lacks a required permission."""


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

    user = _resolve_user_for_session(
        connection=connection,
        session_id=session_id,
        timestamp=timestamp,
    )
    if not user.can_perform(action):
        raise AuthorizationServiceError("User is not authorized for this action.")

    return AuthenticatedActor(
        user_id=user.id,
        display_name=user.display_name,
        roles=user.roles,
    )


def resolve_actor_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    timestamp: datetime,
) -> AuthenticatedActor:
    """Resolve an active session to an authenticated actor without action check."""
    _require_text(session_id, "Session id")
    _require_timezone_aware(timestamp, "Authentication timestamp")
    user = _resolve_user_for_session(
        connection=connection,
        session_id=session_id,
        timestamp=timestamp,
    )
    return AuthenticatedActor(
        user_id=user.id,
        display_name=user.display_name,
        roles=user.roles,
    )


def _resolve_user_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    timestamp: datetime,
) -> UserAccount:
    user_repository = SQLiteUserAccountRepository(connection)
    session_repository = SQLiteUserSessionRepository(connection)
    try:
        session = session_repository.get(session_id)
    except RecordNotFoundError as exc:
        raise AuthenticationFailureError("Session is not active.") from exc
    if not session.active_at(timestamp):
        raise AuthenticationFailureError("Session is not active.")

    try:
        user = user_repository.get(session.user_id)
    except RecordNotFoundError as exc:
        raise AuthenticationFailureError("Session user is not active.") from exc
    if not user.active:
        raise AuthenticationFailureError("User account is inactive.")
    return user


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise AuthenticationServiceError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AuthenticationServiceError(f"{field_name} must be timezone-aware.")
