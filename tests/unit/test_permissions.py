from app.backend.auth.permissions import Action, Role, is_allowed


def test_operator_can_create_and_calculate_but_not_release():
    assert is_allowed(Role.OPERATOR, Action.CREATE_CALIBRATION_JOB)
    assert is_allowed(Role.OPERATOR, Action.RUN_CALCULATION)
    assert is_allowed(Role.OPERATOR, Action.PREVIEW_CERTIFICATE)
    assert not is_allowed(Role.OPERATOR, Action.RELEASE_CERTIFICATE)


def test_qa_approver_can_release_but_not_edit_measurements():
    assert is_allowed(Role.QA_APPROVER, Action.RELEASE_CERTIFICATE)
    assert is_allowed(Role.QA_APPROVER, Action.APPROVE_QA_RELEASE)
    assert is_allowed(Role.QA_APPROVER, Action.PREVIEW_CERTIFICATE)
    assert not is_allowed(Role.QA_APPROVER, Action.ENTER_MANUAL_READINGS)


def test_admin_can_manage_users_and_constants():
    assert is_allowed(Role.ADMIN, Action.MANAGE_USERS_AND_ROLES)
    assert is_allowed(Role.ADMIN, Action.CREATE_CONSTANTS)
    assert is_allowed(Role.ADMIN, Action.APPROVE_CONSTANTS)


def test_read_only_has_limited_access():
    assert is_allowed(Role.READ_ONLY, Action.VIEW_RELEASED_CERTIFICATE)
    assert not is_allowed(Role.READ_ONLY, Action.VIEW_AUDIT_TRAIL)
    assert not is_allowed(Role.READ_ONLY, Action.CREATE_CALIBRATION_JOB)


def test_inactive_user_cannot_perform_regulated_action():
    assert not is_allowed(
        Role.ADMIN, Action.MANAGE_USERS_AND_ROLES, user_active=False
    )
