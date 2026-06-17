import json
from datetime import datetime, timezone

import pytest

from app.backend.validation.parser_validation import (
    ParserValidationEvidenceError,
    build_parser_validation_evidence,
)
from scripts.validation.generate_parser_validation_evidence import main


def test_parser_validation_evidence_passes_when_fixture_run_and_review_are_present(
    tmp_path,
):
    files = _evidence_files(tmp_path)

    evidence = build_parser_validation_evidence(
        parser_version="valprobe-xlsx-parser-v1",
        fixture_manifest_path=files["fixture_manifest"],
        parser_test_report_path=files["parser_test_report"],
        controlled_fixture_report_path=files["controlled_fixture_report"],
        controlled_fixtures_enabled=True,
        reviewer_approved=True,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "passed"
    assert payload["blockers"] == []
    assert payload["parser_version"] == "valprobe-xlsx-parser-v1"
    assert payload["controlled_fixtures_enabled"] is True
    assert payload["reviewer_approved"] is True
    assert {item["key"] for item in payload["evidence_files"]} == set(files)
    assert all(len(item["sha256"]) == 64 for item in payload["evidence_files"])
    assert "unsafe_xml_declaration_rejection" in payload["required_coverage"]


def test_parser_validation_evidence_blocks_without_fixture_run_and_approval(tmp_path):
    files = _evidence_files(tmp_path)

    evidence = build_parser_validation_evidence(
        parser_version="valprobe-xlsx-parser-v1",
        fixture_manifest_path=files["fixture_manifest"],
        parser_test_report_path=files["parser_test_report"],
        controlled_fixture_report_path=files["controlled_fixture_report"],
        controlled_fixtures_enabled=False,
        reviewer_approved=False,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert payload["blockers"] == [
        "controlled_fixture_execution_missing",
        "parser_validation_reviewer_approval_missing",
    ]


def test_parser_validation_evidence_rejects_missing_file(tmp_path):
    files = _evidence_files(tmp_path)

    with pytest.raises(ParserValidationEvidenceError, match="does not exist"):
        build_parser_validation_evidence(
            parser_version="valprobe-xlsx-parser-v1",
            fixture_manifest_path=files["fixture_manifest"],
            parser_test_report_path=tmp_path / "missing.xml",
            controlled_fixture_report_path=files["controlled_fixture_report"],
            controlled_fixtures_enabled=True,
            reviewer_approved=True,
            generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
        )


def test_parser_validation_evidence_rejects_naive_timestamp(tmp_path):
    files = _evidence_files(tmp_path)

    with pytest.raises(ParserValidationEvidenceError, match="timezone-aware"):
        build_parser_validation_evidence(
            parser_version="valprobe-xlsx-parser-v1",
            fixture_manifest_path=files["fixture_manifest"],
            parser_test_report_path=files["parser_test_report"],
            controlled_fixture_report_path=files["controlled_fixture_report"],
            controlled_fixtures_enabled=True,
            reviewer_approved=True,
            generated_at=datetime(2026, 6, 15, 12, 0),
        )


def test_generate_parser_validation_evidence_cli_writes_blocked_output(tmp_path):
    files = _evidence_files(tmp_path)
    output = tmp_path / "valprobe-parser-validation.json"

    result = main(
        [
            "--parser-version",
            "valprobe-xlsx-parser-v1",
            "--fixture-manifest",
            str(files["fixture_manifest"]),
            "--parser-test-report",
            str(files["parser_test_report"]),
            "--controlled-fixture-report",
            str(files["controlled_fixture_report"]),
            "--controlled-fixtures-enabled",
            "false",
            "--generated-at",
            "2026-06-15T12:00:00Z",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result == 2
    assert payload["status"] == "blocked"
    assert "controlled_fixture_execution_missing" in payload["blockers"]


def test_generate_parser_validation_evidence_cli_writes_passed_output(tmp_path):
    files = _evidence_files(tmp_path)
    output = tmp_path / "valprobe-parser-validation.json"

    result = main(
        [
            "--parser-version",
            "valprobe-xlsx-parser-v1",
            "--fixture-manifest",
            str(files["fixture_manifest"]),
            "--parser-test-report",
            str(files["parser_test_report"]),
            "--controlled-fixture-report",
            str(files["controlled_fixture_report"]),
            "--controlled-fixtures-enabled",
            "true",
            "--reviewer-approved",
            "--generated-at",
            "2026-06-15T12:00:00Z",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result == 0
    assert payload["status"] == "passed"
    assert payload["blockers"] == []


def _evidence_files(tmp_path):
    files = {
        "fixture_manifest": tmp_path / "example_files_manifest.json",
        "parser_test_report": tmp_path / "parser-tests.xml",
        "controlled_fixture_report": tmp_path / "controlled-fixtures.xml",
    }
    for key, path in files.items():
        path.write_text(f"{key} evidence", encoding="utf-8")
    return files
