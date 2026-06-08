import importlib
import sys

from tests.unit.test_api_app import _api_request


def test_asgi_entrypoint_uses_environment_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("SIMVAL_DATABASE_PATH", str(tmp_path / "simval.sqlite3"))
    monkeypatch.setenv("SIMVAL_ARTIFACT_STORAGE_PATH", str(tmp_path / "artifacts"))
    sys.modules.pop("app.backend.api.main", None)

    module = importlib.import_module("app.backend.api.main")

    response = _api_request(module.app, "GET", "/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
