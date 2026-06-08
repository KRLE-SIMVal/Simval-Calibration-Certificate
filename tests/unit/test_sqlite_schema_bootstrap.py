import sqlite3

from app.backend.persistence.migrations import list_applied_migrations
from app.backend.persistence.schema_bootstrap import (
    SQLITE_BASELINE_SCHEMA_MIGRATION,
    bootstrap_sqlite_schema,
)
from app.backend.persistence.sqlite import list_schema_versions


def test_bootstrap_sqlite_schema_creates_current_schema_and_records_baseline():
    connection = sqlite3.connect(":memory:")

    result = bootstrap_sqlite_schema(connection)

    assert list_schema_versions(connection) == ("p13-sqlite-schema-v1",)
    assert result.schema_versions == ("p13-sqlite-schema-v1",)
    assert result.controlled_migrations[0].version == (
        SQLITE_BASELINE_SCHEMA_MIGRATION.version
    )
    connection.execute("SELECT id FROM user_accounts").fetchall()
    connection.execute("SELECT id FROM audit_events").fetchall()
    connection.execute("SELECT job_id FROM certificate_metadata").fetchall()
    connection.execute("SELECT job_id FROM selected_reference_equipment").fetchall()


def test_bootstrap_sqlite_schema_is_idempotent_for_matching_baseline_checksum():
    connection = sqlite3.connect(":memory:")

    first = bootstrap_sqlite_schema(connection)
    second = bootstrap_sqlite_schema(connection)

    assert first.controlled_migrations == second.controlled_migrations
    assert list_applied_migrations(connection) == first.controlled_migrations
