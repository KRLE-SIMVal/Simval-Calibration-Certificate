"""Controlled SQLite schema bootstrap for persistent databases."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from app.backend.persistence.migrations import (
    AppliedMigration,
    SQLiteMigration,
    apply_sqlite_migrations,
)
from app.backend.persistence.sqlite import initialize_schema, list_schema_versions


BASELINE_SCHEMA_VERSION = "p3-baseline-schema-v1"

SQLITE_BASELINE_SCHEMA_MIGRATION = SQLiteMigration(
    version=BASELINE_SCHEMA_VERSION,
    description="Validated P3 baseline SQLite schema",
    sql="""
    SELECT 'validated-p3-baseline-schema';
    """,
)


@dataclass(frozen=True, slots=True)
class SQLiteSchemaBootstrapResult:
    schema_versions: tuple[str, ...]
    controlled_migrations: tuple[AppliedMigration, ...]


def bootstrap_sqlite_schema(
    connection: sqlite3.Connection,
) -> SQLiteSchemaBootstrapResult:
    """Create the validated baseline schema and record controlled migration evidence.

    P3 starts before any production database deployment. The current validated
    schema is therefore recorded as one controlled baseline migration; future
    schema changes must be explicit SQL migrations after this baseline.
    """
    initialize_schema(connection)
    controlled_migrations = apply_sqlite_migrations(
        connection,
        (SQLITE_BASELINE_SCHEMA_MIGRATION,),
    )
    return SQLiteSchemaBootstrapResult(
        schema_versions=list_schema_versions(connection),
        controlled_migrations=controlled_migrations,
    )
