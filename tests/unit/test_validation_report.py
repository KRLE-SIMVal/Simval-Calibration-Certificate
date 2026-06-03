import json

from app.backend.validation.report import build_validation_report
from scripts.validation.generate_validation_report import main


def test_validation_report_contains_required_evidence_fields():
    report = build_validation_report(
        status="passed",
        objective="P1 default regression",
        test_suite="pytest",
        evidence={"junit": "Docs/Validation/evidence/latest/pytest.xml"},
    )
    data = json.loads(report.to_json())
    assert data["status"] == "passed"
    assert data["objective"] == "P1 default regression"
    assert data["test_suite"] == "pytest"
    assert data["python_version"]
    assert data["generated_at"]
    assert data["evidence"]["junit"] == "Docs/Validation/evidence/latest/pytest.xml"


def test_validation_report_classifies_quarterly_regression_run():
    report = build_validation_report(
        status="passed",
        objective="Quarterly regression",
        test_suite="pytest",
        evidence={"junit": "Docs/Validation/evidence/2026/Q2/pytest.xml"},
        trigger_event="schedule",
        run_id="123456",
        run_number="42",
        run_attempt="1",
        actor="github-actions[bot]",
        repository="KRLE-SIMVal/Simval-Calibration-Certificate",
        ref="refs/heads/main",
        sha="abcdef123456",
        run_started_at="2026-04-01T00:00:00+00:00",
        controlled_fixtures_enabled=False,
    )

    data = json.loads(report.to_json())

    assert data["run_type"] == "quarterly_regression"
    assert data["quarter"] == "2026-Q2"
    assert data["trigger_event"] == "schedule"
    assert data["ci"]["run_id"] == "123456"
    assert data["ci"]["run_number"] == "42"
    assert data["ci"]["run_attempt"] == "1"
    assert data["ci"]["actor"] == "github-actions[bot]"
    assert data["ci"]["repository"] == "KRLE-SIMVal/Simval-Calibration-Certificate"
    assert data["ci"]["ref"] == "refs/heads/main"
    assert data["ci"]["sha"] == "abcdef123456"
    assert data["controlled_fixture_policy"] == {
        "enabled": False,
        "enable_environment_variable": "SIMVAL_RUN_CONTROLLED_FIXTURE_TESTS=1",
        "default_ci_policy": "disabled",
        "reason": (
            "Controlled internal confidential fixtures are not approved "
            "for default CI execution."
        ),
    }
    assert data["environment"]["platform"]
    assert data["environment"]["python_implementation"]


def test_validation_report_classifies_push_as_change_regression():
    report = build_validation_report(
        status="passed",
        objective="Push regression",
        test_suite="pytest",
        trigger_event="push",
        run_started_at="2026-06-03T12:00:00+00:00",
    )

    data = json.loads(report.to_json())

    assert data["run_type"] == "change_regression"
    assert data["quarter"] == "2026-Q2"


def test_generate_validation_report_cli_writes_ci_metadata(tmp_path):
    output = tmp_path / "validation-report.json"

    result = main(
        [
            "--status",
            "success",
            "--objective",
            "Automated regression run",
            "--test-suite",
            "pytest",
            "--trigger-event",
            "workflow_dispatch",
            "--run-id",
            "789",
            "--run-started-at",
            "2026-07-01T00:00:00Z",
            "--controlled-fixtures-enabled",
            "false",
            "--evidence",
            "junit=Docs/Validation/evidence/latest/pytest.xml",
            "--output",
            str(output),
        ]
    )

    data = json.loads(output.read_text(encoding="utf-8"))

    assert result == 0
    assert data["run_type"] == "manual_regression"
    assert data["quarter"] == "2026-Q3"
    assert data["ci"]["run_id"] == "789"
    assert data["controlled_fixture_policy"]["enabled"] is False
    assert data["evidence"]["junit"] == "Docs/Validation/evidence/latest/pytest.xml"
