"""Certificate preview and export-readiness services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import sqlite3

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.auth.permissions import Action
from app.backend.certificates.metadata import (
    CertificateMetadata,
    CertificateMetadataError,
)
from app.backend.certificates.records import (
    ArtifactType,
    CertificateRecord,
    CertificateRecordError,
    CertificateRevision,
    CertificateStatus,
    ExportArtifact,
    create_revision_record,
)
from app.backend.certificates.preview import (
    CertificatePreview,
    CertificatePreviewDut,
    CertificatePreviewError,
    CertificatePreviewReferenceEquipment,
    CertificatePreviewRow,
)
from app.backend.certificates.rendering import (
    RenderedCertificateArtifact,
    render_certificate_pdf,
)
from app.backend.certificates.storage import (
    StoredCertificateArtifact,
    discard_staged_artifact,
    finalize_staged_artifact,
    stage_rendered_artifact,
    verified_stored_artifact_path,
)
from app.backend.certificates.template_contract import (
    CertificateTemplateContractError,
    validate_certificate_template_contract,
)
from app.backend.domain.equipment import ReferenceEquipment, SelectedReferenceEquipment
from app.backend.domain.equipment import reference_equipment_blockers
from app.backend.domain.entities import (
    DeviceUnderTest,
    Discipline,
    DomainValidationError,
)
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    RecordNotFoundError,
    PersistenceError,
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteCertificateMetadataRepository,
    SQLiteCertificateRecordRepository,
    SQLiteCertificateRevisionRepository,
    SQLiteDeviceUnderTestRepository,
    SQLiteMeasurementPointSummaryRepository,
    SQLiteSelectedReferenceEquipmentRepository,
)
from app.backend.services.authentication import resolve_actor_for_action
from app.backend.services.certificate_numbers import (
    CertificateNumberAllocationResult,
    CertificateNumberServiceError,
    allocate_certificate_number_in_transaction,
)
from app.backend.services.reviewer_independence import (
    ReviewerIndependenceError,
    ReviewerIndependenceStage,
    assert_reviewer_independence,
)
from app.backend.services.workflow import transition_calibration_job
from app.calculation_engine.common.summary import MeasurementPointSummary


class CertificatePreviewServiceError(ValueError):
    """Raised when a certificate preview cannot be generated safely."""


class CertificateReleaseServiceError(ValueError):
    """Raised when a certificate cannot be released safely."""


class CertificateMetadataServiceError(ValueError):
    """Raised when certificate metadata cannot be captured safely."""


class CertificateReferenceEquipmentServiceError(ValueError):
    """Raised when reference equipment cannot be selected safely."""


class CertificateRevisionServiceError(ValueError):
    """Raised when a released certificate cannot be revised safely."""


@dataclass(frozen=True, slots=True)
class CertificateMetadataCapture:
    metadata: CertificateMetadata
    metadata_audit_event_id: int
    metadata_audit_event: AuditEvent
    workflow_audit_event_id: int
    workflow_audit_event: AuditEvent


@dataclass(frozen=True, slots=True)
class CertificateReferenceEquipmentSelection:
    selection: SelectedReferenceEquipment
    selection_audit_event_id: int
    selection_audit_event: AuditEvent
    workflow_audit_event_id: int
    workflow_audit_event: AuditEvent


@dataclass(frozen=True, slots=True)
class CertificatePreviewGeneration:
    preview: CertificatePreview
    audit_event_id: int
    audit_event: AuditEvent


@dataclass(frozen=True, slots=True)
class CertificateRelease:
    certificate: CertificateRecord
    accreditation_mark_allowed: bool
    export_audit_event_id: int
    export_audit_event: AuditEvent
    release_audit_event_id: int
    release_audit_event: AuditEvent
    workflow_audit_event_id: int
    workflow_audit_event: AuditEvent


@dataclass(frozen=True, slots=True)
class RenderedCertificateRelease:
    rendered_artifact: RenderedCertificateArtifact
    stored_artifact: StoredCertificateArtifact
    release: CertificateRelease


@dataclass(frozen=True, slots=True)
class AllocatedRenderedCertificateRelease:
    rendered_artifact: RenderedCertificateArtifact
    stored_artifact: StoredCertificateArtifact
    release: CertificateRelease
    certificate_number_allocation: CertificateNumberAllocationResult


@dataclass(frozen=True, slots=True)
class CertificateRevisionRegistration:
    revision: CertificateRevision
    revision_audit_event_id: int
    revision_audit_event: AuditEvent
    workflow_audit_event_id: int
    workflow_audit_event: AuditEvent


@dataclass(frozen=True, slots=True)
class CertificateHistoryEntry:
    certificate: CertificateRecord
    revisions: tuple[CertificateRevision, ...]


@dataclass(frozen=True, slots=True)
class CertificateHistory:
    job_id: str
    entries: tuple[CertificateHistoryEntry, ...]


@dataclass(frozen=True, slots=True)
class ReleasedCertificateArtifactRetrieval:
    certificate: CertificateRecord
    artifact: ExportArtifact
    path: Path


@dataclass(frozen=True, slots=True)
class _ApprovalEvidence:
    approved_by: str
    approved_at: datetime


def capture_certificate_metadata_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    certificate_date: date,
    calibration_date: date,
    receipt_date: date,
    task_number: str,
    purchase_order: str,
    client_name: str,
    client_address: str,
    procedure: str,
    place: str,
    approved_by_label: str,
    remarks: str,
    traceability_statement: str,
    uncertainty_statement: str,
    ambient_conditions: str,
    temperature_scale: str,
    software_version: str,
    timestamp: datetime,
) -> CertificateMetadataCapture:
    """Capture immutable certificate metadata and move a draft job forward."""
    _require_metadata_text(software_version, "Software version")
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.EDIT_DRAFT_JOB_METADATA,
        timestamp=timestamp,
    )
    try:
        metadata = CertificateMetadata(
            job_id=job_id,
            certificate_date=certificate_date,
            calibration_date=calibration_date,
            receipt_date=receipt_date,
            task_number=task_number,
            purchase_order=purchase_order,
            client_name=client_name,
            client_address=client_address,
            procedure=procedure,
            place=place,
            approved_by_label=approved_by_label,
            remarks=remarks,
            traceability_statement=traceability_statement,
            uncertainty_statement=uncertainty_statement,
            ambient_conditions=ambient_conditions,
            temperature_scale=temperature_scale,
            recorded_by=actor.user_id,
            recorded_at=timestamp,
        )
    except CertificateMetadataError as exc:
        raise CertificateMetadataServiceError(str(exc)) from exc

    with connection:
        job_repository = SQLiteCalibrationJobRepository(connection, autocommit=False)
        metadata_repository = SQLiteCertificateMetadataRepository(
            connection,
            autocommit=False,
        )
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)

        job = job_repository.get(job_id)
        if job.state is not WorkflowState.DRAFT:
            raise CertificateMetadataServiceError(
                "Certificate metadata capture requires draft workflow state."
            )

        metadata_repository.add(metadata)
        metadata_audit_event = _certificate_metadata_audit_event(
            metadata=metadata,
            software_version=software_version,
            timestamp=timestamp,
        )
        metadata_audit_event_id = audit_repository.append(metadata_audit_event)
        transition = transition_calibration_job(
            job_id=job_id,
            current=job.state,
            target=WorkflowState.METADATA_COMPLETE,
            user_id=actor.user_id,
            software_version=software_version,
            timestamp=timestamp,
        )
        job_repository.update_state(
            job_id=job_id,
            expected_state=job.state,
            new_state=transition.state,
        )
        workflow_audit_event_id = audit_repository.append(transition.audit_event)

    return CertificateMetadataCapture(
        metadata=metadata,
        metadata_audit_event_id=metadata_audit_event_id,
        metadata_audit_event=metadata_audit_event,
        workflow_audit_event_id=workflow_audit_event_id,
        workflow_audit_event=transition.audit_event,
    )


def select_reference_equipment_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    equipment: ReferenceEquipment,
    software_version: str,
    timestamp: datetime,
) -> CertificateReferenceEquipmentSelection:
    """Select immutable reference-equipment evidence and move the job forward."""
    _require_reference_equipment_text(software_version, "Software version")
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.SELECT_REFERENCE_EQUIPMENT,
        timestamp=timestamp,
    )
    try:
        selection = SelectedReferenceEquipment(
            job_id=job_id,
            equipment=equipment,
            selected_by=actor.user_id,
            selected_at=timestamp,
        )
    except DomainValidationError as exc:
        raise CertificateReferenceEquipmentServiceError(str(exc)) from exc

    with connection:
        job_repository = SQLiteCalibrationJobRepository(connection, autocommit=False)
        selection_repository = SQLiteSelectedReferenceEquipmentRepository(
            connection,
            autocommit=False,
        )
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)

        job = job_repository.get(job_id)
        if job.state is not WorkflowState.METADATA_COMPLETE:
            raise CertificateReferenceEquipmentServiceError(
                "Reference equipment selection requires metadata_complete workflow state."
            )

        try:
            selection_repository.add(selection)
        except PersistenceError as exc:
            raise CertificateReferenceEquipmentServiceError(str(exc)) from exc
        selection_audit_event = _reference_equipment_selection_audit_event(
            selection=selection,
            software_version=software_version,
            timestamp=timestamp,
        )
        selection_audit_event_id = audit_repository.append(selection_audit_event)
        transition = transition_calibration_job(
            job_id=job_id,
            current=job.state,
            target=WorkflowState.EQUIPMENT_SELECTED,
            user_id=actor.user_id,
            software_version=software_version,
            timestamp=timestamp,
        )
        job_repository.update_state(
            job_id=job_id,
            expected_state=job.state,
            new_state=transition.state,
        )
        workflow_audit_event_id = audit_repository.append(transition.audit_event)

    return CertificateReferenceEquipmentSelection(
        selection=selection,
        selection_audit_event_id=selection_audit_event_id,
        selection_audit_event=selection_audit_event,
        workflow_audit_event_id=workflow_audit_event_id,
        workflow_audit_event=transition.audit_event,
    )


def build_certificate_preview_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    template_version: str,
    software_version: str,
    timestamp: datetime,
    accreditation_mark_allowed: bool = True,
) -> CertificatePreviewGeneration:
    """Build a certificate preview from locked summaries after actor resolution."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.PREVIEW_CERTIFICATE,
        timestamp=timestamp,
    )
    return build_certificate_preview(
        connection=connection,
        job_id=job_id,
        generated_by=actor.user_id,
        template_version=template_version,
        software_version=software_version,
        accreditation_mark_allowed=accreditation_mark_allowed,
        timestamp=timestamp,
    )


