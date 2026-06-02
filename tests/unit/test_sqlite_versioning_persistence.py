import sqlite3
from datetime import datetime, timezone

import pytest

from app.backend.domain.entities import Discipline
from app.backend.domain.versioning import ConstantSet, UncertaintyBudget, VersionStatus
from app.backend.persistence.sqlite import (
    PersistenceError,
    SQLiteConstantSetRepository,
    SQLiteUncertaintyBudgetRepository,
    initialize_schema,
)


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    return connection


def _approved_constant_set() -> ConstantSet:
    return ConstantSet(
        version="constants-2026-001",
        discipline=Discipline.TEMPERATURE,
        status=VersionStatus.APPROVED,
        effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        approved_by="qa-001",
        approved_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _draft_constant_set() -> ConstantSet:
    return ConstantSet(
        version="constants-2026-002",
        discipline=Discipline.TEMPERATURE,
        status=VersionStatus.DRAFT,
        effective_from=datetime(2026, 2, 1, tzinfo=timezone.utc),
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


def _draft_budget() -> UncertaintyBudget:
    return UncertaintyBudget(
        version="budget-temp-002",
        budget_type="temperature_logger",
        method="ValProbe RT automatic temperature",
        discipline=Discipline.TEMPERATURE,
        status=VersionStatus.DRAFT,
        linked_constant_set_version="constants-2026-001",
    )


def test_sqlite_constant_set_repository_round_trips_version_record():
    connection = _connection()
    repository = SQLiteConstantSetRepository(connection)
    constant_set = _approved_constant_set()

    repository.add(constant_set)

    assert repository.get("constants-2026-001") == constant_set


def test_sqlite_constant_set_repository_rejects_duplicate_version():
    connection = _connection()
    repository = SQLiteConstantSetRepository(connection)
    repository.add(_approved_constant_set())

    with pytest.raises(PersistenceError):
        repository.add(_approved_constant_set())


def test_sqlite_uncertainty_budget_repository_round_trips_version_record():
    connection = _connection()
    SQLiteConstantSetRepository(connection).add(_approved_constant_set())
    repository = SQLiteUncertaintyBudgetRepository(connection)
    budget = _approved_budget()

    repository.add(budget)

    assert repository.get("budget-temp-001") == budget


def test_sqlite_uncertainty_budget_repository_rejects_unknown_constant_set():
    connection = _connection()
    repository = SQLiteUncertaintyBudgetRepository(connection)

    with pytest.raises(PersistenceError):
        repository.add(_approved_budget())


def test_sqlite_version_repositories_list_only_approved_versions():
    connection = _connection()
    constant_repository = SQLiteConstantSetRepository(connection)
    budget_repository = SQLiteUncertaintyBudgetRepository(connection)
    constant_repository.add(_draft_constant_set())
    constant_repository.add(_approved_constant_set())
    budget_repository.add(_approved_budget())
    budget_repository.add(_draft_budget())

    assert constant_repository.list_approved() == (_approved_constant_set(),)
    assert budget_repository.list_approved() == (_approved_budget(),)
