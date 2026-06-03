from datetime import datetime, timezone

import pytest

from app.backend.audit.events import AuditAction
from app.backend.auth.permissions import Role
from app.backend.certificates.records import ArtifactType
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteCertificateRevisionRepository,
)
from app.backend.services.authentication import AuthenticationServiceError
from app.backend.services.certificates import (
    CertificateRevisionServiceError,
    build_certificate_preview_for_session,
    release_certificate_for_session,
    revise_released_certificate_for_session,
)
from tests.unit.test_certificate_release_service import _connection_with_release_data


def test_revise_released_certificate_for_session_records_revision_and_workflow():
    connection = _released_connection()

    result = revise_released_certificate_for_session(
        connection=connection,
        session_id="qa-session",
        certificate_id="cert-001",
        revision_id="rev-001",
        reason="Corrected customer address after QA approval.",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 45, tzinfo=timezone.utc),
    )

    assert result.revision.original_certificate_id == "cert-001"
    assert result.revision.original_certificate_number == "SIMVAL-CAL-0001"
    assert result.revision.revised_by == "qa-001"
    assert result.revision.reason == "Corrected customer address after QA approval."
    assert result.revision_audit_event.action is AuditAction.CERTIFICATE_REVISED
    assert result.revision_audit_event.reason == result.revision.reason
    assert result.workflow_audit_event.action is AuditAction.WORKFLOW_TRANSITIONED
    assert SQLiteCertificateRevisionRepository(connection).get("rev-001") == (
        result.revision
    )
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.REVISED
    )


def test_revise_released_certificate_for_session_requires_reason():
    connection = _released_connection()

    with pytest.raises(CertificateRevisionServiceError):
        revise_released_certificate_for_session(
            connection=connection,
            session_id="qa-session",
            certificate_id="cert-001",
            revision_id="rev-001",
            reason=" ",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 45, tzinfo=timezone.utc),
        )

    assert SQLiteCertificateRevisionRepository(connection).list_for_original(
        "cert-001"
    ) == ()
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.RELEASED
    )


def test_revise_released_certificate_for_session_requires_released_job_state():
    connection = _connection_with_release_data()

    with pytest.raises(CertificateRevisionServiceError):
        revise_released_certificate_for_session(
            connection=connection,
            session_id="qa-session",
            certificate_id="cert-001",
            revision_id="rev-001",
            reason="Corrected customer address after QA approval.",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 45, tzinfo=timezone.utc),
        )

    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "calibration_job",
        "job-001",
    ) == ()


def test_revise_released_certificate_for_session_rejects_unauthorized_actor():
    connection = _released_connection(actor_roles=(Role.OPERATOR,))

    with pytest.raises(AuthenticationServiceError):
        revise_released_certificate_for_session(
            connection=connection,
            session_id="qa-session",
            certificate_id="cert-001",
            revision_id="rev-001",
            reason="Corrected customer address after QA approval.",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 45, tzinfo=timezone.utc),
        )

    assert SQLiteCertificateRevisionRepository(connection).list_for_original(
        "cert-001"
    ) == ()
    assert SQLiteCalibrationJobRepository(connection).get("job-001").state is (
        WorkflowState.RELEASED
    )


def _released_connection(
    *,
    actor_roles: tuple[Role, ...] = (Role.QA_APPROVER,),
):
    connection = _connection_with_release_data(actor_roles=(Role.QA_APPROVER,))
    build_certificate_preview_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
    )
    release_certificate_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        certificate_id="cert-001",
        certificate_number="SIMVAL-CAL-0001",
        artifact_id="artifact-001",
        artifact_type=ArtifactType.PDF,
        filename="SIMVAL-CAL-0001.pdf",
        checksum_sha256="b" * 64,
        storage_uri="controlled-local://SIMVAL-CAL-0001.pdf",
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
    )
    if actor_roles != (Role.QA_APPROVER,):
        role_values = ",".join(f'"{role.value}"' for role in actor_roles)
        connection.execute(
            "UPDATE user_accounts SET roles_json = ? WHERE id = ?",
            (f"[{role_values}]", "qa-001"),
        )
        connection.commit()
    return connection