def build_certificate_preview(
    *,
    connection: sqlite3.Connection,
    job_id: str,
    generated_by: str,
    template_version: str,
    software_version: str,
    timestamp: datetime,
    accreditation_mark_allowed: bool = True,
) -> CertificatePreviewGeneration:
    """Build and audit a certificate preview from persisted calculation summaries."""
    _require_text(job_id, "Job id")
    _require_text(generated_by, "Generated by")
    _require_text(template_version, "Template version")
    _require_text(software_version, "Software version")
    _require_timezone_aware(timestamp, "Preview timestamp")

    with connection:
        job_repository = SQLiteCalibrationJobRepository(connection, autocommit=False)
        metadata_repository = SQLiteCertificateMetadataRepository(
            connection,
            autocommit=False,
        )
        dut_repository = SQLiteDeviceUnderTestRepository(connection, autocommit=False)
        selected_reference_repository = SQLiteSelectedReferenceEquipmentRepository(
            connection,
            autocommit=False,
        )
        summary_repository = SQLiteMeasurementPointSummaryRepository(
            connection,
            autocommit=False,
        )
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)

        job = job_repository.get(job_id)
        if job.state not in {
            WorkflowState.CALCULATED,
            WorkflowState.TECHNICAL_REVIEW,
            WorkflowState.QA_REVIEW,
            WorkflowState.APPROVED,
        }:
            raise CertificatePreviewServiceError(
                "Certificate preview requires calculated or later workflow state."
            )

        summaries = summary_repository.list_for_job(job_id)
        if len(summaries) == 0:
            raise CertificatePreviewServiceError(
                "Certificate preview requires calculation summaries."
            )
        try:
            metadata = metadata_repository.get(job_id)
        except RecordNotFoundError as exc:
            raise CertificatePreviewServiceError(
                "Certificate preview requires certificate metadata."
            ) from exc
        duts = dut_repository.list_for_job(job_id)
        selected_reference_equipment = selected_reference_repository.list_for_job(
            job_id
        )
        if len(selected_reference_equipment) == 0:
            raise CertificatePreviewServiceError(
                "Certificate preview requires reference equipment."
            )
        suitability_blockers = _reference_equipment_suitability_blockers(
            job=job,
            metadata=metadata,
            selected_reference_equipment=selected_reference_equipment,
            summaries=summaries,
        )
        if len(suitability_blockers) > 0:
            raise CertificatePreviewServiceError(
                _reference_equipment_suitability_message(suitability_blockers)
            )

        preview = _preview_from_summaries(
            job_id=job_id,
            generated_by=generated_by,
            generated_at=timestamp,
            discipline=job.discipline,
            software_version=software_version,
            template_version=template_version,
            accreditation_mark_allowed=accreditation_mark_allowed,
            metadata=metadata,
            duts=duts,
            selected_reference_equipment=selected_reference_equipment,
            summaries=summaries,
        )
        audit_event = _preview_audit_event(preview)
        audit_event_id = audit_repository.append(audit_event)

    return CertificatePreviewGeneration(
        preview=preview,
        audit_event_id=audit_event_id,
        audit_event=audit_event,
    )


