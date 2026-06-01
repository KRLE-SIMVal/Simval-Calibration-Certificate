"""Workflow state rules for calibration jobs."""

from __future__ import annotations

from enum import StrEnum


class WorkflowState(StrEnum):
    DRAFT = "draft"
    METADATA_COMPLETE = "metadata_complete"
    EQUIPMENT_SELECTED = "equipment_selected"
    DATA_ENTERED = "data_entered"
    WINDOWS_SELECTED = "windows_selected"
    CALCULATED = "calculated"
    TECHNICAL_REVIEW = "technical_review"
    QA_REVIEW = "qa_review"
    APPROVED = "approved"
    RELEASED = "released"
    REVISED = "revised"
    VOIDED = "voided"


ALLOWED_TRANSITIONS: dict[WorkflowState, frozenset[WorkflowState]] = {
    WorkflowState.DRAFT: frozenset(
        {WorkflowState.METADATA_COMPLETE, WorkflowState.VOIDED}
    ),
    WorkflowState.METADATA_COMPLETE: frozenset(
        {WorkflowState.EQUIPMENT_SELECTED, WorkflowState.VOIDED}
    ),
    WorkflowState.EQUIPMENT_SELECTED: frozenset(
        {WorkflowState.DATA_ENTERED, WorkflowState.VOIDED}
    ),
    WorkflowState.DATA_ENTERED: frozenset(
        {WorkflowState.WINDOWS_SELECTED, WorkflowState.VOIDED}
    ),
    WorkflowState.WINDOWS_SELECTED: frozenset(
        {WorkflowState.CALCULATED, WorkflowState.VOIDED}
    ),
    WorkflowState.CALCULATED: frozenset(
        {WorkflowState.TECHNICAL_REVIEW, WorkflowState.VOIDED}
    ),
    WorkflowState.TECHNICAL_REVIEW: frozenset(
        {WorkflowState.QA_REVIEW, WorkflowState.VOIDED}
    ),
    WorkflowState.QA_REVIEW: frozenset(
        {WorkflowState.APPROVED, WorkflowState.VOIDED}
    ),
    WorkflowState.APPROVED: frozenset(
        {WorkflowState.RELEASED, WorkflowState.VOIDED}
    ),
    WorkflowState.RELEASED: frozenset({WorkflowState.REVISED}),
    WorkflowState.REVISED: frozenset({WorkflowState.VOIDED}),
    WorkflowState.VOIDED: frozenset(),
}


class WorkflowTransitionError(ValueError):
    """Raised when a requested workflow transition is not allowed."""


def can_transition(current: WorkflowState, target: WorkflowState) -> bool:
    """Return whether a workflow transition is allowed."""
    return target in ALLOWED_TRANSITIONS[current]


def require_transition(current: WorkflowState, target: WorkflowState) -> WorkflowState:
    """Return target when allowed, otherwise raise a domain error."""
    if not can_transition(current, target):
        raise WorkflowTransitionError(
            f"Cannot transition calibration job from {current} to {target}."
        )
    return target


RELEASE_BLOCKERS: frozenset[str] = frozenset(
    {
        "missing_metadata",
        "missing_reference_equipment",
        "equipment_overdue",
        "equipment_inactive",
        "equipment_out_of_range",
        "missing_cmc",
        "cmc_out_of_range",
        "blocking_calculation_warning",
        "missing_approved_uncertainty_budget",
        "reviewer_independence_violation",
        "missing_audit_reason",
        "certificate_preview_failed",
    }
)

