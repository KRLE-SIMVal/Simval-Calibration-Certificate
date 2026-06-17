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
    assert "controlled SQLite schema baseline" in checklist
    assert "SQLite backup evidence" in checklist
    assert "Restore to a separate target path succeeds" in checklist
    assert "generate_production_readiness_report.py" in checklist
    assert "Production readiness report contains blockers." in checklist
    assert "Missing ValProbe parser validation evidence" in checklist
    assert "SIMVAL_ENABLED_DISCIPLINES=temperature" in checklist
    assert "POST /auth/entra/session" in checklist
    assert "user_session_created" in checklist
    assert "Missing Microsoft Entra ID Free live tenant/app registration" in checklist
    assert "Missing reviewer independence production verification evidence" in checklist
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
    assert "controlled SQLite schema" in guide
    assert "GET /users" in guide
    assert "Do not commit production paths, credentials, tokens" in guide
    assert "Microsoft Entra ID Free" in guide
    assert "POST /auth/entra/session" in guide
    assert "user_session_created" in guide
    assert "Roles are not accepted from Entra token claims" in guide
    assert "Same-user preparation/calculation" in guide
    assert "generate_production_readiness_report.py" in guide
    assert "generate_production_smoke_evidence.py" in guide
    assert "generate_pilot_validation_plan.py" in guide
    assert "generate_pilot_validation_package.py" in guide
    assert "generate_runtime_profile_evidence.py" in guide
    assert "generate_parser_validation_evidence.py" in guide
    assert "generate_backup_restore_validation_evidence.py" in guide
    assert "generate_reviewer_independence_evidence.py" in guide
    assert "generate_retention_policy_evidence.py" in guide
    assert "generate_human_approval_evidence.py" in guide
    assert "generate_live_entra_evidence.py" in guide
    assert "generate_tls_host_evidence.py" in guide
    assert "generate_pressure_template_approval_evidence.py" in guide
    assert "pilot-validation-plan" in guide
    assert "exit code `2` while blockers remain" in guide
    assert "--evidence live_entra=C:\\SIMVal\\evidence\\live-entra-evidence.json" in guide
    assert "--evidence tls_host=C:\\SIMVal\\evidence\\tls-host-evidence.json" in guide
    assert "--valprobe-parser-validated" in guide
    assert "--evidence valprobe_parser_validation" in guide
    assert "--evidence smoke_evidence" in guide
    assert "SHA-256 and byte size" in guide
    assert "unavailable_references" in guide
    assert "Manual pressure certificate release is available" in guide
    assert "manual pressure entry, calculation, review, preview" in guide
    assert "Known-schema automatic pressure CSV import" in guide
    assert "pressure-automatic-entry" in guide
    assert "Generic `.csv`, `.json`, and `.txt` source evidence" in guide
    assert "Pressure-specific PDF wording and template layout" in guide
    assert "SIMVAL_ENABLED_DISCIPLINES" in guide


def test_production_environment_example_contains_only_runtime_path_placeholders():
    env_example = (ROOT / "deployment" / "production.env.example").read_text(
        encoding="utf-8"
    )

    assert "SIMVAL_DATABASE_PATH=" in env_example
    assert "SIMVAL_ARTIFACT_STORAGE_PATH=" in env_example
    assert "SIMVAL_RUNTIME_PROFILE=production" in env_example
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


