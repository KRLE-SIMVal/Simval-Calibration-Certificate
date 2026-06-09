from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_p10_handover_sop_contains_required_maintenance_controls():
    sop = (ROOT / "Docs" / "P10" / "Handover_And_Maintenance_SOP.md").read_text(
        encoding="utf-8"
    )

    normalized_sop = " ".join(sop.split())

    assert "SIMVal human must approve each production change." in normalized_sop
    assert "Add or update automated tests before or with implementation." in sop
    assert "Calculation logic must never be changed silently." in sop
    assert "The quarterly regression schedule remains mandatory" in sop
    assert "create a SQLite backup with JSON evidence" in sop
    assert "Treat the following as deviations" in sop
    assert "Do not paste uncontrolled customer data" in sop


def test_p10_production_readiness_checklist_contains_go_no_go_blockers():
    checklist = (
        ROOT / "Docs" / "P10" / "Production_Readiness_Checklist.md"
    ).read_text(encoding="utf-8")

    assert "GET /health" in checklist
    assert "GET /readiness" in checklist
    assert "SQLite backup evidence" in checklist
    assert "Restore to a separate target path succeeds" in checklist
    assert "SIMVAL_ENABLED_DISCIPLINES=temperature" in checklist
    assert "POST /auth/entra/session" in checklist
    assert "user_session_created" in checklist
    assert "Missing Microsoft Entra ID Free live tenant/app registration" in checklist
    assert "Missing reviewer independence control or approved deviation." in (
        checklist
    )
    assert "Missing human approval from System Owner and QA/Compliance Reviewer." in (
        checklist
    )


def test_p10_production_runtime_guide_contains_required_runtime_controls():
    guide = (ROOT / "Docs" / "P10" / "Production_Runtime_Guide.md").read_text(
        encoding="utf-8"
    )

    assert "SIMVAL_DATABASE_PATH" in guide
    assert "SIMVAL_ARTIFACT_STORAGE_PATH" in guide
    assert "python -m uvicorn app.backend.api.main:app" in guide
    assert "bootstrap_first_user.py" in guide
    assert "GET /readiness" in guide
    assert "GET /users" in guide
    assert "Do not commit production paths, credentials, tokens" in guide
    assert "Microsoft Entra ID Free" in guide
    assert "POST /auth/entra/session" in guide
    assert "user_session_created" in guide
    assert "Roles are not accepted from Entra token claims" in guide
    assert "Pressure workflow code remains a future extension point" in guide
    assert "SIMVAL_ENABLED_DISCIPLINES" in guide


def test_production_environment_example_contains_only_runtime_path_placeholders():
    env_example = (ROOT / "deployment" / "production.env.example").read_text(
        encoding="utf-8"
    )

    assert "SIMVAL_DATABASE_PATH=" in env_example
    assert "SIMVAL_ARTIFACT_STORAGE_PATH=" in env_example
    assert "SIMVAL_ENABLED_DISCIPLINES=temperature" in env_example
    assert "SIMVAL_AUTH_PROVIDER=entra_id_free" in env_example
    assert "SIMVAL_ENTRA_TENANT_ID=" in env_example
    assert "SIMVAL_ENTRA_CLIENT_ID=" in env_example
    assert "SIMVAL_ENTRA_AUDIENCE=" in env_example
    assert "SIMVAL_ENTRA_LOCAL_SESSION_HOURS=8" in env_example
    assert "SIMVAL_HOSTING_MODEL=simval_internal_host" in env_example
    assert "SIMVAL_REVIEWER_INDEPENDENCE_REQUIRED=true" in env_example
    assert "password" not in env_example.lower()
    assert "token" not in env_example.lower()


def test_p16_entra_implementation_log_records_auth_boundary_controls():
    log = (ROOT / "Docs" / "P16" / "P16_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "Microsoft Entra ID Free authentication boundary" in log
    assert "POST /auth/entra/session" in log
    assert "Entra token claims do not grant SIMVal roles" in log
    assert "user_session_created" in log
    assert "live tenant/app registration" in log
