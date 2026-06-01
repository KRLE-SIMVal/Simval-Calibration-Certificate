"""Approved version locks for constants and uncertainty budgets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.backend.domain.entities import Discipline, DomainValidationError


class VersionStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    RETIRED = "retired"


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise DomainValidationError(f"{field_name} is required.")


def _require_instance(value: object, expected_type: type, field_name: str) -> None:
    if not isinstance(value, expected_type):
        raise DomainValidationError(f"{field_name} is invalid.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DomainValidationError(f"{field_name} must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class ConstantSet:
    version: str
    discipline: Discipline
    status: VersionStatus
    effective_from: datetime
    approved_by: str | None = None
    approved_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_text(self.version, "Constant set version")
        _require_instance(self.discipline, Discipline, "Constant set discipline")
        _require_instance(self.status, VersionStatus, "Constant set status")
        _require_timezone_aware(self.effective_from, "Constant set effective_from")
        _validate_approval_evidence(
            status=self.status,
            approved_by=self.approved_by,
            approved_at=self.approved_at,
            entity_name="Constant set",
        )

    @property
    def approved(self) -> bool:
        return self.status is VersionStatus.APPROVED


@dataclass(frozen=True, slots=True)
class UncertaintyBudget:
    version: str
    budget_type: str
    method: str
    discipline: Discipline
    status: VersionStatus
    linked_constant_set_version: str
    approved_by: str | None = None
    approved_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_text(self.version, "Uncertainty budget version")
        _require_text(self.budget_type, "Uncertainty budget type")
        _require_text(self.method, "Uncertainty budget method")
        _require_text(
            self.linked_constant_set_version,
            "Uncertainty budget linked constant set version",
        )
        _require_instance(self.discipline, Discipline, "Uncertainty budget discipline")
        _require_instance(self.status, VersionStatus, "Uncertainty budget status")
        _validate_approval_evidence(
            status=self.status,
            approved_by=self.approved_by,
            approved_at=self.approved_at,
            entity_name="Uncertainty budget",
        )

    @property
    def approved(self) -> bool:
        return self.status is VersionStatus.APPROVED


def release_version_blockers(
    constant_set: ConstantSet | None,
    budget: UncertaintyBudget | None,
) -> tuple[str, ...]:
    """Return release blockers for missing or incompatible approved versions."""
    blockers: list[str] = []
    if constant_set is None or not constant_set.approved:
        blockers.append("missing_approved_constant_set")
    if budget is None or not budget.approved:
        blockers.append("missing_approved_uncertainty_budget")
    if blockers:
        return tuple(blockers)

    assert constant_set is not None
    assert budget is not None
    if (
        budget.linked_constant_set_version != constant_set.version
        or budget.discipline is not constant_set.discipline
    ):
        blockers.append("constant_budget_version_mismatch")
    return tuple(blockers)


def _validate_approval_evidence(
    *,
    status: VersionStatus,
    approved_by: str | None,
    approved_at: datetime | None,
    entity_name: str,
) -> None:
    if status is not VersionStatus.APPROVED:
        return
    if approved_by is None or approved_by.strip() == "":
        raise DomainValidationError(f"{entity_name} approval user is required.")
    if approved_at is None:
        raise DomainValidationError(f"{entity_name} approval timestamp is required.")
    _require_timezone_aware(approved_at, f"{entity_name} approved_at")
