import sqlite3
from datetime import datetime

from app.backend.persistence.sqlite import (
    SCHEMA_VERSION,
    initialize_schema,
    list_schema_versions,
)


def test_initialize_schema_records_version_marker_once():
    connection = sqlite3.connect(":memory:")

    initialize_schema(connection)
    initialize_schema(connection)

    assert list_schema_versions(connection) == (SCHEMA_VERSION,)
    row = connection.execute(
        "SELECT applied_at FROM schema_migrations WHERE version = ?",
        (SCHEMA_VERSION,),
    ).fetchone()
    applied_at = datetime.fromisoformat(row["applied_at"])
    assert applied_at.tzinfo is not None


def test_initialize_schema_adds_sequence_status_to_existing_database():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE certificate_number_sequences (
            prefix TEXT PRIMARY KEY,
            next_value INTEGER NOT NULL CHECK (next_value > 0)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO certificate_number_sequences (prefix, next_value)
        VALUES (?, ?)
        """,
        ("SIMVAL-CAL", 7),
    )

    initialize_schema(connection)

    columns = connection.execute(
        "PRAGMA table_info(certificate_number_sequences)"
    ).fetchall()
    assert "status" in {column["name"] for column in columns}
    row = connection.execute(
        """
        SELECT next_value, status
        FROM certificate_number_sequences
        WHERE prefix = ?
        """,
        ("SIMVAL-CAL",),
    ).fetchone()
    assert dict(row) == {"next_value": 7, "status": "active"}
