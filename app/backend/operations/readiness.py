"""Runtime readiness checks for production deployment."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import uuid


@dataclass(frozen=True, slots=True)
class ReadinessComponent:
    name: str
    status: str
    detail: str

    @property
    def ready(self) -> bool:
        return self.status == "ok"

    def to_payload(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class RuntimeReadiness:
    status: str
    components: tuple[ReadinessComponent, ...]

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def to_payload(self) -> dict:
        return {
            "status": self.status,
            "components": [component.to_payload() for component in self.components],
        }


def check_runtime_readiness(
    *,
    connection_scope: Callable[[], AbstractContextManager[sqlite3.Connection]],
    artifact_directory: Path | None,
) -> RuntimeReadiness:
    """Check required runtime dependencies without exposing local paths."""
    components = (
        _database_readiness(connection_scope),
        _artifact_storage_readiness(artifact_directory),
    )
    status = "ready" if all(component.ready for component in components) else "not_ready"
    return RuntimeReadiness(status=status, components=components)


def _database_readiness(
    connection_scope: Callable[[], AbstractContextManager[sqlite3.Connection]],
) -> ReadinessComponent:
    try:
        with connection_scope() as connection:
            connection.execute("SELECT 1").fetchone()
    except Exception:
        return ReadinessComponent(
            name="database",
            status="error",
            detail="SQLite connection check failed.",
        )
    return ReadinessComponent(
        name="database",
        status="ok",
        detail="SQLite connection check passed.",
    )


def _artifact_storage_readiness(
    artifact_directory: Path | None,
) -> ReadinessComponent:
    if artifact_directory is None:
        return ReadinessComponent(
            name="artifact_storage",
            status="not_configured",
            detail="Artifact storage path is not configured.",
        )
    if not artifact_directory.is_dir():
        return ReadinessComponent(
            name="artifact_storage",
            status="error",
            detail="Artifact storage path is not an existing directory.",
        )
    probe_path = artifact_directory / f".simval-readiness-{uuid.uuid4().hex}.tmp"
    try:
        with probe_path.open("xb") as handle:
            handle.write(b"ok")
        probe_path.unlink()
    except OSError:
        return ReadinessComponent(
            name="artifact_storage",
            status="error",
            detail="Artifact storage write/delete probe failed.",
        )
    return ReadinessComponent(
        name="artifact_storage",
        status="ok",
        detail="Artifact storage write/delete probe passed.",
    )

