"""Audited governed-version management for calculation release gates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import sqlite3

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.auth.permissions import Action
from app.backend.domain.entities import Discipline
from app.backend.domain.versioning import ConstantSet, UncertaintyBudget, VersionStatus
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteConstantSetRepository,
    SQLiteUncertaintyBudgetRepository,
)
from app.backend.services.authentication import resolve_actor_for_action


class VersionManagementServiceError(ValueError):
    """Raised when governed version records cannot be created safely."""


@dataclass(frozen=True, slots=True)
class ConstantSetApproval:
    constant_set: ConstantSet
    audit_event_id: int
    audit_event: AuditEvent


@dataclass(frozen=True, slots=True)
class UncertaintyBudgetApproval:
    budget: UncertaintyBudget
    audit_event_id: int
    audit_event: AuditEvent


def record_approved_constant_set_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    version: str,
    discipline: Discipline,
    effective_from: datetime,
    software_version: str,
    timestamp: datetime,
) -> ConstantSetApproval:
    """Create an approved constant-set version with actor approval evidence."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.APPROVE_CONSTANTS,
        timestamp=timestamp,
    )
    _require_text(version, "Constant set version")
    _require_text(software_version, "Software version")
    _require_timezone_aware(effective_from, "Constant set effective_from")
    _require_timezone_aware(timestamp, "Constant set approval timestamp")
    constant_set = ConstantSet(
        version=version,
        discipline=discipline,
        status=VersionStatus.APPROVED,
        effective_from=effective_from,
        approved_by=actor.user_id,
        approved_at=timestamp,
    )
    audit_event = AuditEvent(
        entity_type="constant_set",
        entity_id=constant_set.version,
        action=AuditAction.CONSTANT_SET_CHANGED,
        user_id=actor.user_id,
        timestamp=timestamp,
        new_value={
            "discipline": constant_set.discipline.value,
            "effective_from": constant_set.effective_from.isoformat(),
            "status": constant_set.status.value,
        },
        software_version=software_version,
        constant_set_version=constant_set.version,
    )
    with connection:
        constant_repository = SQLiteConstantSetRepository(connection, autocommit=False)
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)
        constant_repository.add(constant_set)
        audit_event_id = audit_repository.append(audit_event)
    return ConstantSetApproval(
        constant_set=constant_set,
        audit_event_id=audit_event_id,
        audit_event=audit_event,
    )


def record_approved_uncertainty_budget_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    version: str,
    budget_type: str,
    method: str,
    discipline: Discipline,
    linked_constant_set_version: str,
    software_version: str,
    timestamp: datetime,
) -> UncertaintyBudgetApproval:
    """Create an approved uncertainty-budget version with actor approval evidence."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.APPROVE_UNCERTAINTY_BUDGET,
        timestamp=timestamp,
    )
    _require_text(version, "Uncertainty budget version")
    _require_text(budget_type, "Uncertainty budget type")
    _require_text(method, "Uncertainty budget method")
    _require_text(linked_constant_set_version, "Linked constant set version")
    _require_text(software_version, "Software version")
    _require_timezone_aware(timestamp, "Uncertainty budget approval timestamp")
    budget = UncertaintyBudget(
        version=version,
        budget_type=budget_type,
        method=method,
        discipline=discipline,
        status=VersionStatus.APPROVED,
        linked_constant_set_version=linked_constant_set_version,
        approved_by=actor.user_id,
        approved_at=timestamp,
    )
    audit_event = AuditEvent(
        entity_type="uncertainty_budget",
        entity_id=budget.version,
        action=AuditAction.BUDGET_CHANGED,
        user_id=actor.user_id,
        timestamp=timestamp,
        new_value={
            "budget_type": budget.budget_type,
            "discipline": budget.discipline.value,
            "linked_constant_set_version": budget.linked_constant_set_version,
            "method": budget.method,
            "status": budget.status.value,
        },
        software_version=software_version,
        constant_set_version=budget.linked_constant_set_version,
        budget_version=budget.version,
    )
    with connection:
        budget_repository = SQLiteUncertaintyBudgetRepository(connection, autocommit=False)
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)
        budget_repository.add(budget)
        audit_event_id = audit_repository.append(audit_event)
    return UncertaintyBudgetApproval(
        budget=budget,
        audit_event_id=audit_event_id,
        audit_event=audit_event,
    )


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise VersionManagementServiceError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise VersionManagementServiceError(f"{field_name} must be timezone-aware.")