def render_and_release_certificate_pdf_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    certificate_id: str,
    certificate_number: str,
    artifact_id: str,
    artifact_directory: Path,
    template_version: str,
    software_version: str,
    timestamp: datetime,
    accreditation_mark_allowed: bool = True,
) -> RenderedCertificateRelease:
    """Render, store, and release a PDF certificate from locked preview evidence."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.RELEASE_CERTIFICATE,
        timestamp=timestamp,
    )
    _assert_independent_release_actor(
        connection=connection,
        job_id=job_id,
        user_id=actor.user_id,
    )
    preview = _preview_for_release_rendering(
        connection=connection,
        job_id=job_id,
        template_version=template_version,
        software_version=software_version,
        accreditation_mark_allowed=accreditation_mark_allowed,
    )
    rendered_artifact = render_certificate_pdf(
        certificate_id=certificate_id,
        certificate_number=certificate_number,
        preview=preview,
    )
    try:
        validate_certificate_template_contract(
            artifact=rendered_artifact,
            preview=preview,
            certificate_number=certificate_number,
        )
    except CertificateTemplateContractError as exc:
        raise CertificateReleaseServiceError(str(exc)) from exc
    pending_artifact = stage_rendered_artifact(
        base_path=artifact_directory,
        artifact=rendered_artifact,
    )
    try:
        release = release_certificate(
            connection=connection,
            job_id=job_id,
            certificate_id=certificate_id,
            certificate_number=certificate_number,
            artifact_id=artifact_id,
            artifact_type=rendered_artifact.artifact_type,
            filename=pending_artifact.filename,
            checksum_sha256=pending_artifact.checksum_sha256,
            storage_uri=pending_artifact.storage_uri,
            released_by=actor.user_id,
            template_version=template_version,
            software_version=software_version,
            accreditation_mark_allowed=accreditation_mark_allowed,
            timestamp=timestamp,
        )
    except Exception:
        discard_staged_artifact(pending_artifact)
        raise
    stored_artifact = finalize_staged_artifact(pending_artifact)
    return RenderedCertificateRelease(
        rendered_artifact=rendered_artifact,
        stored_artifact=stored_artifact,
        release=release,
    )


def render_and_release_certificate_pdf_with_allocated_number_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    certificate_id: str,
    certificate_number_prefix: str,
    certificate_number_padding: int,
    artifact_id: str,
    artifact_directory: Path,
    template_version: str,
    software_version: str,
    timestamp: datetime,
    accreditation_mark_allowed: bool = True,
) -> AllocatedRenderedCertificateRelease:
    """Allocate a controlled certificate number, render, and release a PDF."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.RELEASE_CERTIFICATE,
        timestamp=timestamp,
    )
    _assert_independent_release_actor(
        connection=connection,
        job_id=job_id,
        user_id=actor.user_id,
    )
    preview = _preview_for_release_rendering(
        connection=connection,
        job_id=job_id,
        template_version=template_version,
        software_version=software_version,
        accreditation_mark_allowed=accreditation_mark_allowed,
    )
    pending_artifact = None
    try:
        with connection:
            try:
                allocation = allocate_certificate_number_in_transaction(
                    connection=connection,
                    user_id=actor.user_id,
                    prefix=certificate_number_prefix,
                    padding=certificate_number_padding,
                    software_version=software_version,
                    timestamp=timestamp,
                    context={
                        "job_id": job_id,
                        "certificate_id": certificate_id,
                        "operation": "rendered_certificate_release",
                    },
                )
            except (CertificateNumberServiceError, PersistenceError) as exc:
                raise CertificateReleaseServiceError(str(exc)) from exc

            rendered_artifact = render_certificate_pdf(
                certificate_id=certificate_id,
                certificate_number=allocation.certificate_number,
                preview=preview,
            )
            try:
                validate_certificate_template_contract(
                    artifact=rendered_artifact,
                    preview=preview,
                    certificate_number=allocation.certificate_number,
                )
            except CertificateTemplateContractError as exc:
                raise CertificateReleaseServiceError(str(exc)) from exc
            pending_artifact = stage_rendered_artifact(
                base_path=artifact_directory,
                artifact=rendered_artifact,
            )
            release = _release_certificate_in_transaction(
                connection=connection,
                job_id=job_id,
                certificate_id=certificate_id,
                certificate_number=allocation.certificate_number,
                artifact_id=artifact_id,
                artifact_type=rendered_artifact.artifact_type,
                filename=pending_artifact.filename,
                checksum_sha256=pending_artifact.checksum_sha256,
                storage_uri=pending_artifact.storage_uri,
                released_by=actor.user_id,
                template_version=template_version,
                software_version=software_version,
                accreditation_mark_allowed=accreditation_mark_allowed,
                timestamp=timestamp,
            )
    except Exception:
        if pending_artifact is not None:
            discard_staged_artifact(pending_artifact)
        raise
    stored_artifact = finalize_staged_artifact(pending_artifact)
    return AllocatedRenderedCertificateRelease(
        rendered_artifact=rendered_artifact,
        stored_artifact=stored_artifact,
        release=release,
        certificate_number_allocation=allocation,
    )


