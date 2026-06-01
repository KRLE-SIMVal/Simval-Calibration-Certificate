from datetime import datetime, timezone

import pytest

from app.backend.certificates.records import (
    ArtifactType,
    CertificateRecord,
    CertificateRecordError,
    CertificateRevision,
    CertificateStatus,
    ExportArtifact,
    create_revision_record,
)


def _artifact() -> ExportArtifact:
    return ExportArtifact(
        artifact_id="artifact-001",
        certificate_id="cert-001",
        artifact_type=ArtifactType.PDF,
        filename="SIMVAL-CAL-0001.pdf",
        checksum_sha256="a" * 64,
        storage_uri="controlled-local://SIMVAL-CAL-0001.pdf",
        generated_by="qa-001",
        generated_at=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
    )


def _released_certificate() -> CertificateRecord:
    return CertificateRecord(
        certificate_id="cert-001",
        job_id="job-001",
        certificate_number="SIMVAL-CAL-0001",
        status=CertificateStatus.RELEASED,
        calculation_summary_ids=("point-001",),
        export_artifacts=(_artifact(),),
        software_version="app-0.1.0",
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
        template_version="template-2026-001",
        approved_by="qa-001",
        approved_at=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
        released_by="qa-001",
        released_at=datetime(2026, 6, 1, 15, 31, tzinfo=timezone.utc),
    )


def test_export_artifact_records_checksum_and_generation_evidence():
    artifact = _artifact()

    assert artifact.checksum_sha256 == "a" * 64
    assert artifact.generated_at.tzinfo is not None


def test_export_artifact_rejects_invalid_checksum():
    with pytest.raises(CertificateRecordError):
        ExportArtifact(
            artifact_id="artifact-001",
            certificate_id="cert-001",
            artifact_type=ArtifactType.PDF,
            filename="SIMVAL-CAL-0001.pdf",
            checksum_sha256="not-a-sha256",
            storage_uri="controlled-local://SIMVAL-CAL-0001.pdf",
            generated_by="qa-001",
            generated_at=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
        )


def test_released_certificate_requires_version_references_and_artifact():
    certificate = _released_certificate()

    assert certificate.status is CertificateStatus.RELEASED
    assert certificate.primary_artifact.filename == "SIMVAL-CAL-0001.pdf"
    assert certificate.constant_set_version == "constants-2026-001"
    assert certificate.budget_version == "budget-temp-001"


def test_released_certificate_rejects_missing_artifact():
    with pytest.raises(CertificateRecordError):
        CertificateRecord(
            certificate_id="cert-001",
            job_id="job-001",
            certificate_number="SIMVAL-CAL-0001",
            status=CertificateStatus.RELEASED,
            calculation_summary_ids=("point-001",),
            export_artifacts=(),
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="budget-temp-001",
            template_version="template-2026-001",
            approved_by="qa-001",
            approved_at=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
            released_by="qa-001",
            released_at=datetime(2026, 6, 1, 15, 31, tzinfo=timezone.utc),
        )


def test_released_certificate_rejects_missing_calculation_summary():
    with pytest.raises(CertificateRecordError):
        CertificateRecord(
            certificate_id="cert-001",
            job_id="job-001",
            certificate_number="SIMVAL-CAL-0001",
            status=CertificateStatus.RELEASED,
            calculation_summary_ids=(),
            export_artifacts=(_artifact(),),
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="budget-temp-001",
            template_version="template-2026-001",
            approved_by="qa-001",
            approved_at=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
            released_by="qa-001",
            released_at=datetime(2026, 6, 1, 15, 31, tzinfo=timezone.utc),
        )


def test_released_certificate_rejects_missing_release_evidence():
    with pytest.raises(CertificateRecordError):
        CertificateRecord(
            certificate_id="cert-001",
            job_id="job-001",
            certificate_number="SIMVAL-CAL-0001",
            status=CertificateStatus.RELEASED,
            calculation_summary_ids=("point-001",),
            export_artifacts=(_artifact(),),
            software_version="app-0.1.0",
            calculation_engine_version="calc-engine-0.1.0",
            constant_set_version="constants-2026-001",
            budget_version="budget-temp-001",
            template_version="template-2026-001",
            approved_by="qa-001",
            approved_at=datetime(2026, 6, 1, 15, 20, tzinfo=timezone.utc),
        )


def test_released_certificate_is_immutable():
    certificate = _released_certificate()

    with pytest.raises(AttributeError):
        certificate.certificate_number = "SIMVAL-CAL-0002"


def test_revision_record_requires_reason_and_links_original_release():
    original = _released_certificate()

    revision = create_revision_record(
        revision_id="rev-001",
        original=original,
        reason="Corrected customer address after QA approval.",
        revised_by="qa-002",
        revised_at=datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc),
    )

    assert revision.original_certificate_id == "cert-001"
    assert revision.original_certificate_number == "SIMVAL-CAL-0001"
    assert revision.revised_by == "qa-002"


def test_revision_record_rejects_blank_reason():
    with pytest.raises(CertificateRecordError):
        create_revision_record(
            revision_id="rev-001",
            original=_released_certificate(),
            reason=" ",
            revised_by="qa-002",
            revised_at=datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc),
        )


def test_revision_record_rejects_non_released_original():
    draft = CertificateRecord(
        certificate_id="cert-001",
        job_id="job-001",
        certificate_number="SIMVAL-CAL-0001",
        status=CertificateStatus.DRAFT,
        calculation_summary_ids=(),
        export_artifacts=(),
        software_version="app-0.1.0",
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
        template_version="template-2026-001",
    )

    with pytest.raises(CertificateRecordError):
        create_revision_record(
            revision_id="rev-001",
            original=draft,
            reason="Corrected customer address after QA approval.",
            revised_by="qa-002",
            revised_at=datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc),
        )


def test_certificate_revision_is_immutable_record():
    revision = CertificateRevision(
        revision_id="rev-001",
        original_certificate_id="cert-001",
        original_certificate_number="SIMVAL-CAL-0001",
        reason="Corrected customer address after QA approval.",
        revised_by="qa-002",
        revised_at=datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(AttributeError):
        revision.reason = "different"
