import json
from datetime import datetime, timezone

import pytest

from app.backend.validation.reviewer_independence import (
    ReviewerIndependenceEvidenceError,
    build_reviewer_independence_evidence,
)
from scripts.validation.generate_reviewer_independence_evidence import main


def test_reviewer_independence_evidence_passes_for_distinct_roles_and_review(
    tmp_path,
):
    workflow = _workflow_evidence(tmp_path)

    evidence = build_reviewer_independence_evidence(
        workflow_evidence_path=workflow,
        operator_user="operator@example.com",
        technical_reviewer_user="reviewer@example.com",
        qa_approver_user="qa@example.com",
        release_user="release@example.com",
        blocked_same_user_attempts=2,
        reviewer_approved=True,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "passed"
    assert payload["blockers"] == []
    assert payload["distinct_actor_count"] == 4
    assert payload["blocked_same_user_attempts"] == 2
    assert payload["reviewer_approved"] is True
    assert set(payload["role_actor_digests"]) == {
        "operator",
        "technical_reviewer",
        "qa_approver",
        "release_actor",
    }
    assert "operator@example.com" not in evidence.to_json()
    assert payload["evidence_files"][0]["path"] == "workflow-evidence.json"


def test_reviewer_independence_evidence_blocks_reused_actor(tmp_path):
    workflow = _workflow_evidence(tmp_path)

    evidence = build_reviewer_independence_evidence(
        workflow_evidence_path=workflow,
        operator_user="operator@example.com",
        technical_reviewer_user="reviewer@example.com",
        qa_approver_user="qa@example.com",
        release_user="qa@example.com",
        blocked_same_user_attempts=1,
        reviewer_approved=True,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert "regulated_roles_not_independent" in payload["blockers"]


def test_reviewer_independence_evidence_blocks_missing_same_user_block_or_deviation(
    tmp_path,
):
    workflow = _workflow_evidence(tmp_path)

    evidence = build_reviewer_independence_evidence(
        workflow_evidence_path=workflow,
        operator_user="operator@example.com",
        technical_reviewer_user="reviewer@example.com",
        qa_approver_user="qa@example.com",
        release_user="release@example.com",
        blocked_same_user_attempts=0,
        reviewer_approved=True,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    payload = json.loads(evidence.to_json())

    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["same_user_block_evidence_missing"]


def test_reviewer_independence_evidence_allows_controlled_deviation_for_block_test(
    tmp_path,
):
    workflow = _workflow_evidence(tmp_path)

    evidence = build_reviewer_independence_evidence(
        workflow_evidence_path=workflow,
        operator_user="operator@example.com",
        technical_reviewer_user="reviewer@example.com",
        qa_approver_user="qa@example.com",
        release_user="release@example.com",
        blocked_same_user_attempts=0,
        controlled_deviation_approved=True,
        reviewer_approved=True,
        generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    assert json.loads(evidence.to_json())["status"] == "passed"


def test_reviewer_independence_evidence_rejects_missing_workflow_file(tmp_path):
    with pytest.raises(ReviewerIndependenceEvidenceError, match="does not exist"):
        build_reviewer_independence_evidence(
            workflow_evidence_path=tmp_path / "missing.json",
            operator_user="operator@example.com",
            technical_reviewer_user="reviewer@example.com",
            qa_approver_user="qa@example.com",
            release_user="release@example.com",
            blocked_same_user_attempts=1,
            reviewer_approved=True,
            generated_at=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
        )


def test_reviewer_independence_evidence_rejects_naive_timestamp(tmp_path):
    workflow = _workflow_evidence(tmp_path)

    with pytest.raises(ReviewerIndependenceEvidenceError, match="timezone-aware"):
        build_reviewer_independence_evidence(
            workflow_evidence_path=workflow,
            operator_user="operator@example.com",
            technical_reviewer_user="reviewer@example.com",
            qa_approver_user="qa@example.com",
            release_user="release@example.com",
            blocked_same_user_attempts=1,
            reviewer_approved=True,
            generated_at=datetime(2026, 6, 15, 12, 0),
        )


def test_generate_reviewer_independence_evidence_cli_writes_passed_output(tmp_path):
    workflow = _workflow_evidence(tmp_path)
    output = tmp_path / "reviewer-independence.json"

    result = main(
        [
            "--workflow-evidence",
            str(workflow),
            "--operator-user",
            "operator@example.com",
            "--technical-reviewer-user",
            "reviewer@example.com",
            "--qa-approver-user",
            "qa@example.com",
            "--release-user",
            "release@example.com",
            "--blocked-same-user-attempts",
            "1",
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


def test_generate_reviewer_independence_evidence_cli_returns_two_when_blocked(
    tmp_path,
):
    workflow = _workflow_evidence(tmp_path)
    output = tmp_path / "reviewer-independence.json"

    result = main(
        [
            "--workflow-evidence",
            str(workflow),
            "--operator-user",
            "operator@example.com",
            "--technical-reviewer-user",
            "reviewer@example.com",
            "--qa-approver-user",
            "qa@example.com",
            "--release-user",
            "release@example.com",
            "--blocked-same-user-attempts",
            "1",
            "--generated-at",
            "2026-06-15T12:00:00Z",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result == 2
    assert payload["blockers"] == ["reviewer_independence_approval_missing"]


def _workflow_evidence(tmp_path):
    path = tmp_path / "workflow-evidence.json"
    path.write_text('{"status":"passed"}', encoding="utf-8")
    return path
