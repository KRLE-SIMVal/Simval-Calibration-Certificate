"""API runtime settings."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from collections.abc import Mapping


class ApiSettingsError(ValueError):
    """Raised when API runtime settings are incomplete or unsafe."""


@dataclass(frozen=True, slots=True)
class ApiSettings:
    database_path: Path
    artifact_storage_path: Path

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "ApiSettings":
        env = environment if environment is not None else os.environ
        raw_database_path = _required_environment_value(
            env,
            "SIMVAL_DATABASE_PATH",
        )
        raw_artifact_storage_path = _required_environment_value(
            env,
            "SIMVAL_ARTIFACT_STORAGE_PATH",
        )
        return cls(
            database_path=Path(raw_database_path),
            artifact_storage_path=Path(raw_artifact_storage_path),
        )


def _required_environment_value(
    environment: Mapping[str, str],
    name: str,
) -> str:
    value = environment.get(name)
    if value is None or value.strip() == "":
        raise ApiSettingsError(f"{name} is required.")
    return value
