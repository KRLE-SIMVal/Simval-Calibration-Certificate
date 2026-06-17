"""Controlled SQLite migration runner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import sqlite3


class MigrationError(RuntimeError):
    """Raised when a controlled migration cannot be applied safely."""


@dataclass(frozen=True, slots=True)
class SQLiteMigration:
    version: str
    description: str
    sql: str

    def __post_init__(self) -> None:
        _require_text(self.version, "Migration version")
        _require_text(self.description, "Migration description")
        _require_text(self.sql, "Migration SQL")

    @property
    def checksum_sha256(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AppliedMigration:
    version: str
    description: str
    checksum_sha256: str
    applied_at: datetime


def apply_sqlite_migrations(
    connection: sqlite3.Connection,
    migrations: tuple[SQLiteMigration, ...],
) -> tuple[AppliedMigration, ...]:
    """Apply unapplied migrations in supplied order and return full history."""
    connection.row_factory = sqlite3.Row
    _validate_migration_plan(migrations)
    _initialize_migration_history(connection)
    _reject_unknown_applied_migrations(connection, migrations)

    for migration in migrations:
        applied = _get_applied_migration(connection, migration.version)
        if applied is not None:
            if applied.checksum_sha256 != migration.checksum_sha256:
                raise MigrationError(
                    f"Applied migration {migration.version!r} checksum does not "
                    "match the supplied migration."
                )
            continue
        _apply_one_migration(connection, migration)

    return list_applied_migrations(connection)


def list_applied_migrations(
    connection: sqlite3.Connection,
) -> tuple[AppliedMigration, ...]:
    """Return controlled migration history in application order."""
    connection.row_factory = sqlite3.Row
    _initialize_migration_history(connection)
    rows = connection.execute(
        """
        SELECT
            version,
            description,
            checksum_sha256,
            applied_at
        FROM controlled_schema_migrations
        ORDER BY applied_order ASC
        """
    ).fetchall()
    return tuple(_applied_migration_from_row(row) for row in rows)


def _apply_one_migration(
    connection: sqlite3.Connection,
    migration: SQLiteMigration,
) -> None:
    try:
        with connection:
            connection.executescript(migration.sql)
            next_order = _next_applied_order(connection)
            applied_at = datetime.now(timezone.utc)
            connection.execute(
                """
                INSERT INTO controlled_schema_migrations (
                    version,
                    description,
                    checksum_sha256,
                    applied_at,
                    applied_order
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    migration.version,
                    migration.description,
                    migration.checksum_sha256,
                    applied_at.isoformat(),
                    next_order,
                ),
            )
    except sqlite3.DatabaseError as error:
        raise MigrationError(
            f"Could not apply migration {migration.version!r}."
        ) from error


def _initialize_migration_history(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS controlled_schema_migrations (
            version TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            checksum_sha256 TEXT NOT NULL,
            applied_at TEXT NOT NULL,
            applied_order INTEGER NOT NULL UNIQUE
        )
        """
    )
    connection.commit()


def _get_applied_migration(
    connection: sqlite3.Connection,
    version: str,
) -> AppliedMigration | None:
    row = connection.execute(
        """
        SELECT
            version,
            description,
            checksum_sha256,
            applied_at
        FROM controlled_schema_migrations
        WHERE version = ?
        """,
        (version,),
    ).fetchone()
    if row is None:
        return None
    return _applied_migration_from_row(row)


def _next_applied_order(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        """
        SELECT coalesce(max(applied_order), -1) + 1 AS next_order
        FROM controlled_schema_migrations
        """
    ).fetchone()
    return int(row["next_order"])


def _applied_migration_from_row(row: sqlite3.Row) -> AppliedMigration:
    return AppliedMigration(
        version=row["version"],
        description=row["description"],
        checksum_sha256=row["checksum_sha256"],
        applied_at=_datetime_from_text(row["applied_at"]),
    )


def _validate_migration_plan(migrations: tuple[SQLiteMigration, ...]) -> None:
    versions = [migration.version for migration in migrations]
    if len(set(versions)) != len(versions):
        raise MigrationError("Migration plan contains duplicate versions.")


def _reject_unknown_applied_migrations(
    connection: sqlite3.Connection,
    migrations: tuple[SQLiteMigration, ...],
) -> None:
    expected_versions = {migration.version for migration in migrations}
    applied_versions = {
        migration.version for migration in list_applied_migrations(connection)
    }
    unknown_versions = sorted(applied_versions - expected_versions)
    if unknown_versions:
        raise MigrationError(
            "Database contains applied migrations outside the controlled plan: "
            + ", ".join(unknown_versions)
            + "."
        )


def _datetime_from_text(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise MigrationError("Migration applied_at is not a valid ISO datetime.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MigrationError("Migration applied_at must be timezone-aware.")
    return parsed


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise MigrationError(f"{field_name} is required.")
