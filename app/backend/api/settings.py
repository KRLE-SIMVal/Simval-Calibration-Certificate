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

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "ApiSettings":
        env = environment if environment is not None else os.environ
        raw_database_path = env.get("SIMVAL_DATABASE_PATH")
        if raw_database_path is None or raw_database_path.strip() == "":
            raise ApiSettingsError("SIMVAL_DATABASE_PATH is required.")
        return cls(database_path=Path(raw_database_path))
