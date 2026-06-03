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
    CertificateStatus,
    ExportArtifact,
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
    store_rendered_artifact,
)
from app.backend.domain.equipment import SelectedReferenceEquipment
from app.backend.domain.entities import DeviceUnderTest
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    RecordNotFoundError,
    SQLiteAuditEventRepository,
    SQLiteCalibrationJobRepository,
    SQLiteCertificateMetadataRepository,
    SQLiteCertificateRecordRepository,
    SQLiteDeviceUnderTestRepository,
    SQLiteMeasurementPointSummaryRepository,
    SQLiteSelectedReferenceEquipmentRepository,
)
from app.backend.services.authentication import resolve_actor_for_action
from app.backend.services.workflow import transition_calibration_job
from app.calculation_engine.common.summary import MeasurementPointSummary


class CertificatePreviewServiceError(ValueError):
    """Raised when a certificate preview cannot be generated safely."""


class CertificateReleaseServiceError(ValueError):
    """Raised when a certificate cannot be released safely."""


class CertificateMetadataServiceError(ValueError):
    """Raised when certificate metadata cannot be captured safely."""


@dataclass(frozen=True, slots=True)
class CertificateMetadataCapture:
    metadata: CertificateMetadata
    metadata_audit_event_id: int
    metadata_audit_event: AuditEvent
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


def build_certificate_preview_for_session(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    job_id: str,
    template_version: str,
    software_version: str,
    timestamp: datetime,
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

        preview = _preview_from_summaries(
            job_id=job_id,
            generated_by=generated_by,
            generated_at=timestamp,
            software_version=software_version,
            template_version=template_version,
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
) -> RenderedCertificateRelease:
    """Render, store, and release a PDF certificate from locked preview evidence."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.RELEASE_CERTIFICATE,
        timestamp=timestamp,
    )
    preview = _preview_for_release_rendering(
        connection=connection,
        job_id=job_id,
        template_version=template_version,
        software_version=software_version,
    )
    rendered_artifact = render_certificate_pdf(
        certificate_id=certificate_id,
        certificate_number=certificate_number,
        preview=preview,
    )
    stored_artifact = store_rendered_artifact(
        base_path=artifact_directory,
        artifact=rendered_artifact,
    )
    release = release_certificate(
        connection=connection,
        job_id=job_id,
        certificate_id=certificate_id,
        certificate_number=certificate_number,
        artifact_id=artifact_id,
        artifact_type=rendered_artifact.artifact_type,
        filename=stored_artifact.filename,
        checksum_sha256=stored_artifact.checksum_sha256,
        storage_uri=stored_artifact.storage_uri,
        released_by=actor.user_id,
        template_version=template_version,
        software_version=software_version,
        timestamp=timestamp,
    )
    return RenderedCertificateRelease(
        rendered_artifact=rendered_artifact,
        stored_artifact=stored_artifact,
        release=release,
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
) -> CertificateRelease:
    """Release a certificate only after matching preview evidence exists."""
    actor = resolve_actor_for_action(
        connection=connection,
        session_id=session_id,
        action=Action.RELEASE_CERTIFICATE,
        timestamp=timestamp,
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
        timestamp=timestamp,
    )


def _preview_for_release_rendering(
    *,
    connection: sqlite3.Connection,
    job_id: str,
    template_version: str,
    software_version: str,
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
            software_version=software_version,
            template_version=template_version,
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
        job_repository = SQLiteCalibrationJobRepository(connection, autocommit=False)
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
        if not _matching_preview_exists(
            audit_repository.list_for_entity("calibration_job", job_id),
            summary_ids=summary_ids,
            template_version=template_version,
            software_version=software_version,
            calculation_engine_version=calculation_engine_version,
            constant_set_version=constant_set_version,
            budget_version=budget_version,
        ):
            raise CertificateReleaseServiceError(
                "Certificate release requires matching preview audit evidence."
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
            approved_by=released_by,
            approved_at=timestamp,
            released_by=released_by,
            released_at=timestamp,
        )
        certificate_repository.add(certificate)

        export_audit_event = _export_artifact_audit_event(
            certificate=certificate,
            artifact=artifact,
            timestamp=timestamp,
        )
        export_audit_event_id = audit_repository.append(export_audit_event)
        release_audit_event = _certificate_release_audit_event(
            certificate=certificate,
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
        export_audit_event_id=export_audit_event_id,
        export_audit_event=export_audit_event,
        release_audit_event_id=release_audit_event_id,
        release_audit_event=release_audit_event,
        workflow_audit_event_id=workflow_audit_event_id,
        workflow_audit_event=transition.audit_event,
    )


def _preview_from_summaries(
    *,
    job_id: str,
    generated_by: str,
    generated_at: datetime,
    software_version: str,
    template_version: str,
    metadata: CertificateMetadata,
    duts: tuple[DeviceUnderTest, ...],
    selected_reference_equipment: tuple[SelectedReferenceEquipment, ...],
    summaries: tuple[MeasurementPointSummary, ...],
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
            "row_count": len(preview.rows),
            "template_version": preview.template_version,
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
            "template_version": certificate.template_version,
        },
        software_version=certificate.software_version,
        calculation_engine_version=certificate.calculation_engine_version,
        constant_set_version=certificate.constant_set_version,
        budget_version=certificate.budget_version,
    )


def _single_release_version(versions: set[str], label: str) -> str:
    try:
        return _single_version(versions, label)
    except CertificatePreviewServiceError as exc:
        raise CertificateReleaseServiceError(str(exc)) from exc


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
