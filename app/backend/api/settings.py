"""API runtime settings."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from collections.abc import Mapping

from app.backend.domain.entities import Discipline


class ApiSettingsError(ValueError):
    """Raised when API runtime settings are incomplete or unsafe."""


@dataclass(frozen=True, slots=True)
class ApiSettings:
    database_path: Path
    artifact_storage_path: Path
    enabled_disciplines: frozenset[Discipline]

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
            enabled_disciplines=_enabled_disciplines(env),
        )


def _required_environment_value(
    environment: Mapping[str, str],
    name: str,
) -> str:
    value = environment.get(name)
    if value is None or value.strip() == "":
        raise ApiSettingsError(f"{name} is required.")
    return value


def _enabled_disciplines(environment: Mapping[str, str]) -> frozenset[Discipline]:
    raw_value = environment.get("SIMVAL_ENABLED_DISCIPLINES", "temperature")
    values = [value.strip() for value in raw_value.split(",") if value.strip() != ""]
    if len(values) == 0:
        raise ApiSettingsError("SIMVAL_ENABLED_DISCIPLINES must not be blank.")
    try:
        return frozenset(Discipline(value) for value in values)
    except ValueError as exc:
        raise ApiSettingsError(
            "SIMVAL_ENABLED_DISCIPLINES contains an invalid value."
        ) from exc
