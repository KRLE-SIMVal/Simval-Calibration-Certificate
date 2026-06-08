from datetime import datetime, timezone

import pytest

from app.backend.auth.permissions import Role
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    SQLiteAuditEventRepository,
    SQLiteCertificateNumberAllocator,
    SQLiteCertificateRecordRepository,
)
from app.backend.certificates.template_contract import CertificateTemplateContractError
from app.backend.services.authentication import AuthenticationServiceError
from app.backend.services.certificates import (
    CertificateReleaseServiceError,
    build_certificate_preview_for_session,
    render_and_release_certificate_pdf_with_allocated_number_for_session,
    render_and_release_certificate_pdf_for_session,
)
from tests.unit.test_certificate_release_service import _connection_with_release_data
from tests.unit.test_sqlite_certificate_persistence import (
    _certificate as _persisted_certificate,
)


def test_render_and_release_certificate_pdf_for_session_uses_generated_artifact(tmp_path):
    connection = _connection_with_release_data()
    build_certificate_preview_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
    )

    result = render_and_release_certificate_pdf_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        certificate_id="cert-001",
        certificate_number="SIMVAL-CAL-0001",
        artifact_id="artifact-001",
        artifact_directory=tmp_path,
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
    )

    stored_path = tmp_path / "SIMVAL-CAL-0001.pdf"
    assert stored_path.read_bytes() == result.rendered_artifact.content_bytes
    assert result.stored_artifact.checksum_sha256 == (
        result.rendered_artifact.checksum_sha256
    )
    assert result.release.certificate.primary_artifact.checksum_sha256 == (
        result.rendered_artifact.checksum_sha256
    )
    assert result.release.certificate.primary_artifact.storage_uri == (
        "controlled-local://SIMVAL-CAL-0001.pdf"
    )
    assert SQLiteCertificateRecordRepository(connection).get("cert-001") == (
        result.release.certificate
    )


def test_render_and_release_certificate_pdf_for_session_can_suppress_danak_mark(
    tmp_path,
):
    connection = _connection_with_release_data()
    build_certificate_preview_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
        accreditation_mark_allowed=False,
    )

    result = render_and_release_certificate_pdf_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        certificate_id="cert-001",
        certificate_number="SIMVAL-CAL-0001",
        artifact_id="artifact-001",
        artifact_directory=tmp_path,
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        accreditation_mark_allowed=False,
    )

    content_text = result.rendered_artifact.content_bytes.decode("latin-1")
    assert result.release.accreditation_mark_allowed is False
    assert "/ImSimval" in content_text
    assert "/ImDanak" not in content_text
    assert "Accreditation mark: not applied for this certificate scope." in (
        content_text
    )


def test_render_and_release_certificate_pdf_with_allocated_number_uses_sequence(
    tmp_path,
):
    connection = _connection_with_release_data()
    SQLiteCertificateNumberAllocator(connection).create_sequence(
        prefix="SIMVAL-CAL",
        next_value=7,
    )
    build_certificate_preview_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
    )

    result = render_and_release_certificate_pdf_with_allocated_number_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        certificate_id="cert-001",
        certificate_number_prefix="SIMVAL-CAL",
        certificate_number_padding=4,
        artifact_id="artifact-001",
        artifact_directory=tmp_path,
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
    )

    assert result.certificate_number_allocation.certificate_number == (
        "SIMVAL-CAL-0007"
    )
    assert result.certificate_number_allocation.next_value_after == 8
    assert SQLiteCertificateNumberAllocator(connection).next_value("SIMVAL-CAL") == 8
    assert (tmp_path / "SIMVAL-CAL-0007.pdf").exists()
    assert result.release.certificate.certificate_number == "SIMVAL-CAL-0007"
    assert result.release.certificate.released_by == "qa-001"
    event = SQLiteAuditEventRepository(connection).list_for_entity(
        "certificate_number",
        "SIMVAL-CAL-0007",
    )[0]
    assert event.user_id == "qa-001"
    assert event.new_value == {
        "prefix": "SIMVAL-CAL",
        "certificate_number": "SIMVAL-CAL-0007",
        "next_value_after": 8,
        "context": {
            "job_id": "job-001",
            "certificate_id": "cert-001",
            "operation": "rendered_certificate_release",
        },
    }


