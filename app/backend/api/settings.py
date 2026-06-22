"""API runtime settings."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from collections.abc import Mapping
from datetime import timedelta
from enum import StrEnum

from app.backend.auth.entra import EntraIdConfiguration
from app.backend.domain.entities import Discipline


class ApiSettingsError(ValueError):
    """Raised when API runtime settings are incomplete or unsafe."""


class AuthProvider(StrEnum):
    LOCAL_SESSION = "local_session"
    ENTRA_ID_FREE = "entra_id_free"


class RuntimeProfile(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


@dataclass(frozen=True, slots=True)
class ApiSettings:
    database_path: Path
    artifact_storage_path: Path
    runtime_profile: RuntimeProfile
    enabled_disciplines: frozenset[Discipline]
    auth_provider: AuthProvider
    entra_id: EntraIdConfiguration | None
    entra_session_duration: timedelta
    allow_provisional_valprobe_parser: bool

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
        runtime_profile = _runtime_profile(env)
        auth_provider = _auth_provider(env, runtime_profile)
        return cls(
            database_path=Path(raw_database_path),
            artifact_storage_path=Path(raw_artifact_storage_path),
            runtime_profile=runtime_profile,
            enabled_disciplines=_enabled_disciplines(env),
            auth_provider=auth_provider,
            entra_id=_entra_configuration(env, auth_provider),
            entra_session_duration=_entra_session_duration(env),
            allow_provisional_valprobe_parser=_allow_provisional_valprobe_parser(
                env,
                runtime_profile,
            ),
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


def _runtime_profile(environment: Mapping[str, str]) -> RuntimeProfile:
    raw_value = environment.get(
        "SIMVAL_RUNTIME_PROFILE",
        RuntimeProfile.DEVELOPMENT.value,
    )
    try:
        return RuntimeProfile(raw_value.strip())
    except ValueError as exc:
        raise ApiSettingsError(
            "SIMVAL_RUNTIME_PROFILE must be development or production."
        ) from exc


def _auth_provider(
    environment: Mapping[str, str],
    runtime_profile: RuntimeProfile,
) -> AuthProvider:
    raw_value = environment.get("SIMVAL_AUTH_PROVIDER")
    if raw_value is None or raw_value.strip() == "":
        if runtime_profile is RuntimeProfile.PRODUCTION:
            raise ApiSettingsError(
                "SIMVAL_AUTH_PROVIDER must be explicitly set in production."
            )
        raw_value = AuthProvider.LOCAL_SESSION.value
    try:
        auth_provider = AuthProvider(raw_value.strip())
    except ValueError as exc:
        raise ApiSettingsError("SIMVAL_AUTH_PROVIDER contains an invalid value.") from exc
    if (
        runtime_profile is RuntimeProfile.PRODUCTION
        and auth_provider is not AuthProvider.ENTRA_ID_FREE
    ):
        raise ApiSettingsError(
            "Production runtime requires SIMVAL_AUTH_PROVIDER=entra_id_free."
        )
    return auth_provider


def _entra_configuration(
    environment: Mapping[str, str],
    auth_provider: AuthProvider,
) -> EntraIdConfiguration | None:
    if auth_provider is not AuthProvider.ENTRA_ID_FREE:
        return None
    tenant_id = _required_environment_value(environment, "SIMVAL_ENTRA_TENANT_ID")
    client_id = _required_environment_value(environment, "SIMVAL_ENTRA_CLIENT_ID")
    audience = _optional_environment_value(environment, "SIMVAL_ENTRA_AUDIENCE")
    issuer = _optional_environment_value(environment, "SIMVAL_ENTRA_ISSUER")
    jwks_url = _optional_environment_value(environment, "SIMVAL_ENTRA_JWKS_URL")
    try:
        return EntraIdConfiguration.for_tenant(
            tenant_id=tenant_id,
            client_id=client_id,
            audience=audience,
            issuer=issuer,
            jwks_url=jwks_url,
        )
    except ValueError as exc:
        raise ApiSettingsError(str(exc)) from exc


def _entra_session_duration(environment: Mapping[str, str]) -> timedelta:
    raw_value = environment.get("SIMVAL_ENTRA_LOCAL_SESSION_HOURS", "8")
    try:
        hours = int(raw_value)
    except ValueError as exc:
        raise ApiSettingsError(
            "SIMVAL_ENTRA_LOCAL_SESSION_HOURS must be an integer."
        ) from exc
    if hours <= 0 or hours > 12:
        raise ApiSettingsError(
            "SIMVAL_ENTRA_LOCAL_SESSION_HOURS must be between 1 and 12."
        )
    return timedelta(hours=hours)


def _allow_provisional_valprobe_parser(
    environment: Mapping[str, str],
    runtime_profile: RuntimeProfile,
) -> bool:
    raw_value = environment.get("SIMVAL_ALLOW_PROVISIONAL_VALPROBE_PARSER", "false")
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        if runtime_profile is RuntimeProfile.PRODUCTION:
            raise ApiSettingsError(
                "SIMVAL_ALLOW_PROVISIONAL_VALPROBE_PARSER is not allowed in production."
            )
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ApiSettingsError(
        "SIMVAL_ALLOW_PROVISIONAL_VALPROBE_PARSER must be true or false."
    )


def _optional_environment_value(
    environment: Mapping[str, str],
    name: str,
) -> str | None:
    value = environment.get(name)
    if value is None or value.strip() == "":
        return None
    return value
