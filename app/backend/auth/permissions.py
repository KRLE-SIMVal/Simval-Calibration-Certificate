"""Role and permission matrix for regulated actions."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    OPERATOR = "operator"
    TECHNICAL_REVIEWER = "technical_reviewer"
    QA_APPROVER = "qa_approver"
    ADMIN = "admin"
    READ_ONLY = "read_only"


class Action(StrEnum):
    CREATE_CALIBRATION_JOB = "create_calibration_job"
    EDIT_DRAFT_JOB_METADATA = "edit_draft_job_metadata"
    SELECT_REFERENCE_EQUIPMENT = "select_reference_equipment"
    UPLOAD_IMPORT_FILE = "upload_import_file"
    ENTER_MANUAL_READINGS = "enter_manual_readings"
    SELECT_MEASUREMENT_WINDOWS = "select_measurement_windows"
    RUN_CALCULATION = "run_calculation"
    PREVIEW_CERTIFICATE = "preview_certificate"
    SUBMIT_TECHNICAL_REVIEW = "submit_technical_review"
    APPROVE_TECHNICAL_REVIEW = "approve_technical_review"
    APPROVE_QA_RELEASE = "approve_qa_release"
    RELEASE_CERTIFICATE = "release_certificate"
    REVISE_RELEASED_CERTIFICATE = "revise_released_certificate"
    VOID_CERTIFICATE = "void_certificate"
    VIEW_AUDIT_TRAIL = "view_audit_trail"
    CREATE_CONSTANTS = "create_constants"
    APPROVE_CONSTANTS = "approve_constants"
    CREATE_UNCERTAINTY_BUDGET = "create_uncertainty_budget"
    APPROVE_UNCERTAINTY_BUDGET = "approve_uncertainty_budget"
    MANAGE_CERTIFICATE_NUMBERS = "manage_certificate_numbers"
    MANAGE_USERS_AND_ROLES = "manage_users_and_roles"
    VIEW_RELEASED_CERTIFICATE = "view_released_certificate"


PERMISSIONS: dict[Role, frozenset[Action]] = {
    Role.OPERATOR: frozenset(
        {
            Action.CREATE_CALIBRATION_JOB,
            Action.EDIT_DRAFT_JOB_METADATA,
            Action.SELECT_REFERENCE_EQUIPMENT,
            Action.UPLOAD_IMPORT_FILE,
            Action.ENTER_MANUAL_READINGS,
            Action.SELECT_MEASUREMENT_WINDOWS,
            Action.RUN_CALCULATION,
            Action.PREVIEW_CERTIFICATE,
            Action.SUBMIT_TECHNICAL_REVIEW,
            Action.VIEW_RELEASED_CERTIFICATE,
        }
    ),
    Role.TECHNICAL_REVIEWER: frozenset(
        {
            Action.CREATE_CALIBRATION_JOB,
            Action.EDIT_DRAFT_JOB_METADATA,
            Action.SELECT_REFERENCE_EQUIPMENT,
            Action.UPLOAD_IMPORT_FILE,
            Action.ENTER_MANUAL_READINGS,
            Action.SELECT_MEASUREMENT_WINDOWS,
            Action.RUN_CALCULATION,
            Action.PREVIEW_CERTIFICATE,
            Action.SUBMIT_TECHNICAL_REVIEW,
            Action.APPROVE_TECHNICAL_REVIEW,
            Action.VIEW_AUDIT_TRAIL,
            Action.CREATE_UNCERTAINTY_BUDGET,
            Action.VIEW_RELEASED_CERTIFICATE,
        }
    ),
    Role.QA_APPROVER: frozenset(
        {
            Action.APPROVE_QA_RELEASE,
            Action.PREVIEW_CERTIFICATE,
            Action.RELEASE_CERTIFICATE,
            Action.REVISE_RELEASED_CERTIFICATE,
            Action.VOID_CERTIFICATE,
            Action.VIEW_AUDIT_TRAIL,
            Action.APPROVE_CONSTANTS,
            Action.APPROVE_UNCERTAINTY_BUDGET,
            Action.VIEW_RELEASED_CERTIFICATE,
        }
    ),
    Role.ADMIN: frozenset(Action),
    Role.READ_ONLY: frozenset({Action.VIEW_RELEASED_CERTIFICATE}),
}


def is_allowed(role: Role, action: Action, *, user_active: bool = True) -> bool:
    """Return whether an active user with role may perform action."""
    if not user_active:
        return False
    return action in PERMISSIONS[role]
