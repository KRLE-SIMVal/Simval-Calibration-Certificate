"""Reviewer independence checks from retained job audit evidence."""

from __future__ import annotations

from enum import StrEnum
import sqlite3

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.persistence.sqlite import SQLiteAuditEventRepository


class ReviewerIndependenceStage(StrEnum):
    TECHNICAL_REVIEW_APPROVAL = "technical_review_approval"
    QA_RELEASE_APPROVAL = "qa_release_approval"
    CERTIFICATE_RELEASE = "certificate_release"


class ReviewerIndependenceError(ValueError):
    """Raised when one user attempts incompatible regulated workflow stages."""


PREPARATION_AND_CALCULATION_ACTIONS: frozenset[AuditAction] = frozenset(
    {
        AuditAction.JOB_CREATED,
        AuditAction.METADATA_CHANGED,
        AuditAction.FILE_UPLOADED,
        AuditAction.PARSER_RESULT_RECORDED,
        AuditAction.IMPORT_ALIGNMENT_RECORDED,
        AuditAction.DATA_ENTRY_RECORDED,
        AuditAction.MANUAL_IRTD_TABLE_RECORDED,
        AuditAction.MANUAL_READING_CHANGED,
        AuditAction.REFERENCE_EQUIPMENT_SELECTED,
        AuditAction.MEASUREMENT_WINDOW_CHANGED,
        AuditAction.CALCULATION_RUN,
    }
)


WORKFLOW_STATE_CONFLICTS: dict[ReviewerIndependenceStage, frozenset[str]] = {
    ReviewerIndependenceStage.TECHNICAL_REVIEW_APPROVAL: frozenset(
        {"technical_review"}
    ),
    ReviewerIndependenceStage.QA_RELEASE_APPROVAL: frozenset(
        {"technical_review", "qa_review"}
    ),
    ReviewerIndependenceStage.CERTIFICATE_RELEASE: frozenset(
        {"technical_review", "qa_review", "approved"}
    ),
}


def assert_reviewer_independence(
    *,
    connection: sqlite3.Connection,
    job_id: str,
    user_id: str,
    stage: ReviewerIndependenceStage,
) -> None:
    """Reject same-user preparation, review, approval, and release conflicts."""
    _require_text(job_id, "Job id")
    _require_text(user_id, "User id")
    if not isinstance(stage, ReviewerIndependenceStage):
        raise ReviewerIndependenceError("Reviewer independence stage is invalid.")

    events = SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        job_id,
    )
    conflict = _first_conflict_for_user(
        events=events,
        user_id=user_id,
        stage=stage,
    )
    if conflict is not None:
        raise ReviewerIndependenceError(
            "reviewer_independence_violation: user already performed "
            f"{conflict} for calibration job {job_id}."
        )


def _first_conflict_for_user(
    *,
    events: tuple[AuditEvent, ...],
    user_id: str,
    stage: ReviewerIndependenceStage,
) -> str | None:
    for event in events:
        if event.user_id != user_id:
            continue
        if event.action in PREPARATION_AND_CALCULATION_ACTIONS:
            return event.action.value
        if event.action is AuditAction.WORKFLOW_TRANSITIONED:
            target_state = _workflow_target_state(event)
            if target_state in WORKFLOW_STATE_CONFLICTS[stage]:
                return f"workflow transition to {target_state}"
    return None


def _workflow_target_state(event: AuditEvent) -> str | None:
    if event.new_value is None:
        return None
    value = event.new_value.get("state")
    if not isinstance(value, str) or value.strip() == "":
        return None
    return value


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise ReviewerIndependenceError(f"{field_name} is required.")
