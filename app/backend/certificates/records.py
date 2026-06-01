"""Immutable certificate and export artifact records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import re


class CertificateRecordError(ValueError):
    """Raised when a certificate record is incomplete or inconsistent."""


class ArtifactType(StrEnum):
    PDF = "pdf"
    XLSX = "xlsx"


class CertificateStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    RELEASED = "released"
    REVISED = "revised"
    VOIDED = "voided"


_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    artifact_id: str
    certificate_id: str
    artifact_type: ArtifactType
    filename: str
    checksum_sha256: str
    storage_uri: str
    generated_by: str
    generated_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.artifact_id, "Artifact id")
        _require_text(self.certificate_id, "Artifact certificate id")
        _require_instance(self.artifact_type, ArtifactType, "Artifact type")
        _require_text(self.filename, "Artifact filename")
        _require_text(self.storage_uri, "Artifact storage URI")
        _require_text(self.generated_by, "Artifact generated_by")
        _require_timezone_aware(self.generated_at, "Artifact generated_at")
        if not _SHA256_PATTERN.fullmatch(self.checksum_sha256):
            raise CertificateRecordError("Artifact checksum must be a SHA-256 hex digest.")
        object.__setattr__(self, "checksum_sha256", self.checksum_sha256.lower())


@dataclass(frozen=True, slots=True)
class CertificateRecord:
    certificate_id: str
    job_id: str
    certificate_number: str
    status: CertificateStatus
    calculation_summary_ids: tuple[str, ...]
    export_artifacts: tuple[ExportArtifact, ...]
    software_version: str
    calculation_engine_version: str
    constant_set_version: str
    budget_version: str
    template_version: str
    approved_by: str | None = None
    approved_at: datetime | None = None
    released_by: str | None = None
    released_at: datetime | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "certificate_id",
            "job_id",
            "certificate_number",
            "software_version",
            "calculation_engine_version",
            "constant_set_version",
            "budget_version",
            "template_version",
        ):
            _require_text(getattr(self, field_name), field_name)
        _require_instance(self.status, CertificateStatus, "Certificate status")
        for summary_id in self.calculation_summary_ids:
            _require_text(summary_id, "Calculation summary id")
        for artifact in self.export_artifacts:
            if artifact.certificate_id != self.certificate_id:
                raise CertificateRecordError(
                    "Export artifact must belong to the certificate."
                )
        if self.status in {CertificateStatus.APPROVED, CertificateStatus.RELEASED}:
            _require_approval_evidence(self.approved_by, self.approved_at)
        if self.status is CertificateStatus.RELEASED:
            if len(self.calculation_summary_ids) == 0:
                raise CertificateRecordError(
                    "Released certificate requires calculation summaries."
                )
            if len(self.export_artifacts) == 0:
                raise CertificateRecordError(
                    "Released certificate requires an export artifact."
                )
            _require_release_evidence(self.released_by, self.released_at)

    @property
    def primary_artifact(self) -> ExportArtifact:
        if not self.export_artifacts:
            raise CertificateRecordError("Certificate has no export artifact.")
        return self.export_artifacts[0]


@dataclass(frozen=True, slots=True)
class CertificateRevision:
    revision_id: str
    original_certificate_id: str
    original_certificate_number: str
    reason: str
    revised_by: str
    revised_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.revision_id, "Revision id")
        _require_text(self.original_certificate_id, "Original certificate id")
        _require_text(
            self.original_certificate_number,
            "Original certificate number",
        )
        _require_text(self.reason, "Revision reason")
        _require_text(self.revised_by, "Revision revised_by")
        _require_timezone_aware(self.revised_at, "Revision revised_at")


def create_revision_record(
    *,
    revision_id: str,
    original: CertificateRecord,
    reason: str,
    revised_by: str,
    revised_at: datetime,
) -> CertificateRevision:
    """Create immutable revision evidence for a previously released certificate."""
    if original.status is not CertificateStatus.RELEASED:
        raise CertificateRecordError("Only released certificates can be revised.")
    return CertificateRevision(
        revision_id=revision_id,
        original_certificate_id=original.certificate_id,
        original_certificate_number=original.certificate_number,
        reason=reason,
        revised_by=revised_by,
        revised_at=revised_at,
    )


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise CertificateRecordError(f"{field_name} is required.")


def _require_instance(value: object, expected_type: type, field_name: str) -> None:
    if not isinstance(value, expected_type):
        raise CertificateRecordError(f"{field_name} is invalid.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CertificateRecordError(f"{field_name} must be timezone-aware.")


def _require_approval_evidence(
    approved_by: str | None,
    approved_at: datetime | None,
) -> None:
    if approved_by is None or approved_by.strip() == "":
        raise CertificateRecordError("Approved certificate requires approved_by.")
    if approved_at is None:
        raise CertificateRecordError("Approved certificate requires approved_at.")
    _require_timezone_aware(approved_at, "Certificate approved_at")


def _require_release_evidence(
    released_by: str | None,
    released_at: datetime | None,
) -> None:
    if released_by is None or released_by.strip() == "":
        raise CertificateRecordError("Released certificate requires released_by.")
    if released_at is None:
        raise CertificateRecordError("Released certificate requires released_at.")
    _require_timezone_aware(released_at, "Certificate released_at")
