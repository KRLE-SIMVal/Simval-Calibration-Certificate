import pytest

from app.backend.api.settings import ApiSettings, ApiSettingsError


def test_api_settings_load_database_path_from_environment_mapping(tmp_path):
    database_path = tmp_path / "simval.sqlite3"

    settings = ApiSettings.from_environment(
        {"SIMVAL_DATABASE_PATH": str(database_path)}
    )

    assert settings.database_path == database_path


def test_api_settings_rejects_missing_database_path():
    with pytest.raises(ApiSettingsError):
        ApiSettings.from_environment({})


def test_api_settings_rejects_blank_database_path():
    with pytest.raises(ApiSettingsError):
        ApiSettings.from_environment({"SIMVAL_DATABASE_PATH": " "})
