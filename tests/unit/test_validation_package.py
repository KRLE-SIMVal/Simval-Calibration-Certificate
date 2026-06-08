import json

from app.backend.validation.package import (
    build_validation_package,
    write_validation_package,
)
from scripts.validation.generate_validation_package import main


def test_validation_package_records_iq_oq_pq_evidence_with_checksums(tmp_path):
    requirements = tmp_path / "requirements.md"
    requirements.write_text("requirements", encoding="utf-8")
    test_results = tmp_path / "pytest.xml"
    test_results.write_text("<testsuite/>", encoding="utf-8")
    validation_report = tmp_path / "validation-report.json"
    validation_report.write_text('{"status":"success"}', encoding="utf-8")

    package = build_validation_package(
        status="draft_pending_review",
        release_version="v0.8.0",
        objective="Production readiness validation",
        iq_paths=(requirements,),
        oq_paths=(test_results,),
        pq_paths=(validation_report,),
        known_limitations=("Reviewer approval is pending.",),
        source_commit="abcdef123456",
    )
    data = json.loads(package.to_json())

    assert data["package_type"] == "iq_oq_pq_equivalent"
    assert data["status"] == "draft_pending_review"
    assert data["release_version"] == "v0.8.0"
    assert data["source_commit"] == "abcdef123456"
    assert data["iq_evidence"][0]["path"].endswith("requirements.md")
    assert len(data["iq_evidence"][0]["sha256"]) == 64
    assert data["oq_evidence"][0]["purpose"] == (
        "Operational qualification evidence"
    )
    assert data["pq_evidence"][0]["purpose"] == (
        "Performance qualification evidence"
    )
    assert data["known_limitations"] == ["Reviewer approval is pending."]
    assert "QA/Compliance Reviewer" in data["required_reviewers"]


def test_validation_package_writes_markdown_and_reviewer_disposition(tmp_path):
    evidence = tmp_path / "validation-report.json"
    evidence.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "package"
    package = build_validation_package(
        status="draft_pending_review",
        release_version="v0.8.0",
        objective="Production readiness validation",
        iq_paths=(evidence,),
        oq_paths=(evidence,),
        pq_paths=(evidence,),
        known_limitations=("PDF/A decision pending.",),
        source_commit="abcdef123456",
    )

    write_validation_package(package, output_dir)

    assert (output_dir / "validation-package.json").is_file()
    markdown = (output_dir / "validation-package.md").read_text(encoding="utf-8")
    disposition = (output_dir / "reviewer-disposition.md").read_text(
        encoding="utf-8"
    )
    assert markdown.startswith("# SIMVal Validation Package")
    assert "PDF/A decision pending." in markdown
    assert "Decision: pending" in disposition
    assert "Pending human QA/laboratory approval." in disposition


def test_generate_validation_package_cli_writes_package_outputs(tmp_path):
    iq = tmp_path / "requirements.md"
    oq = tmp_path / "pytest.xml"
    pq = tmp_path / "validation-report.json"
    iq.write_text("requirements", encoding="utf-8")
    oq.write_text("<testsuite/>", encoding="utf-8")
    pq.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "package"

    result = main(
        [
            "--status",
            "draft_pending_review",
            "--release-version",
            "v0.8.0",
            "--objective",
            "Production readiness validation",
            "--source-commit",
            "abcdef123456",
            "--iq",
            str(iq),
            "--oq",
            str(oq),
            "--pq",
            str(pq),
            "--known-limitation",
            "Controlled fixture execution remains opt-in.",
            "--output-dir",
            str(output_dir),
        ]
    )

    data = json.loads(
        (output_dir / "validation-package.json").read_text(encoding="utf-8")
    )

    assert result == 0
    assert data["release_version"] == "v0.8.0"
    assert data["known_limitations"] == [
        "Controlled fixture execution remains opt-in."
    ]
    assert (output_dir / "validation-package.md").is_file()
    assert (output_dir / "reviewer-disposition.md").is_file()
