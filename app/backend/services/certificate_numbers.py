"""Audited certificate-number sequence services."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import sqlite3

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.auth.permissions import Action
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCertificateNumberAllocator,
)
from app.backend.services.authentication import resolve_actor_for_action


class CertificateNumberServiceError(ValueError):
    """Raised when certificate-number sequence control fails."""


@dataclass(frozen=True, slots=True)
class CertificateNumberSequenceResult:
    prefix: str
    next_value: int
    status: str
    audit_event_id: int
    audit_event: AuditEvent


@dataclass(frozen=True, slots=True)
class CertificateNumberAllocationResult:
    prefix: str
    certificate_number: str
    next_value_after: int
    audit_event_id: int
    audit_event: AuditEvent


@dataclass(frozen=True, slots=True)
class CertificateNumberSequenceRetirementResult:
    prefix: str
    next_value: int
    previous_status: str
    status: str
    audit_event_id: int
    audit_event: AuditEvent


def create_certificate_number_sequence_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    prefix: str,
    next_value: int,
    software_version: str,
    timestamp: datetime,
) -> CertificateNumberSequenceResult:
    """Create a certificate-number sequence for an authorized admin session."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.MANAGE_CERTIFICATE_NUMBERS,
        timestamp=timestamp,
    )
    _validate_sequence_inputs(
        prefix=prefix,
        software_version=software_version,
        timestamp=timestamp,
    )

    with connection:
        allocator = SQLiteCertificateNumberAllocator(connection, autocommit=False)
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)
        allocator.create_sequence(prefix=prefix, next_value=next_value)
        audit_event = AuditEvent(
            entity_type="certificate_number_sequence",
            entity_id=prefix,
            action=AuditAction.CERTIFICATE_NUMBER_SEQUENCE_CHANGED,
            user_id=actor.user_id,
            timestamp=timestamp,
            new_value={
                "prefix": prefix,
                "next_value": next_value,
                "status": "active",
            },
            software_version=software_version,
        )
        audit_event_id = audit_repository.append(audit_event)

    return CertificateNumberSequenceResult(
        prefix=prefix,
        next_value=next_value,
        status="active",
        audit_event_id=audit_event_id,
        audit_event=audit_event,
    )


def retire_certificate_number_sequence_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    prefix: str,
    reason: str,
    software_version: str,
    timestamp: datetime,
) -> CertificateNumberSequenceRetirementResult:
    """Retire a certificate-number sequence for an authorized admin session."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.MANAGE_CERTIFICATE_NUMBERS,
        timestamp=timestamp,
    )
    _validate_sequence_inputs(
        prefix=prefix,
        software_version=software_version,
        timestamp=timestamp,
    )
    _require_text(reason, "Certificate number retirement reason")

    with connection:
        allocator = SQLiteCertificateNumberAllocator(connection, autocommit=False)
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)
        next_value = allocator.next_value(prefix)
        previous_status = allocator.status(prefix)
        allocator.retire_sequence(prefix)
        audit_event = AuditEvent(
            entity_type="certificate_number_sequence",
            entity_id=prefix,
            action=AuditAction.CERTIFICATE_NUMBER_SEQUENCE_RETIRED,
            user_id=actor.user_id,
            timestamp=timestamp,
            previous_value={
                "prefix": prefix,
                "next_value": next_value,
                "status": previous_status,
            },
            new_value={
                "prefix": prefix,
                "next_value": next_value,
                "status": "retired",
            },
            reason=reason,
            software_version=software_version,
        )
        audit_event_id = audit_repository.append(audit_event)

    return CertificateNumberSequenceRetirementResult(
        prefix=prefix,
        next_value=next_value,
        previous_status=previous_status,
        status="retired",
        audit_event_id=audit_event_id,
        audit_event=audit_event,
    )


def allocate_certificate_number_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    prefix: str,
    padding: int,
    software_version: str,
    timestamp: datetime,
) -> CertificateNumberAllocationResult:
    """Allocate the next controlled certificate number for an admin session."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.MANAGE_CERTIFICATE_NUMBERS,
        timestamp=timestamp,
    )
    _validate_sequence_inputs(
        prefix=prefix,
        software_version=software_version,
        timestamp=timestamp,
    )

    with connection:
        return allocate_certificate_number_in_transaction(
            connection=connection,
            user_id=actor.user_id,
            prefix=prefix,
            padding=padding,
            software_version=software_version,
            timestamp=timestamp,
        )


def allocate_certificate_number_in_transaction(
    *,
    connection: sqlite3.Connection,
    user_id: str,
    prefix: str,
    padding: int,
    software_version: str,
    timestamp: datetime,
    context: Mapping[str, str] | None = None,
) -> CertificateNumberAllocationResult:
    """Allocate a number inside the caller's transaction and audit the use."""
    _validate_sequence_inputs(
        prefix=prefix,
        software_version=software_version,
        timestamp=timestamp,
    )
    _require_text(user_id, "Certificate number user")

    allocator = SQLiteCertificateNumberAllocator(connection, autocommit=False)
    audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)
    certificate_number = allocator.allocate_next(prefix=prefix, padding=padding)
    next_value_after = allocator.next_value(prefix)
    new_value: dict[str, object] = {
        "prefix": prefix,
        "certificate_number": certificate_number,
        "next_value_after": next_value_after,
    }
    if context is not None:
        new_value["context"] = dict(context)
    audit_event = AuditEvent(
        entity_type="certificate_number",
        entity_id=certificate_number,
        action=AuditAction.CERTIFICATE_NUMBER_ALLOCATED,
        user_id=user_id,
        timestamp=timestamp,
        new_value=new_value,
        software_version=software_version,
    )
    audit_event_id = audit_repository.append(audit_event)

    return CertificateNumberAllocationResult(
        prefix=prefix,
        certificate_number=certificate_number,
        next_value_after=next_value_after,
        audit_event_id=audit_event_id,
        audit_event=audit_event,
    )


def _validate_sequence_inputs(
    *,
    prefix: str,
    software_version: str,
    timestamp: datetime,
) -> None:
    _require_text(prefix, "Certificate number prefix")
    _require_text(software_version, "Software version")
    _require_timezone_aware(timestamp, "Certificate number timestamp")


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise CertificateNumberServiceError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CertificateNumberServiceError(f"{field_name} must be timezone-aware.")