def test_allocated_number_release_rolls_back_sequence_on_template_failure(
    tmp_path,
    monkeypatch,
):
    connection = _connection_with_release_data()
    SQLiteCertificateNumberAllocator(connection).create_sequence(
        prefix="SIMVAL-CAL",
        next_value=7,
    )
    build_certificate_preview_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
    )

    def fail_template_contract(**_kwargs):
        raise CertificateTemplateContractError("template contract failed")

    monkeypatch.setattr(
        "app.backend.services.certificates.validate_certificate_template_contract",
        fail_template_contract,
    )

    with pytest.raises(CertificateReleaseServiceError, match="template contract"):
        render_and_release_certificate_pdf_with_allocated_number_for_session(
            connection=connection,
            session_id="qa-session",
            job_id="job-001",
            certificate_id="cert-001",
            certificate_number_prefix="SIMVAL-CAL",
            certificate_number_padding=4,
            artifact_id="artifact-001",
            artifact_directory=tmp_path,
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert SQLiteCertificateNumberAllocator(connection).next_value("SIMVAL-CAL") == 7
    assert SQLiteAuditEventRepository(connection).list_for_entity(
        "certificate_number",
        "SIMVAL-CAL-0007",
    ) == ()
    assert not (tmp_path / "SIMVAL-CAL-0007.pdf").exists()
    assert not (tmp_path / ".SIMVAL-CAL-0007.pdf.pending").exists()


def test_render_and_release_certificate_pdf_blocks_missing_preview_before_file_write(
    tmp_path,
):
    connection = _connection_with_release_data()

    with pytest.raises(CertificateReleaseServiceError):
        render_and_release_certificate_pdf_for_session(
            connection=connection,
            session_id="qa-session",
            job_id="job-001",
            certificate_id="cert-001",
            certificate_number="SIMVAL-CAL-0001",
            artifact_id="artifact-001",
            artifact_directory=tmp_path,
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert not (tmp_path / "SIMVAL-CAL-0001.pdf").exists()
    assert SQLiteCertificateRecordRepository(connection).list_for_job("job-001") == ()


def test_render_and_release_certificate_pdf_blocks_template_contract_failure_before_file_write(
    tmp_path,
    monkeypatch,
):
    connection = _connection_with_release_data()
    build_certificate_preview_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
    )

    def fail_template_contract(**_kwargs):
        raise CertificateTemplateContractError("template contract failed")

    monkeypatch.setattr(
        "app.backend.services.certificates.validate_certificate_template_contract",
        fail_template_contract,
    )

    with pytest.raises(CertificateReleaseServiceError, match="template contract"):
        render_and_release_certificate_pdf_for_session(
            connection=connection,
            session_id="qa-session",
            job_id="job-001",
            certificate_id="cert-001",
            certificate_number="SIMVAL-CAL-0001",
            artifact_id="artifact-001",
            artifact_directory=tmp_path,
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert not (tmp_path / "SIMVAL-CAL-0001.pdf").exists()
    assert not (tmp_path / ".SIMVAL-CAL-0001.pdf.pending").exists()
    assert SQLiteCertificateRecordRepository(connection).list_for_job("job-001") == ()


def test_render_and_release_certificate_pdf_discards_pending_file_on_release_failure(
    tmp_path,
):
    connection = _connection_with_release_data()
    build_certificate_preview_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
    )
    SQLiteCertificateRecordRepository(connection).add(_persisted_certificate())

    with pytest.raises(CertificateReleaseServiceError):
        render_and_release_certificate_pdf_for_session(
            connection=connection,
            session_id="qa-session",
            job_id="job-001",
            certificate_id="cert-001",
            certificate_number="SIMVAL-CAL-0001",
            artifact_id="artifact-001",
            artifact_directory=tmp_path,
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert not (tmp_path / "SIMVAL-CAL-0001.pdf").exists()
    assert not (tmp_path / ".SIMVAL-CAL-0001.pdf.pending").exists()


def test_render_and_release_certificate_pdf_blocks_unauthorized_actor_before_file_write(
    tmp_path,
):
    connection = _connection_with_release_data(actor_roles=(Role.OPERATOR,))
    build_certificate_preview_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
    )

    with pytest.raises(AuthenticationServiceError):
        render_and_release_certificate_pdf_for_session(
            connection=connection,
            session_id="qa-session",
            job_id="job-001",
            certificate_id="cert-001",
            certificate_number="SIMVAL-CAL-0001",
            artifact_id="artifact-001",
            artifact_directory=tmp_path,
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert not (tmp_path / "SIMVAL-CAL-0001.pdf").exists()
    assert SQLiteCertificateRecordRepository(connection).list_for_job("job-001") == ()


def test_render_and_release_certificate_pdf_blocks_before_approved_state(tmp_path):
    connection = _connection_with_release_data(job_state=WorkflowState.CALCULATED)
    build_certificate_preview_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        template_version="template-2026-001",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
    )

    with pytest.raises(CertificateReleaseServiceError):
        render_and_release_certificate_pdf_for_session(
            connection=connection,
            session_id="qa-session",
            job_id="job-001",
            certificate_id="cert-001",
            certificate_number="SIMVAL-CAL-0001",
            artifact_id="artifact-001",
            artifact_directory=tmp_path,
            template_version="template-2026-001",
            software_version="app-0.1.0",
            timestamp=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )

    assert not (tmp_path / "SIMVAL-CAL-0001.pdf").exists()
