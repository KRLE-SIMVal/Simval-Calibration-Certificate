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
