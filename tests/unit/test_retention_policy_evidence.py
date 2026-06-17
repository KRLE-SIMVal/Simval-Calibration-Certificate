import json
from datetime import datetime, timezone

import pytest

from app.backend.validation.retention_policy import (
    REQUIRED_RETENTION_CATEGORIES,
    RetentionPolicyEvidenceError,
    build_retention_policy_evidence,
)
from scripts.validation.generate_retention_policy_evidence import main


def test_retention_policy_evidence_passes_for_complete_reviewed_policy(tmp_path):
    policy = _retention_policy(tmp_path)

    evidence = build_retention_policy_evidence(
        policy_path=policy,
        reviewer_approved=True,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "passed"
    assert payload["blockers"] == []
    assert payload["required_categories"] == list(REQUIRED_RETENTION_CATEGORIES)
    assert payload["missing_categories"] == []
    assert payload["incomplete_categories"] == []
    assert payload["reviewer_approved"] is True
    assert payload["category_coverage"][0]["missing_required_fields"] == []
    assert payload["evidence_files"][0]["path"] == "retention-policy.json"
    assert "controlled SIMVal evidence store" not in evidence.to_json()


def test_retention_policy_evidence_blocks_missing_required_category(tmp_path):
    policy = _retention_policy(tmp_path, remove_category="audit_events")

    evidence = build_retention_policy_evidence(
        policy_path=policy,
        reviewer_approved=True,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert payload["missing_categories"] == ["audit_events"]
    assert "retention_policy_required_categories_missing" in payload["blockers"]


def test_retention_policy_evidence_blocks_incomplete_required_category(tmp_path):
    policy = _retention_policy(
        tmp_path,
        incomplete_category="database_backups",
        incomplete_field="owner_role",
    )

    evidence = build_retention_policy_evidence(
        policy_path=policy,
        reviewer_approved=True,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert payload["incomplete_categories"] == ["database_backups"]
    assert "retention_policy_required_categories_incomplete" in payload["blockers"]


def test_retention_policy_evidence_blocks_missing_reviewer_approval(tmp_path):
    policy = _retention_policy(tmp_path)

    evidence = build_retention_policy_evidence(
        policy_path=policy,
        reviewer_approved=False,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["retention_policy_reviewer_approval_missing"]


def test_retention_policy_evidence_rejects_invalid_json(tmp_path):
    policy = tmp_path / "retention-policy.json"
    policy.write_text("not-json", encoding="utf-8")

    with pytest.raises(RetentionPolicyEvidenceError, match="not valid JSON"):
        build_retention_policy_evidence(
            policy_path=policy,
            reviewer_approved=True,
            generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
        )


def test_retention_policy_evidence_rejects_naive_timestamp(tmp_path):
    policy = _retention_policy(tmp_path)

    with pytest.raises(RetentionPolicyEvidenceError, match="timezone-aware"):
        build_retention_policy_evidence(
            policy_path=policy,
            reviewer_approved=True,
            generated_at=datetime(2026, 6, 15, 12, 0),
        )


def test_generate_retention_policy_evidence_cli_writes_passed_output(tmp_path):
    policy = _retention_policy(tmp_path)
    output = tmp_path / "retention-evidence.json"

    result = main(
        [
            "--policy-file",
            str(policy),
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


def test_generate_retention_policy_evidence_cli_returns_two_when_blocked(
    tmp_path,
):
    policy = _retention_policy(tmp_path, remove_category="certificates")
    output = tmp_path / "retention-evidence.json"

    result = main(
        [
            "--policy-file",
            str(policy),
            "--generated-at",
            "2026-06-15T12:00:00Z",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result == 2
    assert payload["status"] == "blocked"
    assert payload["blockers"] == [
        "retention_policy_required_categories_missing",
        "retention_policy_reviewer_approval_missing",
    ]


def _retention_policy(
    tmp_path,
    *,
    remove_category: str | None = None,
    incomplete_category: str | None = None,
    incomplete_field: str | None = None,
):
    payload = {
        category: {
            "retention_period": "10 years",
            "owner_role": "QA/Laboratory reviewer",
            "storage_location_type": "controlled SIMVal evidence store",
        }
        for category in REQUIRED_RETENTION_CATEGORIES
    }
    if remove_category is not None:
        payload.pop(remove_category)
    if incomplete_category is not None and incomplete_field is not None:
        payload[incomplete_category][incomplete_field] = ""
    path = tmp_path / "retention-policy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