def release_certificate_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    certificate_id: str,
    certificate_number: str,
    artifact_id: str,
    artifact_type: ArtifactType,
    filename: str,
    checksum_sha256: str,
    storage_uri: str,
    template_version: str,
    software_version: str,
    timestamp: datetime,
    accreditation_mark_allowed: bool = True,
) -> CertificateRelease:
    """Release a certificate only after matching preview evidence exists."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.RELEASE_CERTIFICATE,
        timestamp=timestamp,
    )
    _assert_independent_release_actor(
        connection=connection,
        job_id=job_id,
        user_id=actor.user_id,
    )
    return release_certificate(
        connection=connection,
        job_id=job_id,
        certificate_id=certificate_id,
        certificate_number=certificate_number,
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        filename=filename,
        checksum_sha256=checksum_sha256,
        storage_uri=storage_uri,
        released_by=actor.user_id,
        template_version=template_version,
        software_version=software_version,
        accreditation_mark_allowed=accreditation_mark_allowed,
        timestamp=timestamp,
    )


def _preview_for_release_rendering(
    *,
    connection: sqlite3.Connection,
    job_id: str,
    template_version: str,
    software_version: str,
    accreditation_mark_allowed: bool = True,
) -> CertificatePreview:
    job_repository = SQLiteCalibrationJobRepository(connection)
    metadata_repository = SQLiteCertificateMetadataRepository(connection)
    dut_repository = SQLiteDeviceUnderTestRepository(connection)
    selected_reference_repository = SQLiteSelectedReferenceEquipmentRepository(
        connection
    )
    summary_repository = SQLiteMeasurementPointSummaryRepository(connection)
    audit_repository = SQLiteAuditEventRepository(connection)

    job = job_repository.get(job_id)
    if job.state is not WorkflowState.APPROVED:
        raise CertificateReleaseServiceError(
            "Certificate rendering for release requires approved workflow state."
        )
    summaries = summary_repository.list_for_job(job_id)
    if len(summaries) == 0:
        raise CertificateReleaseServiceError(
            "Certificate rendering for release requires calculation summaries."
        )
    try:
        metadata = metadata_repository.get(job_id)
    except RecordNotFoundError as exc:
        raise CertificateReleaseServiceError(
            "Certificate rendering for release requires certificate metadata."
        ) from exc
    duts = dut_repository.list_for_job(job_id)
    selected_reference_equipment = selected_reference_repository.list_for_job(job_id)
    if len(selected_reference_equipment) == 0:
        raise CertificateReleaseServiceError(
            "Certificate rendering for release requires reference equipment."
        )
    suitability_blockers = _reference_equipment_suitability_blockers(
        job=job,
        metadata=metadata,
        selected_reference_equipment=selected_reference_equipment,
        summaries=summaries,
    )
    if len(suitability_blockers) > 0:
        raise CertificateReleaseServiceError(
            _reference_equipment_suitability_message(suitability_blockers)
        )
    summary_ids = tuple(summary.point_id for summary in summaries)
    calculation_engine_version = _single_release_version(
        {summary.calculation_engine_version for summary in summaries},
        "calculation engine",
    )
    constant_set_version = _single_release_version(
        {summary.constant_set_version for summary in summaries},
        "constant set",
    )
    budget_version = _single_release_version(
        {summary.budget_version for summary in summaries},
        "budget",
    )
    preview_event = _matching_preview_event(
        audit_repository.list_for_entity("calibration_job", job_id),
        summary_ids=summary_ids,
        template_version=template_version,
        software_version=software_version,
        calculation_engine_version=calculation_engine_version,
        constant_set_version=constant_set_version,
        budget_version=budget_version,
        accreditation_mark_allowed=accreditation_mark_allowed,
    )
    if preview_event is None:
        raise CertificateReleaseServiceError(
            "Certificate rendering for release requires matching preview audit evidence."
        )
    try:
        return _preview_from_summaries(
            job_id=job_id,
            generated_by=preview_event.user_id,
            generated_at=preview_event.timestamp,
            discipline=job.discipline,
            software_version=software_version,
            template_version=template_version,
            accreditation_mark_allowed=accreditation_mark_allowed,
            metadata=metadata,
            duts=duts,
            selected_reference_equipment=selected_reference_equipment,
            summaries=summaries,
        )
    except CertificatePreviewServiceError as exc:
        raise CertificateReleaseServiceError(str(exc)) from exc


def release_certificate(
    *,
    connection: sqlite3.Connection,
    job_id: str,
    certificate_id: str,
    certificate_number: str,
    artifact_id: str,
    artifact_type: ArtifactType,
    filename: str,
    checksum_sha256: str,
    storage_uri: str,
    released_by: str,
    template_version: str,
    software_version: str,
    timestamp: datetime,
    accreditation_mark_allowed: bool = True,
) -> CertificateRelease:
    """Persist immutable release evidence and transition the job to released."""
    _validate_release_inputs(
        job_id=job_id,
        certificate_id=certificate_id,
        certificate_number=certificate_number,
        artifact_id=artifact_id,
        filename=filename,
        checksum_sha256=checksum_sha256,
        storage_uri=storage_uri,
        released_by=released_by,
        template_version=template_version,
        software_version=software_version,
        timestamp=timestamp,
    )
    if not isinstance(artifact_type, ArtifactType):
        raise CertificateReleaseServiceError("Artifact type is invalid.")

    with connection:
        return _release_certificate_in_transaction(
            connection=connection,
            job_id=job_id,
            certificate_id=certificate_id,
            certificate_number=certificate_number,
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            filename=filename,
            checksum_sha256=checksum_sha256,
            storage_uri=storage_uri,
            released_by=released_by,
            template_version=template_version,
            software_version=software_version,
            accreditation_mark_allowed=accreditation_mark_allowed,
            timestamp=timestamp,
        )


def _assert_independent_release_actor(
    *,
    connection: sqlite3.Connection,
    job_id: str,
    user_id: str,
) -> None:
    try:
        assert_reviewer_independence(
            connection=connection,
            job_id=job_id,
            user_id=user_id,
            stage=ReviewerIndependenceStage.CERTIFICATE_RELEASE,
        )
    except ReviewerIndependenceError as exc:
        raise CertificateReleaseServiceError(str(exc)) from exc


def _release_certificate_in_transaction(
    *,
    connection: sqlite3.Connection,
    job_id: str,
    certificate_id: str,
    certificate_number: str,
    artifact_id: str,
    artifact_type: ArtifactType,
    filename: str,
    checksum_sha256: str,
    storage_uri: str,
    released_by: str,
    template_version: str,
    software_version: str,
    timestamp: datetime,
    accreditation_mark_allowed: bool = True,
) -> CertificateRelease:
    _validate_release_inputs(
        job_id=job_id,
        certificate_id=certificate_id,
        certificate_number=certificate_number,
        artifact_id=artifact_id,
        filename=filename,
        checksum_sha256=checksum_sha256,
        storage_uri=storage_uri,
        released_by=released_by,
        template_version=template_version,
        software_version=software_version,
        timestamp=timestamp,
    )
    if not isinstance(artifact_type, ArtifactType):
        raise CertificateReleaseServiceError("Artifact type is invalid.")
    _assert_independent_release_actor(
        connection=connection,
        job_id=job_id,
        user_id=released_by,
    )

    job_repository = SQLiteCalibrationJobRepository(connection, autocommit=False)
    metadata_repository = SQLiteCertificateMetadataRepository(
        connection,
        autocommit=False,
    )
    selected_reference_repository = SQLiteSelectedReferenceEquipmentRepository(
        connection,
        autocommit=False,
    )
    summary_repository = SQLiteMeasurementPointSummaryRepository(
        connection,
        autocommit=False,
    )
    certificate_repository = SQLiteCertificateRecordRepository(
        connection,
        autocommit=False,
    )
    audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)

    job = job_repository.get(job_id)
    if job.state is not WorkflowState.APPROVED:
        raise CertificateReleaseServiceError(
            "Certificate release requires approved workflow state."
        )

    summaries = summary_repository.list_for_job(job_id)
    if len(summaries) == 0:
        raise CertificateReleaseServiceError(
            "Certificate release requires calculation summaries."
        )
    try:
        metadata = metadata_repository.get(job_id)
    except RecordNotFoundError as exc:
        raise CertificateReleaseServiceError(
            "Certificate release requires certificate metadata."
        ) from exc
    selected_reference_equipment = selected_reference_repository.list_for_job(job_id)
    if len(selected_reference_equipment) == 0:
        raise CertificateReleaseServiceError(
            "Certificate release requires reference equipment."
        )
    suitability_blockers = _reference_equipment_suitability_blockers(
        job=job,
        metadata=metadata,
        selected_reference_equipment=selected_reference_equipment,
        summaries=summaries,
    )
    if len(suitability_blockers) > 0:
        raise CertificateReleaseServiceError(
            _reference_equipment_suitability_message(suitability_blockers)
        )
    summary_ids = tuple(summary.point_id for summary in summaries)
    calculation_engine_version = _single_release_version(
        {summary.calculation_engine_version for summary in summaries},
        "calculation engine",
    )
    constant_set_version = _single_release_version(
        {summary.constant_set_version for summary in summaries},
        "constant set",
    )
    budget_version = _single_release_version(
        {summary.budget_version for summary in summaries},
        "budget",
    )
    job_audit_events = audit_repository.list_for_entity("calibration_job", job_id)
    if not _matching_preview_exists(
        job_audit_events,
        summary_ids=summary_ids,
        template_version=template_version,
        software_version=software_version,
        calculation_engine_version=calculation_engine_version,
        constant_set_version=constant_set_version,
        budget_version=budget_version,
        accreditation_mark_allowed=accreditation_mark_allowed,
    ):
        raise CertificateReleaseServiceError(
            "Certificate release requires matching preview audit evidence."
        )
    approval_evidence = _qa_approval_evidence(job_audit_events) or _ApprovalEvidence(
        approved_by=released_by,
        approved_at=timestamp,
    )

    artifact = ExportArtifact(
        artifact_id=artifact_id,
        certificate_id=certificate_id,
        artifact_type=artifact_type,
        filename=filename,
        checksum_sha256=checksum_sha256,
        storage_uri=storage_uri,
        generated_by=released_by,
        generated_at=timestamp,
    )
    certificate = CertificateRecord(
        certificate_id=certificate_id,
        job_id=job_id,
        certificate_number=certificate_number,
        status=CertificateStatus.RELEASED,
        calculation_summary_ids=summary_ids,
        export_artifacts=(artifact,),
        software_version=software_version,
        calculation_engine_version=calculation_engine_version,
        constant_set_version=constant_set_version,
        budget_version=budget_version,
        template_version=template_version,
        approved_by=approval_evidence.approved_by,
        approved_at=approval_evidence.approved_at,
        released_by=released_by,
        released_at=timestamp,
    )
    try:
        certificate_repository.add(certificate)
    except PersistenceError as exc:
        raise CertificateReleaseServiceError(str(exc)) from exc

    export_audit_event = _export_artifact_audit_event(
        certificate=certificate,
        artifact=artifact,
        timestamp=timestamp,
    )
    export_audit_event_id = audit_repository.append(export_audit_event)
    release_audit_event = _certificate_release_audit_event(
        certificate=certificate,
        accreditation_mark_allowed=accreditation_mark_allowed,
        timestamp=timestamp,
    )
    release_audit_event_id = audit_repository.append(release_audit_event)
    transition = transition_calibration_job(
        job_id=job_id,
        current=job.state,
        target=WorkflowState.RELEASED,
        user_id=released_by,
        software_version=software_version,
        timestamp=timestamp,
    )
    job_repository.update_state(
        job_id=job_id,
        expected_state=job.state,
        new_state=transition.state,
    )
    workflow_audit_event_id = audit_repository.append(transition.audit_event)

    return CertificateRelease(
        certificate=certificate,
        accreditation_mark_allowed=accreditation_mark_allowed,
        export_audit_event_id=export_audit_event_id,
        export_audit_event=export_audit_event,
        release_audit_event_id=release_audit_event_id,
        release_audit_event=release_audit_event,
        workflow_audit_event_id=workflow_audit_event_id,
        workflow_audit_event=transition.audit_event,
    )


def get_certificate_history_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    timestamp: datetime,
) -> CertificateHistory:
    """Return released certificate artifact and revision evidence for a job."""
    _require_history_text(job_id, "Job id")
    resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.VIEW_RELEASED_CERTIFICATE,
        timestamp=timestamp,
    )
    certificate_repository = SQLiteCertificateRecordRepository(connection)
    revision_repository = SQLiteCertificateRevisionRepository(connection)
    certificates = certificate_repository.list_for_job(job_id)
    return CertificateHistory(
        job_id=job_id,
        entries=tuple(
            CertificateHistoryEntry(
                certificate=certificate,
                revisions=revision_repository.list_for_original(
                    certificate.certificate_id
                ),
            )
            for certificate in certificates
        ),
    )


def get_released_certificate_artifact_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    artifact_id: str,
    artifact_directory: Path,
    timestamp: datetime,
) -> ReleasedCertificateArtifactRetrieval:
    """Return a verified local path for an authorized released artifact download."""
    _require_history_text(artifact_id, "Artifact id")
    resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.VIEW_RELEASED_CERTIFICATE,
        timestamp=timestamp,
    )
    certificate_repository = SQLiteCertificateRecordRepository(connection)
    try:
        certificate = certificate_repository.get_by_artifact_id(artifact_id)
    except RecordNotFoundError as exc:
        raise CertificatePreviewServiceError(str(exc)) from exc
    artifact = _artifact_by_id(certificate, artifact_id)
    if artifact.filename != Path(artifact.filename).name:
        raise CertificatePreviewServiceError(
            "Artifact filename must not contain path components."
        )
    expected_storage_uri = f"controlled-local://{artifact.filename}"
    if artifact.storage_uri != expected_storage_uri:
        raise CertificatePreviewServiceError(
            "Artifact storage URI does not match controlled local storage."
        )
    path = verified_stored_artifact_path(
        base_path=artifact_directory,
        filename=artifact.filename,
        checksum_sha256=artifact.checksum_sha256,
    )
    return ReleasedCertificateArtifactRetrieval(
        certificate=certificate,
        artifact=artifact,
        path=path,
    )


def revise_released_certificate_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    certificate_id: str,
    revision_id: str,
    reason: str,
    software_version: str,
    timestamp: datetime,
) -> CertificateRevisionRegistration:
    """Record controlled revision evidence for a released certificate."""
    _require_revision_text(software_version, "Software version")
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.REVISE_RELEASED_CERTIFICATE,
        timestamp=timestamp,
    )

    with connection:
        job_repository = SQLiteCalibrationJobRepository(connection, autocommit=False)
        certificate_repository = SQLiteCertificateRecordRepository(
            connection,
            autocommit=False,
        )
        revision_repository = SQLiteCertificateRevisionRepository(
            connection,
            autocommit=False,
        )
        audit_repository = SQLiteAuditEventRepository(connection, autocommit=False)

        try:
            certificate = certificate_repository.get(certificate_id)
        except RecordNotFoundError as exc:
            raise CertificateRevisionServiceError(
                "Certificate revision requires an existing released certificate."
            ) from exc
        job = job_repository.get(certificate.job_id)
        if job.state is not WorkflowState.RELEASED:
            raise CertificateRevisionServiceError(
                "Certificate revision requires released workflow state."
            )

        try:
            revision = create_revision_record(
                revision_id=revision_id,
                original=certificate,
                reason=reason,
                revised_by=actor.user_id,
                revised_at=timestamp,
            )
        except CertificateRecordError as exc:
            raise CertificateRevisionServiceError(str(exc)) from exc

        try:
            revision_repository.add(revision)
        except PersistenceError as exc:
            raise CertificateRevisionServiceError(str(exc)) from exc
        revision_audit_event = _certificate_revision_audit_event(
            certificate=certificate,
            revision=revision,
            software_version=software_version,
            timestamp=timestamp,
        )
        revision_audit_event_id = audit_repository.append(revision_audit_event)
        transition = transition_calibration_job(
            job_id=job.id,
            current=job.state,
            target=WorkflowState.REVISED,
            user_id=actor.user_id,
            software_version=software_version,
            timestamp=timestamp,
            reason=revision.reason,
        )
        job_repository.update_state(
            job_id=job.id,
            expected_state=job.state,
            new_state=transition.state,
        )
        workflow_audit_event_id = audit_repository.append(transition.audit_event)

    return CertificateRevisionRegistration(
        revision=revision,
        revision_audit_event_id=revision_audit_event_id,
        revision_audit_event=revision_audit_event,
        workflow_audit_event_id=workflow_audit_event_id,
        workflow_audit_event=transition.audit_event,
    )


def _preview_from_summaries(
    *,
    job_id: str,
    generated_by: str,
    generated_at: datetime,
    discipline: Discipline,
    software_version: str,
    template_version: str,
    metadata: CertificateMetadata,
    duts: tuple[DeviceUnderTest, ...],
    selected_reference_equipment: tuple[SelectedReferenceEquipment, ...],
    summaries: tuple[MeasurementPointSummary, ...],
    accreditation_mark_allowed: bool,
) -> CertificatePreview:
    calculation_engine_version = _single_version(
        {summary.calculation_engine_version for summary in summaries},
        "calculation engine",
    )
    constant_set_version = _single_version(
        {summary.constant_set_version for summary in summaries},
        "constant set",
    )
    budget_version = _single_version(
        {summary.budget_version for summary in summaries},
        "budget",
    )
    try:
        return CertificatePreview(
            job_id=job_id,
            generated_by=generated_by,
            generated_at=generated_at,
            discipline=discipline,
            software_version=software_version,
            calculation_engine_version=calculation_engine_version,
            constant_set_version=constant_set_version,
            budget_version=budget_version,
            template_version=template_version,
            metadata=metadata,
            duts=tuple(_preview_dut(dut) for dut in duts),
            reference_equipment=tuple(
                _preview_reference_equipment(selection)
                for selection in selected_reference_equipment
            ),
            rows=tuple(_preview_row(summary) for summary in summaries),
            accreditation_mark_allowed=accreditation_mark_allowed,
        )
    except CertificatePreviewError as exc:
        raise CertificatePreviewServiceError(str(exc)) from exc


def _preview_row(summary: MeasurementPointSummary) -> CertificatePreviewRow:
    return CertificatePreviewRow(
        point_id=summary.point_id,
        dut_id=summary.dut_id,
        measurement_window_id=summary.measurement_window_id,
        reference=summary.reference,
        indication=summary.indication,
        error_of_indication=summary.error_of_indication,
        display_error_of_indication=summary.display_error_of_indication,
        reported_expanded_uncertainty=summary.reported_expanded_uncertainty,
        unit=summary.unit,
    )


def _preview_dut(dut: DeviceUnderTest) -> CertificatePreviewDut:
    return CertificatePreviewDut(
        dut_id=dut.id,
        make=dut.make,
        model=dut.model,
        serial_number=dut.serial_number,
        channel_id=dut.channel_id,
    )


def _preview_reference_equipment(
    selection: SelectedReferenceEquipment,
) -> CertificatePreviewReferenceEquipment:
    equipment = selection.equipment
    return CertificatePreviewReferenceEquipment(
        equipment_id=equipment.id,
        simval_id=equipment.simval_id,
        equipment_type=equipment.equipment_type,
        serial_number=equipment.serial_number,
        calibration_certificate_reference=(
            equipment.calibration_certificate_reference
        ),
        calibration_due_date=equipment.calibration_due_date,
        range_minimum=equipment.usable_range.minimum,
        range_maximum=equipment.usable_range.maximum,
        range_unit=equipment.usable_range.unit,
        traceability_statement=equipment.traceability_statement,
    )


def _reference_equipment_suitability_blockers(
    *,
    job,
    metadata: CertificateMetadata,
    selected_reference_equipment: tuple[SelectedReferenceEquipment, ...],
    summaries: tuple[MeasurementPointSummary, ...],
) -> tuple[str, ...]:
    blockers: list[str] = []
    for summary in summaries:
        point_blockers: list[str] = []
        for selection in selected_reference_equipment:
            equipment_blockers = reference_equipment_blockers(
                selection.equipment,
                use_date=metadata.calibration_date,
                point=summary.reference,
                unit=summary.unit,
                discipline=job.discipline,
            )
            if len(equipment_blockers) == 0:
                point_blockers = []
                break
            point_blockers.extend(equipment_blockers)
        blockers.extend(
            f"{summary.point_id}:{blocker}" for blocker in _unique(point_blockers)
        )
    return tuple(blockers)


def _reference_equipment_suitability_message(blockers: tuple[str, ...]) -> str:
    return (
        "Reference equipment is not suitable for certificate points: "
        + ", ".join(blockers)
    )


def _unique(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return tuple(unique_values)


def _reference_equipment_selection_audit_event(
    *,
    selection: SelectedReferenceEquipment,
    software_version: str,
    timestamp: datetime,
) -> AuditEvent:
    equipment = selection.equipment
    return AuditEvent(
        entity_type="calibration_job",
        entity_id=selection.job_id,
        action=AuditAction.REFERENCE_EQUIPMENT_SELECTED,
        user_id=selection.selected_by,
        timestamp=timestamp,
        new_value={
            "equipment_id": equipment.id,
            "simval_id": equipment.simval_id,
            "equipment_type": equipment.equipment_type,
            "serial_number": equipment.serial_number,
            "calibration_certificate_reference": (
                equipment.calibration_certificate_reference
            ),
            "calibration_due_date": (
                equipment.calibration_due_date.isoformat()
            ),
            "range": _equipment_range_text(equipment),
            "selected_at": selection.selected_at.isoformat(),
        },
        software_version=software_version,
    )


def _certificate_metadata_audit_event(
    *,
    metadata: CertificateMetadata,
    software_version: str,
    timestamp: datetime,
) -> AuditEvent:
    return AuditEvent(
        entity_type="calibration_job",
        entity_id=metadata.job_id,
        action=AuditAction.METADATA_CHANGED,
        user_id=metadata.recorded_by,
        timestamp=timestamp,
        new_value={
            "certificate_date": metadata.certificate_date.isoformat(),
            "calibration_date": metadata.calibration_date.isoformat(),
            "receipt_date": metadata.receipt_date.isoformat(),
            "task_number": metadata.task_number,
            "purchase_order": metadata.purchase_order,
            "client_name": metadata.client_name,
            "procedure": metadata.procedure,
            "place": metadata.place,
            "temperature_scale": metadata.temperature_scale,
            "recorded_at": metadata.recorded_at.isoformat(),
        },
        software_version=software_version,
    )


def _preview_audit_event(preview: CertificatePreview) -> AuditEvent:
    return AuditEvent(
        entity_type="calibration_job",
        entity_id=preview.job_id,
        action=AuditAction.CERTIFICATE_PREVIEW_GENERATED,
        user_id=preview.generated_by,
        timestamp=preview.generated_at,
        new_value={
            "summary_ids": list(preview.summary_ids),
            "dut_ids": [dut.dut_id for dut in preview.duts],
            "reference_equipment_ids": [
                equipment.equipment_id for equipment in preview.reference_equipment
            ],
            "metadata_recorded_at": preview.metadata.recorded_at.isoformat(),
            "discipline": preview.discipline.value,
            "row_count": len(preview.rows),
            "template_version": preview.template_version,
            "accreditation_mark_allowed": preview.accreditation_mark_allowed,
        },
        software_version=preview.software_version,
        calculation_engine_version=preview.calculation_engine_version,
        constant_set_version=preview.constant_set_version,
        budget_version=preview.budget_version,
    )


def _matching_preview_exists(
    audit_events: tuple[AuditEvent, ...],
    *,
    summary_ids: tuple[str, ...],
    template_version: str,
    software_version: str,
    calculation_engine_version: str,
    constant_set_version: str,
    budget_version: str,
    accreditation_mark_allowed: bool,
) -> bool:
    return (
        _matching_preview_event(
            audit_events,
            summary_ids=summary_ids,
            template_version=template_version,
            software_version=software_version,
            calculation_engine_version=calculation_engine_version,
            constant_set_version=constant_set_version,
            budget_version=budget_version,
            accreditation_mark_allowed=accreditation_mark_allowed,
        )
        is not None
    )


def _matching_preview_event(
    audit_events: tuple[AuditEvent, ...],
    *,
    summary_ids: tuple[str, ...],
    template_version: str,
    software_version: str,
    calculation_engine_version: str,
    constant_set_version: str,
    budget_version: str,
    accreditation_mark_allowed: bool,
) -> AuditEvent | None:
    expected_summary_ids = list(summary_ids)
    for event in audit_events:
        if event.action is not AuditAction.CERTIFICATE_PREVIEW_GENERATED:
            continue
        if event.new_value is None:
            continue
        if event.new_value.get("summary_ids") != expected_summary_ids:
            continue
        if event.new_value.get("template_version") != template_version:
            continue
        if (
            event.new_value.get("accreditation_mark_allowed", True)
            != accreditation_mark_allowed
        ):
            continue
        if event.software_version != software_version:
            continue
        if event.calculation_engine_version != calculation_engine_version:
            continue
        if event.constant_set_version != constant_set_version:
            continue
        if event.budget_version != budget_version:
            continue
        return event
    return None


def _qa_approval_evidence(
    audit_events: tuple[AuditEvent, ...],
) -> _ApprovalEvidence | None:
    approval_events = [
        event
        for event in audit_events
        if event.action is AuditAction.WORKFLOW_TRANSITIONED
        and event.new_value is not None
        and event.new_value.get("state") == WorkflowState.APPROVED.value
    ]
    if len(approval_events) == 0:
        return None
    latest = max(approval_events, key=lambda event: event.timestamp)
    return _ApprovalEvidence(
        approved_by=latest.user_id,
        approved_at=latest.timestamp,
    )


def _export_artifact_audit_event(
    *,
    certificate: CertificateRecord,
    artifact: ExportArtifact,
    timestamp: datetime,
) -> AuditEvent:
    return AuditEvent(
        entity_type="calibration_job",
        entity_id=certificate.job_id,
        action=AuditAction.EXPORT_ARTIFACT_GENERATED,
        user_id=artifact.generated_by,
        timestamp=timestamp,
        new_value={
            "artifact_id": artifact.artifact_id,
            "artifact_type": artifact.artifact_type.value,
            "certificate_id": certificate.certificate_id,
            "checksum_sha256": artifact.checksum_sha256,
            "filename": artifact.filename,
            "storage_uri": artifact.storage_uri,
        },
        software_version=certificate.software_version,
        calculation_engine_version=certificate.calculation_engine_version,
        constant_set_version=certificate.constant_set_version,
        budget_version=certificate.budget_version,
    )


def _certificate_release_audit_event(
    *,
    certificate: CertificateRecord,
    accreditation_mark_allowed: bool,
    timestamp: datetime,
) -> AuditEvent:
    return AuditEvent(
        entity_type="calibration_job",
        entity_id=certificate.job_id,
        action=AuditAction.CERTIFICATE_RELEASED,
        user_id=certificate.released_by or "",
        timestamp=timestamp,
        new_value={
            "calculation_summary_ids": list(certificate.calculation_summary_ids),
            "certificate_id": certificate.certificate_id,
            "certificate_number": certificate.certificate_number,
            "approved_by": certificate.approved_by,
            "approved_at": (
                certificate.approved_at.isoformat()
                if certificate.approved_at is not None
                else None
            ),
            "released_by": certificate.released_by,
            "released_at": (
                certificate.released_at.isoformat()
                if certificate.released_at is not None
                else None
            ),
            "template_version": certificate.template_version,
            "accreditation_mark_allowed": accreditation_mark_allowed,
        },
        software_version=certificate.software_version,
        calculation_engine_version=certificate.calculation_engine_version,
        constant_set_version=certificate.constant_set_version,
        budget_version=certificate.budget_version,
    )


def _certificate_revision_audit_event(
    *,
    certificate: CertificateRecord,
    revision: CertificateRevision,
    software_version: str,
    timestamp: datetime,
) -> AuditEvent:
    return AuditEvent(
        entity_type="calibration_job",
        entity_id=certificate.job_id,
        action=AuditAction.CERTIFICATE_REVISED,
        user_id=revision.revised_by,
        timestamp=timestamp,
        previous_value={
            "certificate_id": certificate.certificate_id,
            "certificate_number": certificate.certificate_number,
            "status": certificate.status.value,
        },
        new_value={
            "revision_id": revision.revision_id,
            "original_certificate_id": revision.original_certificate_id,
            "original_certificate_number": revision.original_certificate_number,
            "revised_at": revision.revised_at.isoformat(),
        },
        reason=revision.reason,
        software_version=software_version,
        calculation_engine_version=certificate.calculation_engine_version,
        constant_set_version=certificate.constant_set_version,
        budget_version=certificate.budget_version,
    )


def _single_release_version(versions: set[str], label: str) -> str:
    try:
        return _single_version(versions, label)
    except CertificatePreviewServiceError as exc:
        raise CertificateReleaseServiceError(str(exc)) from exc


def _artifact_by_id(
    certificate: CertificateRecord,
    artifact_id: str,
) -> ExportArtifact:
    for artifact in certificate.export_artifacts:
        if artifact.artifact_id == artifact_id:
            return artifact
    raise CertificatePreviewServiceError(
        f"Artifact {artifact_id!r} was not found for the released certificate."
    )


def _validate_release_inputs(
    *,
    job_id: str,
    certificate_id: str,
    certificate_number: str,
    artifact_id: str,
    filename: str,
    checksum_sha256: str,
    storage_uri: str,
    released_by: str,
    template_version: str,
    software_version: str,
    timestamp: datetime,
) -> None:
    _require_release_text(job_id, "Job id")
    _require_release_text(certificate_id, "Certificate id")
    _require_release_text(certificate_number, "Certificate number")
    _require_release_text(artifact_id, "Artifact id")
    _require_release_text(filename, "Artifact filename")
    _require_release_text(checksum_sha256, "Artifact checksum")
    _require_release_text(storage_uri, "Artifact storage URI")
    _require_release_text(released_by, "Released by")
    _require_release_text(template_version, "Template version")
    _require_release_text(software_version, "Software version")
    _require_release_timezone_aware(timestamp, "Release timestamp")


def _require_release_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise CertificateReleaseServiceError(f"{field_name} is required.")


def _require_metadata_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise CertificateMetadataServiceError(f"{field_name} is required.")


def _require_reference_equipment_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise CertificateReferenceEquipmentServiceError(
            f"{field_name} is required."
        )


def _require_revision_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise CertificateRevisionServiceError(f"{field_name} is required.")


def _require_history_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise CertificatePreviewServiceError(f"{field_name} is required.")


def _equipment_range_text(equipment: ReferenceEquipment) -> str:
    return (
        f"{equipment.usable_range.minimum:g} to "
        f"{equipment.usable_range.maximum:g} {equipment.usable_range.unit}"
    )


def _require_release_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CertificateReleaseServiceError(f"{field_name} must be timezone-aware.")


def _single_version(versions: set[str], label: str) -> str:
    if len(versions) != 1:
        raise CertificatePreviewServiceError(
            f"Certificate preview requires one {label} version across summaries."
        )
    return next(iter(versions))


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise CertificatePreviewServiceError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CertificatePreviewServiceError(f"{field_name} must be timezone-aware.")
