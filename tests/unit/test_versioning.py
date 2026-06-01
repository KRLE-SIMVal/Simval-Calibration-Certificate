from datetime import datetime, timezone

import pytest

from app.backend.domain.versioning import (
    ConstantSet,
    UncertaintyBudget,
    VersionStatus,
    release_version_blockers,
)
from app.backend.domain.entities import Discipline, DomainValidationError
from app.backend.domain.workflow import RELEASE_BLOCKERS


def _approved_constant_set() -> ConstantSet:
    return ConstantSet(
        version="constants-2026-001",
        discipline=Discipline.TEMPERATURE,
        status=VersionStatus.APPROVED,
        effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        approved_by="qa-001",
        approved_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _approved_budget() -> UncertaintyBudget:
    return UncertaintyBudget(
        version="budget-temp-001",
        budget_type="temperature_logger",
        method="ValProbe RT automatic temperature",
        discipline=Discipline.TEMPERATURE,
        status=VersionStatus.APPROVED,
        linked_constant_set_version="constants-2026-001",
        approved_by="qa-001",
        approved_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )


def test_approved_constant_set_requires_approval_evidence():
    with pytest.raises(DomainValidationError):
        ConstantSet(
            version="constants-2026-001",
            discipline=Discipline.TEMPERATURE,
            status=VersionStatus.APPROVED,
            effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )


def test_approved_budget_requires_approval_evidence():
    with pytest.raises(DomainValidationError):
        UncertaintyBudget(
            version="budget-temp-001",
            budget_type="temperature_logger",
            method="ValProbe RT automatic temperature",
            discipline=Discipline.TEMPERATURE,
            status=VersionStatus.APPROVED,
            linked_constant_set_version="constants-2026-001",
        )


def test_budget_requires_linked_constant_set_version():
    with pytest.raises(DomainValidationError):
        UncertaintyBudget(
            version="budget-temp-001",
            budget_type="temperature_logger",
            method="ValProbe RT automatic temperature",
            discipline=Discipline.TEMPERATURE,
            status=VersionStatus.DRAFT,
            linked_constant_set_version=" ",
        )


def test_release_version_blockers_accept_approved_matching_versions():
    assert release_version_blockers(_approved_constant_set(), _approved_budget()) == ()


def test_release_version_blockers_reject_missing_versions():
    assert release_version_blockers(None, None) == (
        "missing_approved_constant_set",
        "missing_approved_uncertainty_budget",
    )


def test_release_version_blockers_reject_draft_versions():
    constant_set = ConstantSet(
        version="constants-2026-001",
        discipline=Discipline.TEMPERATURE,
        status=VersionStatus.DRAFT,
        effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    budget = UncertaintyBudget(
        version="budget-temp-001",
        budget_type="temperature_logger",
        method="ValProbe RT automatic temperature",
        discipline=Discipline.TEMPERATURE,
        status=VersionStatus.DRAFT,
        linked_constant_set_version="constants-2026-001",
    )

    assert release_version_blockers(constant_set, budget) == (
        "missing_approved_constant_set",
        "missing_approved_uncertainty_budget",
    )


def test_release_version_blockers_reject_budget_constant_mismatch():
    budget = UncertaintyBudget(
        version="budget-temp-001",
        budget_type="temperature_logger",
        method="ValProbe RT automatic temperature",
        discipline=Discipline.TEMPERATURE,
        status=VersionStatus.APPROVED,
        linked_constant_set_version="constants-2025-009",
        approved_by="qa-001",
        approved_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )

    assert release_version_blockers(_approved_constant_set(), budget) == (
        "constant_budget_version_mismatch",
    )


def test_release_version_blockers_report_one_mismatch_for_version_and_discipline():
    budget = UncertaintyBudget(
        version="budget-pressure-001",
        budget_type="pressure",
        method="Pressure method",
        discipline=Discipline.PRESSURE,
        status=VersionStatus.APPROVED,
        linked_constant_set_version="constants-2025-009",
        approved_by="qa-001",
        approved_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )

    assert release_version_blockers(_approved_constant_set(), budget) == (
        "constant_budget_version_mismatch",
    )


def test_release_blocker_catalog_contains_version_lock_blockers():
    assert "missing_approved_constant_set" in RELEASE_BLOCKERS
    assert "missing_approved_uncertainty_budget" in RELEASE_BLOCKERS
    assert "constant_budget_version_mismatch" in RELEASE_BLOCKERS
