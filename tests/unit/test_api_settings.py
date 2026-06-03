import pytest

from app.backend.api.settings import ApiSettings, ApiSettingsError


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
