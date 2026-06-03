"""FastAPI application factory for controlled backend services."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import sqlite3

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict

from app.backend.api.database import sqlite_connection_scope
from app.backend.api.settings import ApiSettings
from app.backend.certificates.storage import CertificateArtifactStorageError
from app.backend.certificates.records import ArtifactType
from app.backend.domain.entities import Discipline, DomainValidationError
from app.backend.domain.equipment import (
    EquipmentRange,
    EquipmentStatus,
    ReferenceEquipment,
)
from app.backend.services.authentication import (
    AuthenticationFailureError,
    AuthenticationServiceError,
    AuthorizationServiceError,
    resolve_actor_for_session,
)
from app.backend.services.certificates import (
    CertificateMetadataCapture,
    CertificateMetadataServiceError,
    CertificateReferenceEquipmentSelection,
    CertificateReferenceEquipmentServiceError,
    CertificateRelease,
    CertificateReleaseServiceError,
    CertificatePreviewGeneration,
    CertificatePreviewServiceError,
    build_certificate_preview_for_session,
    capture_certificate_metadata_for_session,
    release_certificate_for_session,
    render_and_release_certificate_pdf_for_session,
    select_reference_equipment_for_session,
)


class ApiError(BaseModel):
    detail: str


class ActorResponse(BaseModel):
    user_id: str
    display_name: str
    roles: tuple[str, ...]


class CertificatePreviewRequest(BaseModel):
    job_id: str
    template_version: str
    software_version: str
    accreditation_mark_allowed: bool


class CertificateMetadataRequest(BaseModel):
    job_id: str
    certificate_date: date
    calibration_date: date
    receipt_date: date
    task_number: str
    purchase_order: str
    client_name: str
    client_address: str
    procedure: str
    place: str
    approved_by_label: str
    remarks: str
    traceability_statement: str
    uncertainty_statement: str
    ambient_conditions: str
    temperature_scale: str
    software_version: str


class CertificateMetadataResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    job_id: str
    certificate_date: str
    calibration_date: str
    receipt_date: str
    task_number: str
    purchase_order: str
    client_name: str
    client_address: str
    procedure: str
    place: str
    approved_by_label: str
    remarks: str
    traceability_statement: str
    uncertainty_statement: str
    ambient_conditions: str
    temperature_scale: str
    recorded_by: str
    recorded_at: str
    metadata_audit_event_id: int
    workflow_audit_event_id: int
    workflow_state: str


class ReferenceEquipmentSelectionRequest(BaseModel):
    job_id: str
    equipment_id: str
    simval_id: str
    equipment_type: str
    serial_number: str
    discipline: Discipline
    calibration_certificate_reference: str
    calibration_due_date: date
    status: EquipmentStatus
    range_minimum: float
    range_maximum: float
    range_unit: str
    traceability_statement: str
    software_version: str


class ReferenceEquipmentSelectionResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    job_id: str
    equipment_id: str
    simval_id: str
    equipment_type: str
    serial_number: str
    discipline: str
    calibration_certificate_reference: str
    calibration_due_date: str
    status: str
    range_minimum: float
    range_maximum: float
    range_unit: str
    traceability_statement: str
    selected_by: str
    selected_at: str
    selection_audit_event_id: int
    workflow_audit_event_id: int
    workflow_state: str


class CertificatePreviewRowResponse(BaseModel):
    point_id: str
    dut_id: str
    measurement_window_id: str
    reference: float
    indication: float
    error_of_indication: float
    display_error_of_indication: str
    reported_expanded_uncertainty: str
    unit: str


class CertificatePreviewReferenceEquipmentResponse(BaseModel):
    equipment_id: str
    simval_id: str
    equipment_type: str
    serial_number: str
    calibration_certificate_reference: str
    calibration_due_date: str
    range_minimum: float
    range_maximum: float
    range_unit: str
    traceability_statement: str


class CertificatePreviewResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    job_id: str
    generated_by: str
    generated_at: str
    software_version: str
    calculation_engine_version: str
    constant_set_version: str
    budget_version: str
    template_version: str
    accreditation_mark_allowed: bool
    summary_ids: tuple[str, ...]
    reference_equipment: tuple[CertificatePreviewReferenceEquipmentResponse, ...]
    rows: tuple[CertificatePreviewRowResponse, ...]
    audit_event_id: int


class CertificateReleaseRequest(BaseModel):
    job_id: str
    certificate_id: str
    certificate_number: str
    artifact_id: str
    artifact_type: ArtifactType
    filename: str
    checksum_sha256: str
    storage_uri: str
    template_version: str
    software_version: str
    accreditation_mark_allowed: bool


class RenderedCertificateReleaseRequest(BaseModel):
    job_id: str
    certificate_id: str
    certificate_number: str
    artifact_id: str
    template_version: str
    software_version: str
    accreditation_mark_allowed: bool


class ExportArtifactResponse(BaseModel):
    artifact_id: str
    artifact_type: str
    filename: str
    checksum_sha256: str
    storage_uri: str
    generated_by: str
    generated_at: str


class CertificateReleaseResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    certificate_id: str
    job_id: str
    certificate_number: str
    status: str
    calculation_summary_ids: tuple[str, ...]
    software_version: str
    calculation_engine_version: str
    constant_set_version: str
    budget_version: str
    template_version: str
    accreditation_mark_allowed: bool
    released_by: str
    released_at: str
    artifacts: tuple[ExportArtifactResponse, ...]
    export_audit_event_id: int
    release_audit_event_id: int
    workflow_audit_event_id: int


def create_app(
    *,
    connection: sqlite3.Connection | None = None,
    connection_provider: (
        Callable[[], AbstractContextManager[sqlite3.Connection]] | None
    ) = None,
    clock: Callable[[], datetime] | None = None,
    artifact_directory: Path | None = None,
) -> FastAPI:
    """Create the backend API with an injected connection or connection scope."""
    if connection is None and connection_provider is None:
        raise ValueError("A connection or connection provider is required.")
    if connection is not None and connection_provider is not None:
        raise ValueError("Provide either connection or connection provider, not both.")
    connection_scope = (
        connection_provider
        if connection_provider is not None
        else lambda: _fixed_connection_scope(connection)
    )
    app = FastAPI(title="SIMVal Calibration Certificate API")
    clock_fn = clock or _utc_now

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        "/me",
        response_model=ActorResponse,
        responses={401: {"model": ApiError}},
    )
    def me(x_session_id: str = Header(alias="X-Session-Id")) -> ActorResponse:
        try:
            with connection_scope() as scoped_connection:
                actor = resolve_actor_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    timestamp=clock_fn(),
                )
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        return ActorResponse(
            user_id=actor.user_id,
            display_name=actor.display_name,
            roles=tuple(role.value for role in actor.roles),
        )

    @app.post(
        "/certificate-metadata",
        response_model=CertificateMetadataResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def certificate_metadata(
        request: CertificateMetadataRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> CertificateMetadataResponse:
        try:
            with connection_scope() as scoped_connection:
                result = capture_certificate_metadata_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=request.job_id,
                    certificate_date=request.certificate_date,
                    calibration_date=request.calibration_date,
                    receipt_date=request.receipt_date,
                    task_number=request.task_number,
                    purchase_order=request.purchase_order,
                    client_name=request.client_name,
                    client_address=request.client_address,
                    procedure=request.procedure,
                    place=request.place,
                    approved_by_label=request.approved_by_label,
                    remarks=request.remarks,
                    traceability_statement=request.traceability_statement,
                    uncertainty_statement=request.uncertainty_statement,
                    ambient_conditions=request.ambient_conditions,
                    temperature_scale=request.temperature_scale,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except CertificateMetadataServiceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _metadata_response(result)

    @app.post(
        "/reference-equipment-selections",
        response_model=ReferenceEquipmentSelectionResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def reference_equipment_selection(
        request: ReferenceEquipmentSelectionRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> ReferenceEquipmentSelectionResponse:
        try:
            equipment = ReferenceEquipment(
                id=request.equipment_id,
                simval_id=request.simval_id,
                equipment_type=request.equipment_type,
                serial_number=request.serial_number,
                discipline=request.discipline,
                calibration_certificate_reference=(
                    request.calibration_certificate_reference
                ),
                calibration_due_date=request.calibration_due_date,
                status=request.status,
                usable_range=EquipmentRange(
                    minimum=request.range_minimum,
                    maximum=request.range_maximum,
                    unit=request.range_unit,
                ),
                traceability_statement=request.traceability_statement,
            )
            with connection_scope() as scoped_connection:
                result = select_reference_equipment_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=request.job_id,
                    equipment=equipment,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (
            CertificateReferenceEquipmentServiceError,
            DomainValidationError,
        ) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _reference_equipment_selection_response(result)

    @app.post(
        "/certificate-previews",
        response_model=CertificatePreviewResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def certificate_preview(
        request: CertificatePreviewRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> CertificatePreviewResponse:
        try:
            with connection_scope() as scoped_connection:
                result = build_certificate_preview_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=request.job_id,
                    template_version=request.template_version,
                    software_version=request.software_version,
                    accreditation_mark_allowed=(
                        request.accreditation_mark_allowed
                    ),
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except CertificatePreviewServiceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _preview_response(result)

    @app.post(
        "/certificate-releases",
        response_model=CertificateReleaseResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def certificate_release(
        request: CertificateReleaseRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> CertificateReleaseResponse:
        try:
            with connection_scope() as scoped_connection:
                result = release_certificate_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=request.job_id,
                    certificate_id=request.certificate_id,
                    certificate_number=request.certificate_number,
                    artifact_id=request.artifact_id,
                    artifact_type=request.artifact_type,
                    filename=request.filename,
                    checksum_sha256=request.checksum_sha256,
                    storage_uri=request.storage_uri,
                    template_version=request.template_version,
                    software_version=request.software_version,
                    accreditation_mark_allowed=(
                        request.accreditation_mark_allowed
                    ),
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except CertificateReleaseServiceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _release_response(result)

    @app.post(
        "/certificate-rendered-releases",
        response_model=CertificateReleaseResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def certificate_rendered_release(
        request: RenderedCertificateReleaseRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> CertificateReleaseResponse:
        if artifact_directory is None:
            raise HTTPException(
                status_code=409,
                detail="Artifact storage path is not configured.",
            )
        try:
            with connection_scope() as scoped_connection:
                result = render_and_release_certificate_pdf_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=request.job_id,
                    certificate_id=request.certificate_id,
                    certificate_number=request.certificate_number,
                    artifact_id=request.artifact_id,
                    artifact_directory=artifact_directory,
                    template_version=request.template_version,
                    software_version=request.software_version,
                    accreditation_mark_allowed=(
                        request.accreditation_mark_allowed
                    ),
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (CertificateReleaseServiceError, CertificateArtifactStorageError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _release_response(result.release)

    return app


def create_app_from_settings(
    settings: ApiSettings,
    *,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    """Create the backend API from runtime settings."""
    return create_app(
        connection_provider=lambda: sqlite_connection_scope(settings.database_path),
        clock=clock,
        artifact_directory=settings.artifact_storage_path,
    )


def _preview_response(
    result: CertificatePreviewGeneration,
) -> CertificatePreviewResponse:
    preview = result.preview
    return CertificatePreviewResponse(
        job_id=preview.job_id,
        generated_by=preview.generated_by,
        generated_at=preview.generated_at.isoformat(),
        software_version=preview.software_version,
        calculation_engine_version=preview.calculation_engine_version,
        constant_set_version=preview.constant_set_version,
        budget_version=preview.budget_version,
        template_version=preview.template_version,
        accreditation_mark_allowed=preview.accreditation_mark_allowed,
        summary_ids=preview.summary_ids,
        reference_equipment=tuple(
            CertificatePreviewReferenceEquipmentResponse(
                equipment_id=equipment.equipment_id,
                simval_id=equipment.simval_id,
                equipment_type=equipment.equipment_type,
                serial_number=equipment.serial_number,
                calibration_certificate_reference=(
                    equipment.calibration_certificate_reference
                ),
                calibration_due_date=equipment.calibration_due_date.isoformat(),
                range_minimum=equipment.range_minimum,
                range_maximum=equipment.range_maximum,
                range_unit=equipment.range_unit,
                traceability_statement=equipment.traceability_statement,
            )
            for equipment in preview.reference_equipment
        ),
        rows=tuple(
            CertificatePreviewRowResponse(
                point_id=row.point_id,
                dut_id=row.dut_id,
                measurement_window_id=row.measurement_window_id,
                reference=row.reference,
                indication=row.indication,
                error_of_indication=row.error_of_indication,
                display_error_of_indication=_decimal_to_text(
                    row.display_error_of_indication
                ),
                reported_expanded_uncertainty=_decimal_to_text(
                    row.reported_expanded_uncertainty
                ),
                unit=row.unit,
            )
            for row in preview.rows
        ),
        audit_event_id=result.audit_event_id,
    )


def _metadata_response(result: CertificateMetadataCapture) -> CertificateMetadataResponse:
    metadata = result.metadata
    workflow_state = ""
    if result.workflow_audit_event.new_value is not None:
        workflow_state = str(result.workflow_audit_event.new_value["state"])
    return CertificateMetadataResponse(
        job_id=metadata.job_id,
        certificate_date=metadata.certificate_date.isoformat(),
        calibration_date=metadata.calibration_date.isoformat(),
        receipt_date=metadata.receipt_date.isoformat(),
        task_number=metadata.task_number,
        purchase_order=metadata.purchase_order,
        client_name=metadata.client_name,
        client_address=metadata.client_address,
        procedure=metadata.procedure,
        place=metadata.place,
        approved_by_label=metadata.approved_by_label,
        remarks=metadata.remarks,
        traceability_statement=metadata.traceability_statement,
        uncertainty_statement=metadata.uncertainty_statement,
        ambient_conditions=metadata.ambient_conditions,
        temperature_scale=metadata.temperature_scale,
        recorded_by=metadata.recorded_by,
        recorded_at=metadata.recorded_at.isoformat(),
        metadata_audit_event_id=result.metadata_audit_event_id,
        workflow_audit_event_id=result.workflow_audit_event_id,
        workflow_state=workflow_state,
    )


def _reference_equipment_selection_response(
    result: CertificateReferenceEquipmentSelection,
) -> ReferenceEquipmentSelectionResponse:
    selection = result.selection
    equipment = selection.equipment
    workflow_state = ""
    if result.workflow_audit_event.new_value is not None:
        workflow_state = str(result.workflow_audit_event.new_value["state"])
    return ReferenceEquipmentSelectionResponse(
        job_id=selection.job_id,
        equipment_id=equipment.id,
        simval_id=equipment.simval_id,
        equipment_type=equipment.equipment_type,
        serial_number=equipment.serial_number,
        discipline=equipment.discipline.value,
        calibration_certificate_reference=(
            equipment.calibration_certificate_reference
        ),
        calibration_due_date=equipment.calibration_due_date.isoformat(),
        status=equipment.status.value,
        range_minimum=equipment.usable_range.minimum,
        range_maximum=equipment.usable_range.maximum,
        range_unit=equipment.usable_range.unit,
        traceability_statement=equipment.traceability_statement,
        selected_by=selection.selected_by,
        selected_at=selection.selected_at.isoformat(),
        selection_audit_event_id=result.selection_audit_event_id,
        workflow_audit_event_id=result.workflow_audit_event_id,
        workflow_state=workflow_state,
    )


def _release_response(result: CertificateRelease) -> CertificateReleaseResponse:
    certificate = result.certificate
    return CertificateReleaseResponse(
        certificate_id=certificate.certificate_id,
        job_id=certificate.job_id,
        certificate_number=certificate.certificate_number,
        status=certificate.status.value,
        calculation_summary_ids=certificate.calculation_summary_ids,
        software_version=certificate.software_version,
        calculation_engine_version=certificate.calculation_engine_version,
        constant_set_version=certificate.constant_set_version,
        budget_version=certificate.budget_version,
        template_version=certificate.template_version,
        accreditation_mark_allowed=result.accreditation_mark_allowed,
        released_by=certificate.released_by or "",
        released_at=(
            certificate.released_at.isoformat()
            if certificate.released_at is not None
            else ""
        ),
        artifacts=tuple(
            _artifact_response(artifact) for artifact in certificate.export_artifacts
        ),
        export_audit_event_id=result.export_audit_event_id,
        release_audit_event_id=result.release_audit_event_id,
        workflow_audit_event_id=result.workflow_audit_event_id,
    )


def _artifact_response(artifact) -> ExportArtifactResponse:
    return ExportArtifactResponse(
        artifact_id=artifact.artifact_id,
        artifact_type=artifact.artifact_type.value,
        filename=artifact.filename,
        checksum_sha256=artifact.checksum_sha256,
        storage_uri=artifact.storage_uri,
        generated_by=artifact.generated_by,
        generated_at=artifact.generated_at.isoformat(),
    )


def _decimal_to_text(value: Decimal) -> str:
    return format(value, "f")


@contextmanager
def _fixed_connection_scope(
    connection: sqlite3.Connection | None,
) -> sqlite3.Connection:
    if connection is None:
        raise ValueError("A fixed connection is required.")
    yield connection


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
