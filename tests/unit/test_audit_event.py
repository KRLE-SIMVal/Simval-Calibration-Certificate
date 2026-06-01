from datetime import datetime, timezone

import pytest

from app.backend.audit.events import AuditAction, AuditEvent


def test_audit_event_requires_timezone_aware_timestamp():
    with pytest.raises(ValueError):
        AuditEvent(
            entity_type="CalibrationJob",
            entity_id="job-1",
            action=AuditAction.JOB_CREATED,
            user_id="user-1",
            timestamp=datetime(2026, 6, 1),
        )


def test_audit_event_freezes_value_snapshots():
    previous = {"status": "draft"}
    event = AuditEvent(
        entity_type="CalibrationJob",
        entity_id="job-1",
        action=AuditAction.METADATA_CHANGED,
        user_id="user-1",
        timestamp=datetime(2026, 6, 1, tzinfo=timezone.utc),
        previous_value=previous,
        new_value={"status": "metadata_complete"},
        reason="P1 test",
    )
    previous["status"] = "changed-later"
    assert event.previous_value["status"] == "draft"
    with pytest.raises(TypeError):
        event.previous_value["status"] = "mutated"


def test_audit_event_rejects_blank_reason():
    with pytest.raises(ValueError):
        AuditEvent(
            entity_type="Certificate",
            entity_id="cert-1",
            action=AuditAction.CERTIFICATE_VOIDED,
            user_id="qa-1",
            timestamp=datetime(2026, 6, 1, tzinfo=timezone.utc),
            reason=" ",
        )

