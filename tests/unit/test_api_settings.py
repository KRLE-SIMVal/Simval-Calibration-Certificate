from datetime import timedelta

import pytest

from app.backend.api.settings import (
    AuthProvider,
    ApiSettings,
    ApiSettingsError,
    RuntimeProfile,
)
from app.backend.domain.entities import Discipline


def test_api_settings_load_database_path_from_environment_mapping(tmp_path):
    database_path = tmp_path / "simval.sqlite3"
    artifact_storage_path = tmp_path / "artifacts"

    settings = ApiSettings.from_environment(
        {
            "SIMVAL_DATABASE_PATH": str(database_path),
            "SIMVAL_ARTIFACT_STORAGE_PATH": str(artifact_storage_path),
        }
    )

    assert settings.database_path == database_path
    assert settings.artifact_storage_path == artifact_storage_path
    assert settings.runtime_profile is RuntimeProfile.DEVELOPMENT
    assert settings.enabled_disciplines == frozenset({Discipline.TEMPERATURE})
    assert settings.auth_provider is AuthProvider.LOCAL_SESSION
    assert settings.entra_id is None
    assert settings.entra_session_duration == timedelta(hours=8)


def test_api_settings_loads_enabled_disciplines_from_environment_mapping(tmp_path):
    settings = ApiSettings.from_environment(
        {
            "SIMVAL_DATABASE_PATH": str(tmp_path / "simval.sqlite3"),
            "SIMVAL_ARTIFACT_STORAGE_PATH": str(tmp_path / "artifacts"),
            "SIMVAL_ENABLED_DISCIPLINES": "temperature,pressure",
        }
    )

    assert settings.enabled_disciplines == frozenset(
        {Discipline.TEMPERATURE, Discipline.PRESSURE}
    )


def test_api_settings_loads_entra_id_free_configuration(tmp_path):
    settings = ApiSettings.from_environment(
        {
            "SIMVAL_DATABASE_PATH": str(tmp_path / "simval.sqlite3"),
            "SIMVAL_ARTIFACT_STORAGE_PATH": str(tmp_path / "artifacts"),
            "SIMVAL_AUTH_PROVIDER": "entra_id_free",
            "SIMVAL_ENTRA_TENANT_ID": "tenant-001",
            "SIMVAL_ENTRA_CLIENT_ID": "client-001",
            "SIMVAL_ENTRA_LOCAL_SESSION_HOURS": "4",
        }
    )

    assert settings.auth_provider is AuthProvider.ENTRA_ID_FREE
    assert settings.entra_id is not None
    assert settings.entra_id.tenant_id == "tenant-001"
    assert settings.entra_id.client_id == "client-001"
    assert settings.entra_id.audience == "client-001"
    assert settings.entra_session_duration == timedelta(hours=4)


def test_api_settings_loads_production_runtime_profile(tmp_path):
    settings = ApiSettings.from_environment(
        {
            "SIMVAL_DATABASE_PATH": str(tmp_path / "simval.sqlite3"),
            "SIMVAL_ARTIFACT_STORAGE_PATH": str(tmp_path / "artifacts"),
            "SIMVAL_RUNTIME_PROFILE": "production",
            "SIMVAL_AUTH_PROVIDER": "entra_id_free",
            "SIMVAL_ENTRA_TENANT_ID": "tenant-001",
            "SIMVAL_ENTRA_CLIENT_ID": "client-001",
        }
    )

    assert settings.runtime_profile is RuntimeProfile.PRODUCTION


def test_api_settings_rejects_invalid_runtime_profile(tmp_path):
    with pytest.raises(ApiSettingsError, match="SIMVAL_RUNTIME_PROFILE"):
        ApiSettings.from_environment(
            {
                "SIMVAL_DATABASE_PATH": str(tmp_path / "simval.sqlite3"),
                "SIMVAL_ARTIFACT_STORAGE_PATH": str(tmp_path / "artifacts"),
                "SIMVAL_RUNTIME_PROFILE": "prodution",
                "SIMVAL_AUTH_PROVIDER": "local_session",
            }
        )


