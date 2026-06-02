from datetime import datetime, timezone

import pytest

from app.backend.auth.permissions import Action, Role
from app.backend.auth.users import UserAccount, UserIdentityError, UserSession


def test_user_account_allows_action_when_any_assigned_role_allows_it():
    user = UserAccount(
        id="user-001",
        display_name="Kristian Leth",
        email="KRLE@example.com",
        roles=(Role.OPERATOR, Role.QA_APPROVER),
        active=True,
        signature_label="KRLE",
        created_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
    )

    assert user.email == "krle@example.com"
    assert user.can_perform(Action.RUN_CALCULATION)
    assert user.can_perform(Action.RELEASE_CERTIFICATE)


def test_inactive_user_account_cannot_perform_regulated_action():
    user = UserAccount(
        id="user-001",
        display_name="Inactive User",
        email="inactive@example.com",
        roles=(Role.ADMIN,),
        active=False,
        created_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
    )

    assert not user.can_perform(Action.MANAGE_USERS_AND_ROLES)


def test_user_account_rejects_missing_or_duplicate_roles():
    with pytest.raises(UserIdentityError):
        UserAccount(
            id="user-001",
            display_name="No Role",
            email="norole@example.com",
            roles=(),
        )

    with pytest.raises(UserIdentityError):
        UserAccount(
            id="user-001",
            display_name="Duplicate Role",
            email="duplicate@example.com",
            roles=(Role.OPERATOR, Role.OPERATOR),
        )


def test_user_account_rejects_invalid_email_and_naive_timestamp():
    with pytest.raises(UserIdentityError):
        UserAccount(
            id="user-001",
            display_name="Bad Email",
            email="bad-email",
            roles=(Role.OPERATOR,),
        )

    with pytest.raises(UserIdentityError):
        UserAccount(
            id="user-001",
            display_name="Naive Timestamp",
            email="naive@example.com",
            roles=(Role.OPERATOR,),
            created_at=datetime(2026, 6, 1, 8, 0),
        )


def test_user_session_is_active_only_inside_valid_unrevoked_interval():
    session = UserSession(
        id="session-001",
        user_id="user-001",
        issued_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
    )

    assert not session.active_at(datetime(2026, 6, 1, 7, 59, tzinfo=timezone.utc))
    assert session.active_at(datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc))
    assert not session.active_at(datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc))


def test_user_session_rejects_invalid_dates():
    with pytest.raises(UserIdentityError):
        UserSession(
            id="session-001",
            user_id="user-001",
            issued_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
            expires_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        )

    with pytest.raises(UserIdentityError):
        UserSession(
            id="session-001",
            user_id="user-001",
            issued_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
            expires_at=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
            revoked_at=datetime(2026, 6, 1, 7, 59, tzinfo=timezone.utc),
        )


def test_revoked_user_session_is_not_active():
    session = UserSession(
        id="session-001",
        user_id="user-001",
        issued_at=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
        revoked_at=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
    )

    assert not session.active_at(datetime(2026, 6, 1, 12, 1, tzinfo=timezone.utc))
