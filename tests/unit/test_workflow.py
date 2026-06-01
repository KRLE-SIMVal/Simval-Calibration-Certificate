import pytest

from app.backend.domain.workflow import (
    RELEASE_BLOCKERS,
    WorkflowState,
    WorkflowTransitionError,
    can_transition,
    require_transition,
)


def test_happy_path_transitions_are_explicit():
    assert can_transition(WorkflowState.DRAFT, WorkflowState.METADATA_COMPLETE)
    assert can_transition(WorkflowState.METADATA_COMPLETE, WorkflowState.EQUIPMENT_SELECTED)
    assert can_transition(WorkflowState.EQUIPMENT_SELECTED, WorkflowState.DATA_ENTERED)
    assert can_transition(WorkflowState.DATA_ENTERED, WorkflowState.WINDOWS_SELECTED)
    assert can_transition(WorkflowState.WINDOWS_SELECTED, WorkflowState.CALCULATED)
    assert can_transition(WorkflowState.CALCULATED, WorkflowState.TECHNICAL_REVIEW)
    assert can_transition(WorkflowState.TECHNICAL_REVIEW, WorkflowState.QA_REVIEW)
    assert can_transition(WorkflowState.QA_REVIEW, WorkflowState.APPROVED)
    assert can_transition(WorkflowState.APPROVED, WorkflowState.RELEASED)


def test_released_certificate_cannot_be_edited_back_to_draft():
    assert not can_transition(WorkflowState.RELEASED, WorkflowState.DRAFT)
    with pytest.raises(WorkflowTransitionError):
        require_transition(WorkflowState.RELEASED, WorkflowState.DRAFT)


def test_released_certificate_can_only_enter_revision_path():
    assert can_transition(WorkflowState.RELEASED, WorkflowState.REVISED)
    assert not can_transition(WorkflowState.RELEASED, WorkflowState.VOIDED)


def test_release_blockers_include_regulated_controls():
    assert "missing_cmc" in RELEASE_BLOCKERS
    assert "equipment_overdue" in RELEASE_BLOCKERS
    assert "reviewer_independence_violation" in RELEASE_BLOCKERS
    assert "certificate_preview_failed" in RELEASE_BLOCKERS