def test_api_settings_rejects_missing_database_path():
    with pytest.raises(ApiSettingsError):
        ApiSettings.from_environment({})


def test_api_settings_rejects_blank_database_path():
    with pytest.raises(ApiSettingsError):
        ApiSettings.from_environment(
            {
                "SIMVAL_DATABASE_PATH": " ",
                "SIMVAL_ARTIFACT_STORAGE_PATH": "artifacts",
            }
        )


def test_api_settings_rejects_missing_artifact_storage_path(tmp_path):
    with pytest.raises(ApiSettingsError):
        ApiSettings.from_environment(
            {"SIMVAL_DATABASE_PATH": str(tmp_path / "simval.sqlite3")}
        )


def test_api_settings_rejects_blank_artifact_storage_path(tmp_path):
    with pytest.raises(ApiSettingsError):
        ApiSettings.from_environment(
            {
                "SIMVAL_DATABASE_PATH": str(tmp_path / "simval.sqlite3"),
                "SIMVAL_ARTIFACT_STORAGE_PATH": " ",
            }
        )


def test_api_settings_rejects_invalid_enabled_discipline(tmp_path):
    with pytest.raises(ApiSettingsError):
        ApiSettings.from_environment(
            {
                "SIMVAL_DATABASE_PATH": str(tmp_path / "simval.sqlite3"),
                "SIMVAL_ARTIFACT_STORAGE_PATH": str(tmp_path / "artifacts"),
                "SIMVAL_ENABLED_DISCIPLINES": "temperature,humidity",
            }
        )


def test_api_settings_rejects_invalid_auth_provider(tmp_path):
    with pytest.raises(ApiSettingsError):
        ApiSettings.from_environment(
            {
                "SIMVAL_DATABASE_PATH": str(tmp_path / "simval.sqlite3"),
                "SIMVAL_ARTIFACT_STORAGE_PATH": str(tmp_path / "artifacts"),
                "SIMVAL_AUTH_PROVIDER": "basic_password",
            }
        )


def test_api_settings_rejects_implicit_auth_provider_in_production(tmp_path):
    with pytest.raises(ApiSettingsError):
        ApiSettings.from_environment(
            {
                "SIMVAL_DATABASE_PATH": str(tmp_path / "simval.sqlite3"),
                "SIMVAL_ARTIFACT_STORAGE_PATH": str(tmp_path / "artifacts"),
                "SIMVAL_RUNTIME_PROFILE": "production",
            }
        )


def test_api_settings_rejects_local_auth_provider_in_production(tmp_path):
    with pytest.raises(ApiSettingsError):
        ApiSettings.from_environment(
            {
                "SIMVAL_DATABASE_PATH": str(tmp_path / "simval.sqlite3"),
                "SIMVAL_ARTIFACT_STORAGE_PATH": str(tmp_path / "artifacts"),
                "SIMVAL_RUNTIME_PROFILE": "production",
                "SIMVAL_AUTH_PROVIDER": "local_session",
            }
        )


def test_api_settings_rejects_entra_provider_without_tenant_id(tmp_path):
    with pytest.raises(ApiSettingsError):
        ApiSettings.from_environment(
            {
                "SIMVAL_DATABASE_PATH": str(tmp_path / "simval.sqlite3"),
                "SIMVAL_ARTIFACT_STORAGE_PATH": str(tmp_path / "artifacts"),
                "SIMVAL_AUTH_PROVIDER": "entra_id_free",
                "SIMVAL_ENTRA_CLIENT_ID": "client-001",
            }
        )


def test_api_settings_rejects_invalid_entra_session_duration(tmp_path):
    with pytest.raises(ApiSettingsError):
        ApiSettings.from_environment(
            {
                "SIMVAL_DATABASE_PATH": str(tmp_path / "simval.sqlite3"),
                "SIMVAL_ARTIFACT_STORAGE_PATH": str(tmp_path / "artifacts"),
                "SIMVAL_ENTRA_LOCAL_SESSION_HOURS": "24",
            }
        )
