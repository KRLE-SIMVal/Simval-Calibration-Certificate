import sqlite3

import pytest

from app.backend.persistence.migrations import (
    MigrationError,
    SQLiteMigration,
    apply_sqlite_migrations,
    list_applied_migrations,
)


def test_apply_sqlite_migrations_applies_and_records_history_in_order():
    connection = sqlite3.connect(":memory:")
    migrations = (
        SQLiteMigration(
            version="001",
            description="create example table",
            sql="CREATE TABLE example_records (id TEXT PRIMARY KEY);",
        ),
        SQLiteMigration(
            version="002",
            description="add example value",
            sql="ALTER TABLE example_records ADD COLUMN value TEXT;",
        ),
    )

    history = apply_sqlite_migrations(connection, migrations)

    assert tuple(record.version for record in history) == ("001", "002")
    assert history[0].checksum_sha256 == migrations[0].checksum_sha256
    assert history[0].applied_at.tzinfo is not None
    columns = connection.execute("PRAGMA table_info(example_records)").fetchall()
    assert [column[1] for column in columns] == ["id", "value"]


def test_apply_sqlite_migrations_is_idempotent_for_matching_checksum():
    connection = sqlite3.connect(":memory:")
    migration = SQLiteMigration(
        version="001",
        description="create example table",
        sql="CREATE TABLE example_records (id TEXT PRIMARY KEY);",
    )

    first_history = apply_sqlite_migrations(connection, (migration,))
    second_history = apply_sqlite_migrations(connection, (migration,))

    assert first_history == second_history
    assert len(second_history) == 1


def test_apply_sqlite_migrations_rejects_checksum_mismatch_for_applied_version():
    connection = sqlite3.connect(":memory:")
    apply_sqlite_migrations(
        connection,
        (
            SQLiteMigration(
                version="001",
                description="create example table",
                sql="CREATE TABLE example_records (id TEXT PRIMARY KEY);",
            ),
        ),
    )

    with pytest.raises(MigrationError) as exc_info:
        apply_sqlite_migrations(
            connection,
            (
                SQLiteMigration(
                    version="001",
                    description="changed migration",
                    sql="CREATE TABLE changed_records (id TEXT PRIMARY KEY);",
                ),
            ),
        )

    assert "checksum" in str(exc_info.value)


def test_apply_sqlite_migrations_rejects_duplicate_versions_in_plan():
    connection = sqlite3.connect(":memory:")

    with pytest.raises(MigrationError):
        apply_sqlite_migrations(
            connection,
            (
                SQLiteMigration(
                    version="001",
                    description="create first table",
                    sql="CREATE TABLE first_records (id TEXT PRIMARY KEY);",
                ),
                SQLiteMigration(
                    version="001",
                    description="create second table",
                    sql="CREATE TABLE second_records (id TEXT PRIMARY KEY);",
                ),
            ),
        )


def test_apply_sqlite_migrations_rejects_unknown_applied_history():
    connection = sqlite3.connect(":memory:")
    unmanaged = SQLiteMigration(
        version="unmanaged",
        description="unmanaged schema change",
        sql="CREATE TABLE unmanaged_records (id TEXT PRIMARY KEY);",
    )
    apply_sqlite_migrations(connection, (unmanaged,))

    with pytest.raises(MigrationError) as exc_info:
        apply_sqlite_migrations(
            connection,
            (
                SQLiteMigration(
                    version="001",
                    description="controlled plan",
                    sql="CREATE TABLE controlled_records (id TEXT PRIMARY KEY);",
                ),
            ),
        )

    assert "outside the controlled plan" in str(exc_info.value)


def test_apply_sqlite_migrations_does_not_record_failed_migration():
    connection = sqlite3.connect(":memory:")

    with pytest.raises(MigrationError):
        apply_sqlite_migrations(
            connection,
            (
                SQLiteMigration(
                    version="001",
                    description="invalid migration",
                    sql="CREATE TABLE broken_records (id TEXT PRIMARY KEY",
                ),
            ),
        )

    assert list_applied_migrations(connection) == ()
