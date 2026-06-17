import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.backend.validation.pilot import (
    PilotValidationPlanError,
    build_pilot_validation_plan,
    pilot_evidence_paths_by_stage,
    required_pilot_evidence_keys,
    write_pilot_validation_plan,
)
from scripts.validation.generate_pilot_validation_plan import main
from scripts.validation.generate_pilot_validation_package import (
    main as package_main,
)


def test_pilot_validation_plan_maps_controlled_activities_to_evidence_keys():
    plan = build_pilot_validation_plan(
        release_version="v0.9.0-pilot",
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(plan.to_json())
    evidence_keys = {
        activity["required_evidence_key"] for activity in payload["activities"]
    }

    assert payload["status"] == "draft_pending_review"
    assert payload["scope"] == "temperature-only controlled validation pilot"
    assert payload["release_version"] == "v0.9.0-pilot"
    assert payload["generated_at"] == "2026-06-15T12:00:00+00:00"
    assert evidence_keys == {
        "runtime_profile",
        "smoke_evidence",
        "valprobe_parser_validation",
        "reviewer_independence",
        "backup_restore",
    }
    assert {activity["stage"] for activity in payload["activities"]} == {
        "IQ",
        "OQ",
        "PQ",
    }
    assert "QA/Compliance Reviewer" in payload["required_reviewers"]


def test_pilot_validation_plan_markdown_contains_stop_rule():
    plan = build_pilot_validation_plan(
        release_version="v0.9.0-pilot",
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    markdown = plan.to_markdown()

    assert "# SIMVal Controlled Pilot Validation Plan" in markdown
    assert "PILOT-OQ-002" in markdown
    assert "`valprobe_parser_validation`" in markdown
    assert "Routine production use remains blocked" in markdown


def test_pilot_validation_plan_rejects_naive_timestamp():
    with pytest.raises(PilotValidationPlanError, match="timezone-aware"):
        build_pilot_validation_plan(
            release_version="v0.9.0-pilot",
            generated_at=datetime(2026, 6, 15, 12, 0),
        )


def test_pilot_validation_plan_cli_writes_json_and_markdown(tmp_path):
    output_dir = tmp_path / "pilot-plan"

    result = main(
        [
            "--release-version",
            "v0.9.0-pilot",
            "--generated-at",
            "2026-06-15T12:00:00Z",
            "--output-dir",
            str(output_dir),
        ]
    )

    payload = json.loads(
        (output_dir / "pilot-validation-plan.json").read_text(encoding="utf-8")
    )
    markdown = (output_dir / "pilot-validation-plan.md").read_text(encoding="utf-8")

    assert result == 0
    assert payload["release_version"] == "v0.9.0-pilot"
    assert payload["activities"][0]["activity_id"] == "PILOT-IQ-001"
    assert markdown.startswith("# SIMVal Controlled Pilot Validation Plan")


def test_write_pilot_validation_plan_creates_package_files(tmp_path):
    plan = build_pilot_validation_plan(
        release_version="v0.9.0-pilot",
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    write_pilot_validation_plan(plan, tmp_path)

    assert (tmp_path / "pilot-validation-plan.json").is_file()
    assert (tmp_path / "pilot-validation-plan.md").is_file()


def test_pilot_evidence_paths_by_stage_maps_required_keys():
    references = {
        key: Path(f"evidence/{key}.json")
        for key in required_pilot_evidence_keys()
    }

    paths_by_stage = pilot_evidence_paths_by_stage(references)

    assert [path.name for path in paths_by_stage["IQ"]] == [
        "runtime_profile.json"
    ]
    assert [path.name for path in paths_by_stage["OQ"]] == [
        "smoke_evidence.json",
        "valprobe_parser_validation.json",
    ]
    assert [path.name for path in paths_by_stage["PQ"]] == [
        "reviewer_independence.json",
        "backup_restore.json",
    ]


def test_pilot_evidence_paths_by_stage_rejects_missing_key():
    references = {
        key: Path(f"evidence/{key}.json")
        for key in required_pilot_evidence_keys()
        if key != "backup_restore"
    }

    with pytest.raises(PilotValidationPlanError, match="backup_restore"):
        pilot_evidence_paths_by_stage(references)


def test_generate_pilot_validation_package_cli_writes_standard_package(tmp_path):
    plan_dir = tmp_path / "pilot-plan"
    main(
        [
            "--release-version",
            "v0.9.0-pilot",
            "--generated-at",
            "2026-06-15T12:00:00Z",
            "--output-dir",
            str(plan_dir),
        ]
    )
    evidence_files = {
        key: tmp_path / f"{key}.json"
        for key in required_pilot_evidence_keys()
    }
    for key, path in evidence_files.items():
        path.write_text(f"{key} evidence", encoding="utf-8")
    output_dir = tmp_path / "pilot-package"

    result = package_main(
        [
            "--release-version",
            "v0.9.0-pilot",
            "--source-commit",
            "abcdef123456",
            "--pilot-plan",
            str(plan_dir / "pilot-validation-plan.json"),
            *[
                value
                for key, path in evidence_files.items()
                for value in ("--evidence", f"{key}={path}")
            ],
            "--output-dir",
            str(output_dir),
        ]
    )

    payload = json.loads(
        (output_dir / "validation-package.json").read_text(encoding="utf-8")
    )

    assert result == 0
    assert payload["objective"] == "Controlled pilot validation package"
    assert payload["release_version"] == "v0.9.0-pilot"
    assert [item["path"] for item in payload["iq_evidence"]][0].endswith(
        "pilot-validation-plan.json"
    )
    assert len(payload["oq_evidence"]) == 2
    assert len(payload["pq_evidence"]) == 2
    assert payload["known_limitations"][0].startswith("Routine production remains blocked")
