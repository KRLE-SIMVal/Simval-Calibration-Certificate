import json

from app.backend.validation.deviation import build_regression_deviation
from scripts.validation.generate_regression_deviation import main


def test_regression_deviation_records_required_failure_evidence():
    deviation = build_regression_deviation(
        status="failure",
        objective="Automated regression run",
        test_suite="pytest",
        trigger_event="schedule",
        repository="KRLE-SIMVal/Simval-Calibration-Certificate",
        ref="refs/heads/main",
        sha="abcdef123456",
        run_id="123456",
        run_number="42",
        run_attempt="1",
        run_url="https://github.com/example/actions/runs/123456",
        run_started_at="2026-04-01T00:00:00Z",
        evidence={
            "junit": "Docs/Validation/evidence/2026/Q2/pytest.xml",
            "validation_report": (
                "Docs/Validation/evidence/2026/Q2/validation-report.json"
            ),
        },
        generated_at="2026-04-01T00:05:00+00:00",
    )

    data = json.loads(deviation.to_json())

    assert data["status"] == "open"
    assert data["failure_status"] == "failure"
    assert data["run_type"] == "quarterly_regression_failure"
    assert data["quarter"] == "2026-Q2"
    assert data["repository"] == "KRLE-SIMVal/Simval-Calibration-Certificate"
    assert data["sha"] == "abcdef123456"
    assert data["run_url"] == "https://github.com/example/actions/runs/123456"
    assert data["impact_assessment"] == "Routine use requires QA disposition."
    assert data["required_actions"] == [
        "Review failed regression evidence.",
        "Assess whether routine use may continue.",
        "Identify affected feature area.",
        "Create or link corrective action if a defect is confirmed.",
        "Add or update regression tests before closure if a defect is confirmed.",
    ]


def test_regression_deviation_markdown_is_issue_ready():
    deviation = build_regression_deviation(
        status="cancelled",
        objective="Automated regression run",
        test_suite="pytest",
        trigger_event="schedule",
        repository="KRLE-SIMVal/Simval-Calibration-Certificate",
        ref="refs/heads/main",
        sha="abcdef123456",
        run_id="123456",
        run_number="42",
        run_attempt="2",
        run_url="https://github.com/example/actions/runs/123456",
        run_started_at="2026-07-01T00:00:00+00:00",
        evidence={"artifact": "validation-evidence-123456"},
        generated_at="2026-07-01T00:05:00+00:00",
    )

    markdown = deviation.to_markdown()

    assert "# Quarterly Regression Deviation: 2026-Q3" in markdown
    assert "- Status: open" in markdown
    assert "- Failure status: cancelled" in markdown
    assert "- Run URL: https://github.com/example/actions/runs/123456" in markdown
    assert "Routine use requires QA disposition." in markdown
    assert "Review failed regression evidence." in markdown


def test_generate_regression_deviation_cli_writes_json_and_markdown(tmp_path):
    json_output = tmp_path / "deviation.json"
    markdown_output = tmp_path / "deviation.md"

    result = main(
        [
            "--status",
            "failure",
            "--objective",
            "Automated regression run",
            "--test-suite",
            "pytest",
            "--trigger-event",
            "schedule",
            "--repository",
            "KRLE-SIMVal/Simval-Calibration-Certificate",
            "--ref",
            "refs/heads/main",
            "--sha",
            "abcdef123456",
            "--run-id",
            "123456",
            "--run-number",
            "42",
            "--run-attempt",
            "1",
            "--run-url",
            "https://github.com/example/actions/runs/123456",
            "--run-started-at",
            "2026-10-01T00:00:00Z",
            "--evidence",
            "artifact=validation-evidence-123456",
            "--json-output",
            str(json_output),
            "--markdown-output",
            str(markdown_output),
        ]
    )

    data = json.loads(json_output.read_text(encoding="utf-8"))

    assert result == 0
    assert data["quarter"] == "2026-Q4"
    assert data["evidence"]["artifact"] == "validation-evidence-123456"
    assert markdown_output.read_text(encoding="utf-8").startswith(
        "# Quarterly Regression Deviation: 2026-Q4"
    )
