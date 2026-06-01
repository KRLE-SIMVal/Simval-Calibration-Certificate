import json

from app.backend.validation.report import build_validation_report


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

