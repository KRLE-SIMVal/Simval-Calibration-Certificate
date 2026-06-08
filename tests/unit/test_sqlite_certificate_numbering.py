import sqlite3

import pytest

from app.backend.persistence.sqlite import (
    PersistenceError,
    SQLiteCertificateNumberAllocator,
    initialize_schema,
)


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    return connection


def test_sqlite_certificate_number_allocator_allocates_and_increments_sequence():
    allocator = SQLiteCertificateNumberAllocator(_connection())
    allocator.create_sequence(prefix="SIMVAL-CAL", next_value=1)

    assert allocator.status("SIMVAL-CAL") == "active"
    assert allocator.allocate_next(prefix="SIMVAL-CAL", padding=4) == "SIMVAL-CAL-0001"
    assert allocator.allocate_next(prefix="SIMVAL-CAL", padding=4) == "SIMVAL-CAL-0002"
    assert allocator.next_value("SIMVAL-CAL") == 3


def test_sqlite_certificate_number_allocator_rejects_missing_sequence():
    allocator = SQLiteCertificateNumberAllocator(_connection())

    with pytest.raises(PersistenceError):
        allocator.allocate_next(prefix="SIMVAL-CAL", padding=4)


@pytest.mark.parametrize(
    ("prefix", "next_value"),
    [
        (" ", 1),
        ("SIMVAL-CAL", 0),
    ],
)
def test_sqlite_certificate_number_allocator_rejects_invalid_sequence_config(
    prefix,
    next_value,
):
    allocator = SQLiteCertificateNumberAllocator(_connection())

    with pytest.raises(PersistenceError):
        allocator.create_sequence(prefix=prefix, next_value=next_value)


def test_sqlite_certificate_number_allocator_rejects_invalid_padding():
    allocator = SQLiteCertificateNumberAllocator(_connection())
    allocator.create_sequence(prefix="SIMVAL-CAL", next_value=1)

    with pytest.raises(PersistenceError):
        allocator.allocate_next(prefix="SIMVAL-CAL", padding=0)


def test_sqlite_certificate_number_allocator_blocks_retired_sequence():
    allocator = SQLiteCertificateNumberAllocator(_connection())
    allocator.create_sequence(prefix="SIMVAL-CAL", next_value=7)

    allocator.retire_sequence("SIMVAL-CAL")

    assert allocator.status("SIMVAL-CAL") == "retired"
    assert allocator.next_value("SIMVAL-CAL") == 7
    with pytest.raises(PersistenceError, match="not active"):
        allocator.allocate_next(prefix="SIMVAL-CAL", padding=4)


def test_sqlite_certificate_number_allocator_rejects_second_retirement():
    allocator = SQLiteCertificateNumberAllocator(_connection())
    allocator.create_sequence(prefix="SIMVAL-CAL", next_value=7)
    allocator.retire_sequence("SIMVAL-CAL")

    with pytest.raises(PersistenceError, match="not active"):
        allocator.retire_sequence("SIMVAL-CAL")
