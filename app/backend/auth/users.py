"""User and session identity models for regulated actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re

from app.backend.auth.permissions import Action, Role, is_allowed


class UserIdentityError(ValueError):
    """Raised when user or session identity data is incomplete or unsafe."""


_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class UserAccount:
    id: str
    display_name: str
    email: str
    roles: tuple[Role, ...]
    active: bool = True
    signature_label: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        _require_text(self.id, "User id")
        _require_text(self.display_name, "User display name")
        _require_text(self.email, "User email")
        if not _EMAIL_PATTERN.fullmatch(self.email):
            raise UserIdentityError("User email must be a valid email address.")
        if len(self.roles) == 0:
            raise UserIdentityError("User must have at least one role.")
        if any(not isinstance(role, Role) for role in self.roles):
            raise UserIdentityError("User roles must be controlled Role values.")
        if len(set(self.roles)) != len(self.roles):
            raise UserIdentityError("User roles cannot contain duplicates.")
        if self.signature_label is not None:
            _require_text(self.signature_label, "User signature label")
        _require_timezone_aware(self.created_at, "User created_at")
        object.__setattr__(self, "email", self.email.lower())

    def can_perform(self, action: Action) -> bool:
        _require_action(action)
        return any(
            is_allowed(role, action, user_active=self.active) for role in self.roles
        )


@dataclass(frozen=True, slots=True)
class UserSession:
    id: str
    user_id: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_text(self.id, "Session id")
        _require_text(self.user_id, "Session user id")
        _require_timezone_aware(self.issued_at, "Session issued_at")
        _require_timezone_aware(self.expires_at, "Session expires_at")
        if self.expires_at <= self.issued_at:
            raise UserIdentityError("Session expires_at must be after issued_at.")
        if self.revoked_at is not None:
            _require_timezone_aware(self.revoked_at, "Session revoked_at")
            if self.revoked_at < self.issued_at:
                raise UserIdentityError("Session revoked_at cannot be before issued_at.")

    def active_at(self, timestamp: datetime) -> bool:
        _require_timezone_aware(timestamp, "Session check timestamp")
        return (
            self.issued_at <= timestamp < self.expires_at
            and self.revoked_at is None
        )


@dataclass(frozen=True, slots=True)
class AuthenticatedActor:
    user_id: str
    display_name: str
    roles: tuple[Role, ...]

    def __post_init__(self) -> None:
        _require_text(self.user_id, "Actor user id")
        _require_text(self.display_name, "Actor display name")
        if len(self.roles) == 0:
            raise UserIdentityError("Actor must have at least one role.")
        if any(not isinstance(role, Role) for role in self.roles):
            raise UserIdentityError("Actor roles must be controlled Role values.")


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise UserIdentityError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise UserIdentityError(f"{field_name} must be timezone-aware.")


def _require_action(action: Action) -> None:
    if not isinstance(action, Action):
        raise UserIdentityError("Action must be a controlled Action value.")
