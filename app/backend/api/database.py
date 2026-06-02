"""SQLite connection lifecycle helpers for the API."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from app.backend.persistence.schema_bootstrap import bootstrap_sqlite_schema


@contextmanager
def sqlite_connection_scope(database_path: Path) -> Iterator[sqlite3.Connection]:
    """Open one SQLite connection for an API request and close it afterwards."""
    connection = sqlite3.connect(database_path)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        bootstrap_sqlite_schema(connection)
        yield connection
    finally:
        connection.close()