def test_p17_reviewer_independence_log_records_backend_control():
    log = (ROOT / "Docs" / "P17" / "P17_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "reviewer-independence backend enforcement" in log
    assert "calibration-job audit evidence" in log
    assert "Technical review approval is blocked" in log
    assert "QA release approval is blocked" in log
    assert "Certificate release is blocked" in log


def test_p18_production_readiness_log_records_go_live_report():
    log = (ROOT / "Docs" / "P18" / "P18_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "production-readiness evidence reporting" in log
    assert "generate_production_readiness_report.py" in log
    assert "exit code `2` while blockers remain" in log
    assert "temperature-only" in log
    assert "matching retained evidence references" in log


def test_p19_go_live_evidence_pack_maps_readiness_blockers_to_evidence():
    pack = (ROOT / "Docs" / "P19" / "P19_Go_Live_Evidence_Pack.md").read_text(
        encoding="utf-8"
    )

    for blocker in (
        "live_entra_verification_missing",
        "runtime_profile_not_production",
        "tls_host_verification_missing",
        "backup_restore_verification_missing",
        "reviewer_independence_evidence_missing",
        "valprobe_parser_validation_missing",
        "retention_policy_approval_missing",
        "final_human_approval_missing",
        "production_smoke_evidence_missing",
    ):
        assert blocker in pack

    for evidence_key in (
        "live_entra",
        "tls_host",
        "backup_restore",
        "reviewer_independence",
        "valprobe_parser_validation",
        "retention_policy",
        "human_approval",
        "smoke_evidence",
    ):
        assert f"--evidence {evidence_key}=" in pack

    assert "AB3" in pack
    assert "AB11" in pack
    assert "ready_for_go_live_review" in pack
    assert "matching retained evidence reference" in pack
    assert "SHA-256 and byte size" in pack
    assert "Runtime smoke evidence is parsed" in pack
    assert "ValProbe parser validation evidence is retained" in pack
    assert "generate_pilot_validation_plan.py" in pack
    assert "generate_pilot_validation_package.py" in pack
    assert "generate_runtime_profile_evidence.py" in pack
    assert "generate_parser_validation_evidence.py" in pack
    assert "generate_backup_restore_validation_evidence.py" in pack
    assert "generate_reviewer_independence_evidence.py" in pack
    assert "generate_retention_policy_evidence.py" in pack
    assert "generate_human_approval_evidence.py" in pack
    assert "generate_live_entra_evidence.py" in pack
    assert "generate_tls_host_evidence.py" in pack
    assert "pilot-validation-plan.json" in pack
    assert "pilot-validation-package" in pack
    assert "status` set to" in pack
    assert "`passed`" in pack
    assert "retention-policy evidence JSON" in pack
    assert "human approval evidence JSON" in pack
    assert "live Entra evidence JSON" in pack
    assert "TLS/host evidence JSON" in pack
    assert '["temperature"]' in pack
    assert "entra_id_free" in pack


def test_p19_implementation_log_records_no_domain_logic_change():
    log = (ROOT / "Docs" / "P19" / "P19_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "go-live evidence-pack planning" in log
    assert "P19_Go_Live_Evidence_Pack.md" in log
    assert "`--evidence key=value`" in log
    assert "No calculation, uncertainty, CMC, rounding" in log
    assert "System Owner and QA/Laboratory review" in log


def test_p22_implementation_log_records_schema_readiness_control():
    log = (ROOT / "Docs" / "P22" / "P22_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "runtime schema-baseline readiness" in log
    assert "`schema` readiness component" in log
    assert "baseline migration checksum" in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p20_implementation_log_records_evidence_reference_enforcement():
    log = (ROOT / "Docs" / "P20" / "P20_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "retained-evidence reference enforcement" in log
    assert "verified go-live flags" in log
    assert "`--evidence key=value`" in log
    assert "live_entra" in log
    assert "human_approval" in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p21_implementation_log_records_evidence_manifest_verification():
    log = (ROOT / "Docs" / "P21" / "P21_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "evidence-reference manifest verification" in log
    assert "SHA-256 and byte size" in log
    assert "unavailable_references" in log
    assert "live_entra_evidence_reference_unavailable" in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p23_implementation_log_records_smoke_evidence_collector():
    log = (ROOT / "Docs" / "P23" / "P23_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "runtime smoke evidence collection" in log
    assert "generate_production_smoke_evidence.py" in log
    assert "`GET /health`" in log
    assert "`GET /app/workflow`" in log
    assert "temperature-only scope" in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p24_implementation_log_records_smoke_evidence_gate():
    log = (ROOT / "Docs" / "P24" / "P24_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "smoke-evidence readiness gate" in log
    assert "--evidence smoke_evidence=<path>" in log
    assert "software version must match" in log
    assert "temperature-only" in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p25_implementation_log_records_parser_validation_gate():
    log = (ROOT / "Docs" / "P25" / "P25_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "ValProbe parser-validation readiness gate" in log
    assert "--valprobe-parser-validated" in log
    assert "valprobe_parser_validation" in log
    assert "valprobe_parser_validation_missing" in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p26_implementation_log_records_runtime_profile_gate():
    log = (ROOT / "Docs" / "P26" / "P26_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "runtime-profile readiness gate" in log
    assert "SIMVAL_RUNTIME_PROFILE=production" in log
    assert "runtime_profile_not_production" in log
    assert "production.env.example" in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p27_implementation_log_records_pilot_validation_plan():
    log = (ROOT / "Docs" / "P27" / "P27_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "controlled pilot-validation planning" in log
    assert "generate_pilot_validation_plan.py" in log
    assert "generate_pilot_validation_package.py" in log
    assert "pilot-validation-plan.json" in log
    assert "ValProbe parser validation" in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p28_implementation_log_records_runtime_profile_evidence():
    log = (ROOT / "Docs" / "P28" / "P28_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "runtime-profile pilot evidence generation" in log
    assert "generate_runtime_profile_evidence.py" in log
    assert "runtime_profile" in log
    assert "does not write filesystem paths" in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p29_implementation_log_records_parser_validation_evidence():
    log = (ROOT / "Docs" / "P29" / "P29_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "ValProbe parser-validation evidence generation" in log
    assert "generate_parser_validation_evidence.py" in log
    assert "valprobe_parser_validation" in log
    assert "--reviewer-approved" in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p30_implementation_log_records_backup_restore_validation_evidence():
    log = (ROOT / "Docs" / "P30" / "P30_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "backup/restore validation evidence generation" in log
    assert "generate_backup_restore_validation_evidence.py" in log
    assert "backup_restore" in log
    assert "checksums match" in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p31_implementation_log_records_reviewer_independence_evidence():
    log = (ROOT / "Docs" / "P31" / "P31_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "reviewer-independence validation evidence generation" in log
    assert "generate_reviewer_independence_evidence.py" in log
    assert "reviewer_independence" in log
    assert "hashes actor identifiers" in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p32_implementation_log_records_pilot_evidence_content_gate():
    log = (ROOT / "Docs" / "P32" / "P32_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "pilot-evidence content gating" in log
    assert "backup_restore" in log
    assert "reviewer_independence" in log
    assert "valprobe_parser_validation" in log
    assert 'status == "passed"' in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p33_implementation_log_records_retention_policy_evidence_gate():
    log = (ROOT / "Docs" / "P33" / "P33_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "retention-policy evidence generation" in log
    assert "generate_retention_policy_evidence.py" in log
    assert "retention_policy" in log
    assert 'status == "passed"' in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p34_implementation_log_records_human_approval_evidence_gate():
    log = (ROOT / "Docs" / "P34" / "P34_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "human go/no-go approval evidence generation" in log
    assert "generate_human_approval_evidence.py" in log
    assert "human_approval" in log
    assert 'status == "passed"' in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p35_implementation_log_records_live_entra_evidence_gate():
    log = (ROOT / "Docs" / "P35" / "P35_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "live Entra evidence generation" in log
    assert "generate_live_entra_evidence.py" in log
    assert "live_entra" in log
    assert 'status == "passed"' in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p36_implementation_log_records_tls_host_evidence_gate():
    log = (ROOT / "Docs" / "P36" / "P36_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "TLS/host evidence generation" in log
    assert "generate_tls_host_evidence.py" in log
    assert "tls_host" in log
    assert 'status == "passed"' in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p37_implementation_log_records_manual_pressure_calculation_api():
    log = (ROOT / "Docs" / "P37" / "P37_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "Manual Pressure Calculation API" in log
    assert "POST /pressure/manual-calculations" in log
    assert "calculation_run" in log
    assert "RUN_CALCULATION" in log
    assert "Later pressure milestones add persisted pressure workflow" in log


def test_p38_implementation_log_records_automatic_pressure_calculation_api():
    log = (ROOT / "Docs" / "P38" / "P38_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "Automatic Pressure Calculation API" in log
    assert "POST /pressure/automatic-calculations" in log
    assert "calculation_run" in log
    assert "RUN_CALCULATION" in log
    assert "Later pressure milestones add persisted pressure workflow" in log


def test_p39_implementation_log_records_persisted_pressure_workflow():
    log = (ROOT / "Docs" / "P39" / "P39_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "Persisted Pressure Calculation Workflow" in log
    assert "POST /calibration-jobs/{job_id}/pressure-calculations" in log
    assert "measurement_point_summaries" in log
    assert "calculation_run" in log
    assert "windows_selected" in log
    assert "known-schema" in log
    assert "production readiness" in log


def test_p40_implementation_log_records_generic_source_evidence_upload():
    log = (ROOT / "Docs" / "P40" / "P40_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "Controlled Generic Source Evidence Upload" in log
    assert "UploadedFileKind.OTHER" in log
    assert ".csv" in log
    assert "parser_status" in log
    assert "P45 later adds known-schema automatic pressure CSV import" in log


def test_p41_implementation_log_records_manual_pressure_release_path():
    log = (ROOT / "Docs" / "P41" / "P41_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "Manual Pressure Entry And Release Path" in log
    assert "POST /calibration-jobs/{job_id}/pressure-manual-entry" in log
    assert "ENTER_MANUAL_READINGS" in log
    assert "measurement_window_changed" in log
    assert "PDF release" in log
    assert "P45 later adds known-schema automatic pressure CSV import" in log


def test_p42_implementation_log_records_discipline_neutral_certificate_wording():
    log = (ROOT / "Docs" / "P42" / "P42_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "Discipline-Neutral Certificate Result Wording" in log
    assert "Skala/enhed / Scale/unit" in log
    assert "Temperature scale" in log
    assert "presentation-only" in log
    assert "No calculation logic changed" in log


def test_p43_implementation_log_records_discipline_aware_certificate_wording():
    log = (ROOT / "Docs" / "P43" / "P43_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "Discipline-Aware Certificate Result Wording" in log
    assert "Trykenhed / Pressure unit" in log
    assert "Trykresultater / Pressure results" in log
    assert "DANAK AB2" in log
    assert "DANAK AB11" in log


def test_p44_implementation_log_records_pressure_template_approval_evidence():
    log = (ROOT / "Docs" / "P44" / "P44_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "Pressure Template Approval Evidence" in log
    assert "generate_pressure_template_approval_evidence.py" in log
    assert "QA/Laboratory Reviewer and Laboratory Chief" in log
    assert "DANAK AB2" in log
    assert "DANAK AB11" in log
    assert "exit code `2` while blockers remain" in log
    assert "No calculation, uncertainty, CMC, rounding" in log


def test_p45_implementation_log_records_automatic_pressure_csv_import():
    log = (ROOT / "Docs" / "P45" / "P45_Implementation_Log.md").read_text(
        encoding="utf-8"
    )

    assert "Automatic Pressure CSV Import" in log
    assert "timestamp" in log
    assert "reference" in log
    assert "indication" in log
    assert "pressure-automatic-entry" in log
    assert "UPLOAD_IMPORT_FILE" in log
    assert "No pressure calculation, uncertainty, CMC, rounding" in log
