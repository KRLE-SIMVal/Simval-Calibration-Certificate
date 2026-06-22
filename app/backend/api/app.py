"""FastAPI application factory for controlled backend services."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sqlite3
import uuid

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.api.database import sqlite_connection_scope
from app.backend.api.settings import AuthProvider, ApiSettings
from app.backend.auth.entra import EntraTokenVerifier, PyJwtEntraTokenVerifier
from app.backend.auth.permissions import Action, Role
from app.backend.auth.users import UserAccount, UserIdentityError
from app.backend.certificates.storage import (
    CertificateArtifactStorageError,
    verified_stored_artifact_path,
)
from app.backend.certificates.records import ArtifactType
from app.backend.certificates.rendering import (
    CertificateRenderingError,
    render_certificate_pdf,
)
from app.backend.domain.entities import (
    Discipline,
    DomainValidationError,
    MeasurementMode,
    UploadedFileKind,
)
from app.backend.domain.equipment import (
    EquipmentRange,
    EquipmentStatus,
    ReferenceEquipment,
)
from app.backend.operations.readiness import check_runtime_readiness
from app.backend.persistence.sqlite import (
    PersistenceError,
    SQLiteAuditEventRepository,
    SQLiteUserAccountRepository,
)
from app.backend.services.authentication import (
    AuthenticationFailureError,
    AuthenticationServiceError,
    AuthorizationServiceError,
    resolve_actor_for_action,
    resolve_actor_for_session,
)
from app.backend.services.certificates import (
    AllocatedRenderedCertificateRelease,
    CertificateHistory,
    CertificateMetadataCapture,
    CertificateMetadataServiceError,
    CertificateReferenceEquipmentSelection,
    CertificateReferenceEquipmentServiceError,
    CertificateRelease,
    CertificateReleaseServiceError,
    CertificateRevisionRegistration,
    CertificateRevisionServiceError,
    CertificatePreviewGeneration,
    CertificatePreviewServiceError,
    build_certificate_preview_for_session,
    capture_certificate_metadata_for_session,
    get_certificate_history_for_session,
    get_released_certificate_artifact_for_session,
    release_certificate_for_session,
    render_and_release_certificate_pdf_with_allocated_number_for_session,
    render_and_release_certificate_pdf_for_session,
    revise_released_certificate_for_session,
    select_reference_equipment_for_session,
)
from app.backend.services.certificate_numbers import (
    CertificateNumberAllocationResult,
    CertificateNumberSequenceResult,
    CertificateNumberSequenceRetirementResult,
    CertificateNumberServiceError,
    allocate_certificate_number_for_session,
    create_certificate_number_sequence_for_session,
    retire_certificate_number_sequence_for_session,
)
from app.backend.services.data_entry import (
    DataEntryServiceError,
    TemperatureDataEntryPreparation,
    prepare_temperature_data_entry_for_session,
)
from app.backend.services.entra_authentication import (
    EntraAuthenticationServiceError,
    EntraSessionIssuance,
    issue_entra_session,
)
from app.backend.services.jobs import (
    CalibrationJobCreation,
    CalibrationJobServiceError,
    create_calibration_job_for_session,
)
from app.backend.services.measurement_windows import (
    MeasurementWindowSelectionError,
    TemperatureMeasurementWindowSelection,
    TemperatureWindowCompletion,
    complete_temperature_window_selection_for_session,
    select_temperature_window_from_linked_readings_for_session,
)
from app.backend.services.review_workflow import (
    ReviewWorkflowServiceError,
    ReviewWorkflowTransition,
    approve_qa_release_for_session,
    approve_technical_review_for_session,
    submit_technical_review_for_session,
)
from app.backend.services.import_review import (
    ImportReview,
    ImportReviewServiceError,
    build_import_review_for_session,
)
from app.backend.services.pressure_calculations import (
    AutomaticPressurePointInput,
    ManualPressurePointInput,
    PressureCalculationRun,
    PressureCalculationServiceError,
    calculate_pressure_measurement_points,
    calculate_pressure_measurement_points_for_session,
)
from app.backend.services.pressure_automatic_entry import (
    AutomaticPressureEntry,
    PressureAutomaticEntryServiceError,
    record_automatic_pressure_entry_for_session,
)
from app.backend.services.pressure_manual_entry import (
    ManualPressureEntry,
    ManualPressureReadingInput,
    PressureManualEntryServiceError,
    record_manual_pressure_entry_for_session,
)
from app.backend.services.source_file_uploads import (
    MAX_UPLOAD_SIZE_BYTES,
    SourceFileUploadResult,
    SourceFileUploadServiceError,
    upload_source_file_for_session,
)
from app.backend.services.temperature_calculations import (
    TemperatureCalculationRun,
    TemperatureCalculationServiceError,
    calculate_temperature_measurement_points_for_session,
)
from app.backend.services.user_management import (
    UserAccountManagementResult,
    UserManagementServiceError,
    UserSessionManagementResult,
    change_user_roles_for_session,
    create_user_account_for_session,
    deactivate_user_account_for_session,
    revoke_user_session_for_session,
)
from app.backend.services.verification_transcription import (
    ManualIrtdAlignment,
    VerificationTranscriptionServiceError,
    record_manual_irtd_rows_for_session,
)
from app.backend.services.version_management import (
    ConstantSetApproval,
    UncertaintyBudgetApproval,
    VersionManagementServiceError,
    record_approved_constant_set_for_session,
    record_approved_uncertainty_budget_for_session,
)
from app.calculation_engine.pressure.results import (
    AdditionalStandardUncertainty as PressureAdditionalStandardUncertainty,
    PressureCalculationError,
    PressureKind,
    PressurePointCalculation,
    PressurePointUncertaintyInput,
    calculate_automatic_pressure_point,
    calculate_manual_pressure_point,
)
from app.calculation_engine.temperature.results import (
    AdditionalStandardUncertainty,
    TemperatureCalculationError,
    TemperaturePointUncertaintyInput,
    TemperatureTypeAMethod,
)
from app.backend.ui.workflow import browser_workflow_contract, browser_workflow_html


class ApiError(BaseModel):
    detail: str


class ActorResponse(BaseModel):
    user_id: str
    display_name: str
    roles: tuple[str, ...]


class EntraSessionRequest(BaseModel):
    software_version: str


class EntraSessionResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    session_id: str
    user_id: str
    display_name: str
    roles: tuple[str, ...]
    issued_at: str
    expires_at: str
    audit_event_id: int


class UserAccountCreateRequest(BaseModel):
    user_id: str
    display_name: str
    email: str
    roles: tuple[Role, ...]
    signature_label: str | None = None
    software_version: str


class UserRolesChangeRequest(BaseModel):
    roles: tuple[Role, ...]
    reason: str
    software_version: str


class ReasonedUserManagementRequest(BaseModel):
    reason: str
    software_version: str


class UserAccountResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    user_id: str
    display_name: str
    email: str
    roles: tuple[str, ...]
    active: bool
    signature_label: str | None
    created_at: str


class UserAccountManagementResponse(UserAccountResponse):
    audit_event_id: int


class UserAccessReviewResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    reviewed_by: str
    reviewed_at: str
    users: tuple[UserAccountResponse, ...]


class UserSessionRevocationResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    session_id: str
    user_id: str
    issued_at: str
    expires_at: str
    revoked_at: str | None
    audit_event_id: int


class CertificateNumberSequenceRequest(BaseModel):
    prefix: str
    next_value: int
    software_version: str


class CertificateNumberSequenceResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    prefix: str
    next_value: int
    status: str
    created_by: str
    created_at: str
    audit_event_id: int


class CertificateNumberSequenceRetirementRequest(BaseModel):
    reason: str
    software_version: str


class CertificateNumberSequenceRetirementResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    prefix: str
    next_value: int
    previous_status: str
    status: str
    retired_by: str
    retired_at: str
    reason: str
    audit_event_id: int


class CertificateNumberAllocationRequest(BaseModel):
    prefix: str
    padding: int
    software_version: str


class CertificateNumberAllocationResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    prefix: str
    certificate_number: str
    next_value_after: int
    allocated_by: str
    allocated_at: str
    audit_event_id: int


class CalibrationJobRequest(BaseModel):
    job_id: str
    client_name: str
    client_address: str
    discipline: Discipline
    measurement_mode: MeasurementMode
    method: str
    software_version: str


class CalibrationJobResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    job_id: str
    client_name: str
    client_address: str
    discipline: str
    measurement_mode: str
    method: str
    state: str
    created_by: str
    created_at: str
    audit_event_id: int


class SourceFileUploadResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    uploaded_file_id: str
    job_id: str
    original_filename: str
    file_kind: str
    checksum_sha256: str
    storage_uri: str
    parser_version: str | None
    uploaded_by: str
    uploaded_at: str
    size_bytes: int
    upload_audit_event_id: int
    parser_status: str
    parser_audit_event_id: int | None
    reading_count: int
    warning_count: int
    warnings: tuple[str, ...]


class UploadedFileReviewResponse(BaseModel):
    uploaded_file_id: str
    original_filename: str
    file_kind: str
    checksum_sha256: str
    storage_uri: str
    parser_version: str | None
    uploaded_at: str
    uploaded_by: str
    size_bytes: int | None
    parser_status: str
    reading_count: int
    warning_count: int


class ImportReviewResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    job_id: str
    reviewed_by: str
    reviewed_at: str
    files: tuple[UploadedFileReviewResponse, ...]


class TemperatureDataEntryRequest(BaseModel):
    calibration_uploaded_file_id: str
    setpoints: tuple[float, ...]
    unit: str
    software_version: str


class TemperatureDataEntryResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    job_id: str
    state: str
    dut_ids: tuple[str, ...]
    setpoint_ids: tuple[str, ...]
    data_entry_audit_event_id: int
    workflow_audit_event_id: int


class ManualIrtdRowsRequest(BaseModel):
    calibration_uploaded_file_id: str
    verification_uploaded_file_id: str
    rows: tuple[tuple[str, ...], ...]
    unit: str
    software_version: str


class ManualIrtdRowsResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    job_id: str
    calibration_uploaded_file_id: str
    verification_uploaded_file_id: str
    irtd_reading_count: int
    linked_reading_count: int
    warnings: tuple[str, ...]
    manual_irtd_audit_event_id: int
    alignment_audit_event_id: int


class ManualPressureReadingRequest(BaseModel):
    timestamp: datetime
    value: float
    source_label: str
    row_number: int | None = None
    column_label: str | None = None


class ManualPressureEntryRequest(BaseModel):
    uploaded_file_id: str
    dut_id: str
    dut_make: str
    dut_model: str
    dut_serial_number: str
    dut_channel_id: str
    window_id: str
    setpoint: float
    unit: str
    readings: tuple[ManualPressureReadingRequest, ...]
    software_version: str


class ManualPressureEntryResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    job_id: str
    state: str
    dut_id: str
    window_id: str
    reading_count: int
    data_entry_audit_event_id: int
    data_entry_workflow_audit_event_id: int
    manual_reading_audit_event_id: int
    window_audit_event_id: int
    window_workflow_audit_event_id: int


class AutomaticPressureEntryRequest(BaseModel):
    uploaded_file_id: str
    dut_id: str
    dut_make: str
    dut_model: str
    dut_serial_number: str
    dut_channel_id: str
    window_id: str
    setpoint: float
    unit: str
    parser_version: str = "pressure-csv-parser-v1"
    software_version: str


class AutomaticPressureEntryResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    job_id: str
    state: str
    dut_id: str
    window_id: str
    parser_version: str
    reference_values: tuple[float, ...]
    indication_values: tuple[float, ...]
    reference_reading_count: int
    indication_reading_count: int
    warning_count: int
    warnings: tuple[str, ...]
    parser_audit_event_id: int
    job_parser_audit_event_id: int
    data_entry_audit_event_id: int
    data_entry_workflow_audit_event_id: int
    alignment_audit_event_id: int
    window_audit_event_id: int
    window_workflow_audit_event_id: int


class TemperatureWindowSelectionRequest(BaseModel):
    window_id: str
    dut_id: str
    dut_channel_id: str
    setpoint: float
    unit: str
    start_timestamp: datetime
    end_timestamp: datetime
    software_version: str


class TemperatureWindowSelectionResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    job_id: str
    window_id: str
    dut_id: str
    dut_channel_id: str
    setpoint: float
    unit: str
    start_timestamp: datetime
    end_timestamp: datetime
    reading_count: int
    linked_reading_count: int
    selection_audit_event_id: int


class TemperatureWindowCompletionRequest(BaseModel):
    software_version: str


class TemperatureWindowCompletionResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    job_id: str
    state: str
    workflow_audit_event_id: int


class AdditionalStandardUncertaintyRequest(BaseModel):
    name: str
    standard_uncertainty: float
    sensitivity_coefficient: float = 1.0


class TemperatureUncertaintyInputRequest(BaseModel):
    setpoint: float
    unit: str
    cmc_floor: Decimal
    reference_expanded_uncertainty: float
    reference_coverage_factor: float = 2.0
    bath_expanded_uncertainty: float = 0.0
    bath_coverage_factor: float = 2.0
    dut_resolution: float = 0.0
    coverage_factor: float = 2.0
    type_a_method: TemperatureTypeAMethod = (
        TemperatureTypeAMethod.INDEPENDENT_REFERENCE_AND_DUT
    )
    additional_standard_uncertainties: tuple[
        AdditionalStandardUncertaintyRequest,
        ...,
    ] = ()


class TemperatureCalculationRequest(BaseModel):
    uncertainty_inputs: tuple[TemperatureUncertaintyInputRequest, ...]
    software_version: str
    calculation_engine_version: str
    constant_set_version: str
    budget_version: str


class TemperatureCalculationSummaryResponse(BaseModel):
    point_id: str
    dut_id: str
    measurement_window_id: str
    reference: float
    indication: float
    error_of_indication: float
    display_error_of_indication: str
    reported_expanded_uncertainty: str
    unit: str


class TemperatureCalculationResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    job_id: str
    state: str
    summary_ids: tuple[str, ...]
    summaries: tuple[TemperatureCalculationSummaryResponse, ...]
    calculation_audit_event_id: int
    workflow_audit_event_id: int


class PressureAdditionalStandardUncertaintyRequest(BaseModel):
    name: str
    standard_uncertainty: float
    sensitivity_coefficient: float = 1.0


class PressurePointBaseRequest(BaseModel):
    point_id: str
    dut_id: str
    measurement_window_id: str
    setpoint: float
    unit: str
    pressure_kind: PressureKind
    cmc_floor: Decimal
    reference_expanded_uncertainty: float
    reference_coverage_factor: float = 2.0
    dut_resolution: float = 0.0
    barometer_expanded_uncertainty: float = 0.0
    barometer_coverage_factor: float = 2.0
    coverage_factor: float = 2.0
    additional_standard_uncertainties: tuple[
        PressureAdditionalStandardUncertaintyRequest,
        ...,
    ] = ()


class PressureCalculationBaseRequest(PressurePointBaseRequest):
    job_id: str
    software_version: str
    calculation_engine_version: str
    constant_set_version: str
    budget_version: str


class ManualPressureCalculationRequest(PressureCalculationBaseRequest):
    reference_pressure: float
    indication_values: tuple[float, ...]


class AutomaticPressureCalculationRequest(PressureCalculationBaseRequest):
    reference_values: tuple[float, ...]
    indication_values: tuple[float, ...]


class ManualPressureCalculationPointRequest(PressurePointBaseRequest):
    reference_pressure: float
    indication_values: tuple[float, ...]


class AutomaticPressureCalculationPointRequest(PressurePointBaseRequest):
    reference_values: tuple[float, ...]
    indication_values: tuple[float, ...]


class PressureCalculationRunRequest(BaseModel):
    manual_points: tuple[ManualPressureCalculationPointRequest, ...] = ()
    automatic_points: tuple[AutomaticPressureCalculationPointRequest, ...] = ()
    software_version: str
    calculation_engine_version: str
    constant_set_version: str
    budget_version: str


class PressureContributionResponse(BaseModel):
    name: str
    standard_uncertainty: float
    sensitivity_coefficient: float
    effective_standard_uncertainty: float


class PressureCalculationResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    point_id: str
    job_id: str
    dut_id: str
    measurement_window_id: str
    pressure_kind: str
    reference: float
    indication: float
    error_of_indication: float
    display_error_of_indication: str
    reported_expanded_uncertainty: str
    calculated_expanded_uncertainty: str
    cmc_floor_applied: bool
    unit: str
    contributions: tuple[PressureContributionResponse, ...]
    calculated_by: str
    calculated_at: str
    calculation_audit_event_id: int


class ManualPressureCalculationResponse(PressureCalculationResponse):
    pass


class AutomaticPressureCalculationResponse(PressureCalculationResponse):
    pass


class PressureCalculationSummaryResponse(BaseModel):
    point_id: str
    dut_id: str
    measurement_window_id: str
    calculation_type: str
    pressure_kind: str
    reference: float
    indication: float
    error_of_indication: float
    display_error_of_indication: str
    reported_expanded_uncertainty: str
    calculated_expanded_uncertainty: str
    cmc_floor_applied: bool
    unit: str
    contributions: tuple[PressureContributionResponse, ...]


class PressureCalculationRunResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    job_id: str
    state: str
    summary_ids: tuple[str, ...]
    summaries: tuple[PressureCalculationSummaryResponse, ...]
    calculation_audit_event_id: int
    workflow_audit_event_id: int


class ReviewWorkflowRequest(BaseModel):
    software_version: str


class ReviewWorkflowResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    job_id: str
    state: str
    workflow_audit_event_id: int


class ApprovedConstantSetRequest(BaseModel):
    version: str
    discipline: Discipline
    effective_from: datetime
    software_version: str


class ApprovedConstantSetResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    version: str
    discipline: str
    status: str
    effective_from: str
    approved_by: str
    approved_at: str
    audit_event_id: int


class ApprovedUncertaintyBudgetRequest(BaseModel):
    version: str
    budget_type: str
    method: str
    discipline: Discipline
    linked_constant_set_version: str
    software_version: str


class ApprovedUncertaintyBudgetResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    version: str
    budget_type: str
    method: str
    discipline: str
    status: str
    linked_constant_set_version: str
    approved_by: str
    approved_at: str
    audit_event_id: int


class CertificatePreviewRequest(BaseModel):
    job_id: str
    template_version: str
    software_version: str
    accreditation_mark_allowed: bool


class CertificatePreviewPdfRequest(CertificatePreviewRequest):
    certificate_id: str
    certificate_number: str


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


class AllocatedRenderedCertificateReleaseRequest(BaseModel):
    job_id: str
    certificate_id: str
    certificate_number_prefix: str
    certificate_number_padding: int
    artifact_id: str
    template_version: str
    software_version: str
    accreditation_mark_allowed: bool


class CertificateRevisionRequest(BaseModel):
    certificate_id: str
    revision_id: str
    reason: str
    software_version: str


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


class AllocatedCertificateReleaseResponse(CertificateReleaseResponse):
    certificate_number_prefix: str
    certificate_number_next_value_after: int
    certificate_number_audit_event_id: int


class CertificateRevisionResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    revision_id: str
    original_certificate_id: str
    original_certificate_number: str
    reason: str
    revised_by: str
    revised_at: str
    revision_audit_event_id: int
    workflow_audit_event_id: int
    workflow_state: str


class CertificateHistoryRevisionResponse(BaseModel):
    revision_id: str
    reason: str
    revised_by: str
    revised_at: str


class CertificateHistoryEntryResponse(BaseModel):
    certificate_id: str
    certificate_number: str
    status: str
    software_version: str
    calculation_engine_version: str
    constant_set_version: str
    budget_version: str
    template_version: str
    released_by: str
    released_at: str
    artifacts: tuple[ExportArtifactResponse, ...]
    revisions: tuple[CertificateHistoryRevisionResponse, ...]


class CertificateHistoryResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    job_id: str
    entries: tuple[CertificateHistoryEntryResponse, ...]


def create_app(
    *,
    connection: sqlite3.Connection | None = None,
    connection_provider: (
        Callable[[], AbstractContextManager[sqlite3.Connection]] | None
    ) = None,
    clock: Callable[[], datetime] | None = None,
    artifact_directory: Path | None = None,
    id_factory: Callable[[], str] | None = None,
    enabled_disciplines: frozenset[Discipline] | None = None,
    entra_token_verifier: EntraTokenVerifier | None = None,
    entra_session_duration: timedelta = timedelta(hours=8),
    allow_provisional_valprobe_parser: bool = False,
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
    id_factory_fn = id_factory or _uuid_id
    enabled_discipline_set = enabled_disciplines or frozenset({Discipline.TEMPERATURE})

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def browser_app() -> HTMLResponse:
        return HTMLResponse(browser_workflow_html())

    @app.get("/app", response_class=HTMLResponse, include_in_schema=False)
    def browser_app_alias() -> HTMLResponse:
        return HTMLResponse(browser_workflow_html())

    @app.get("/app/workflow")
    def workflow_contract() -> dict:
        return browser_workflow_contract()

    @app.get("/design-assets/simval-logo", include_in_schema=False)
    def simval_logo() -> FileResponse:
        logo_path = _design_asset_path("Logo - SIMVal.png")
        if not logo_path.is_file():
            raise HTTPException(status_code=404, detail="SIMVal logo asset not found.")
        return FileResponse(logo_path, media_type="image/png")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readiness")
    def readiness() -> JSONResponse:
        result = check_runtime_readiness(
            connection_scope=connection_scope,
            artifact_directory=artifact_directory,
        )
        return JSONResponse(
            status_code=200 if result.ready else 503,
            content=result.to_payload(),
        )

    @app.post(
        "/auth/entra/session",
        response_model=EntraSessionResponse,
        responses={
            401: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def create_entra_session(
        request: EntraSessionRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> EntraSessionResponse:
        if entra_token_verifier is None:
            raise HTTPException(
                status_code=409,
                detail="Microsoft Entra ID Free authentication is not configured.",
            )
        try:
            bearer_token = _bearer_token_from_authorization_header(authorization)
            with connection_scope() as scoped_connection:
                result = issue_entra_session(
                    connection=scoped_connection,
                    bearer_token=bearer_token,
                    token_verifier=entra_token_verifier,
                    session_id=id_factory_fn(),
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                    max_session_duration=entra_session_duration,
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (EntraAuthenticationServiceError, PersistenceError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _entra_session_response(result)

    @app.get(
        "/users",
        response_model=UserAccessReviewResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
        },
    )
    def users(
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> UserAccessReviewResponse:
        timestamp = clock_fn()
        try:
            with connection_scope() as scoped_connection:
                actor = resolve_actor_for_action(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    action=Action.MANAGE_USERS_AND_ROLES,
                    timestamp=timestamp,
                )
                users = SQLiteUserAccountRepository(
                    scoped_connection,
                ).list_active()
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        return UserAccessReviewResponse(
            reviewed_by=actor.user_id,
            reviewed_at=timestamp.isoformat(),
            users=tuple(_user_account_response(user) for user in users),
        )

    @app.post(
        "/users",
        response_model=UserAccountManagementResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def create_user(
        request: UserAccountCreateRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> UserAccountManagementResponse:
        timestamp = clock_fn()
        try:
            user = UserAccount(
                id=request.user_id,
                display_name=request.display_name,
                email=request.email,
                roles=request.roles,
                signature_label=request.signature_label,
                created_at=timestamp,
            )
            with connection_scope() as scoped_connection:
                result = create_user_account_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    user=user,
                    software_version=request.software_version,
                    timestamp=timestamp,
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (UserManagementServiceError, UserIdentityError, PersistenceError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _user_account_management_response(result)

    @app.post(
        "/users/{user_id}/roles",
        response_model=UserAccountManagementResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def change_user_roles(
        user_id: str,
        request: UserRolesChangeRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> UserAccountManagementResponse:
        try:
            with connection_scope() as scoped_connection:
                result = change_user_roles_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    target_user_id=user_id,
                    roles=request.roles,
                    reason=request.reason,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (UserManagementServiceError, UserIdentityError, PersistenceError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _user_account_management_response(result)

    @app.post(
        "/users/{user_id}/deactivation",
        response_model=UserAccountManagementResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def deactivate_user(
        user_id: str,
        request: ReasonedUserManagementRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> UserAccountManagementResponse:
        try:
            with connection_scope() as scoped_connection:
                result = deactivate_user_account_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    target_user_id=user_id,
                    reason=request.reason,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (UserManagementServiceError, UserIdentityError, PersistenceError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _user_account_management_response(result)

    @app.post(
        "/user-sessions/{session_id}/revocation",
        response_model=UserSessionRevocationResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def revoke_user_session(
        session_id: str,
        request: ReasonedUserManagementRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> UserSessionRevocationResponse:
        try:
            with connection_scope() as scoped_connection:
                result = revoke_user_session_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    target_session_id=session_id,
                    reason=request.reason,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (UserManagementServiceError, UserIdentityError, PersistenceError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _user_session_revocation_response(result)

    @app.post(
        "/certificate-number-sequences",
        response_model=CertificateNumberSequenceResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def create_certificate_number_sequence(
        request: CertificateNumberSequenceRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> CertificateNumberSequenceResponse:
        try:
            with connection_scope() as scoped_connection:
                result = create_certificate_number_sequence_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    prefix=request.prefix,
                    next_value=request.next_value,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (CertificateNumberServiceError, PersistenceError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _certificate_number_sequence_response(result)

    @app.post(
        "/certificate-number-sequences/{prefix}/retirement",
        response_model=CertificateNumberSequenceRetirementResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def retire_certificate_number_sequence(
        prefix: str,
        request: CertificateNumberSequenceRetirementRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> CertificateNumberSequenceRetirementResponse:
        try:
            with connection_scope() as scoped_connection:
                result = retire_certificate_number_sequence_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    prefix=prefix,
                    reason=request.reason,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (CertificateNumberServiceError, PersistenceError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _certificate_number_sequence_retirement_response(result)

    @app.post(
        "/certificate-number-allocations",
        response_model=CertificateNumberAllocationResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def allocate_certificate_number(
        request: CertificateNumberAllocationRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> CertificateNumberAllocationResponse:
        try:
            with connection_scope() as scoped_connection:
                result = allocate_certificate_number_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    prefix=request.prefix,
                    padding=request.padding,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (CertificateNumberServiceError, PersistenceError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _certificate_number_allocation_response(result)

    @app.post(
        "/constant-sets/approved",
        response_model=ApprovedConstantSetResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def approved_constant_set(
        request: ApprovedConstantSetRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> ApprovedConstantSetResponse:
        try:
            with connection_scope() as scoped_connection:
                result = record_approved_constant_set_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    version=request.version,
                    discipline=request.discipline,
                    effective_from=request.effective_from,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (VersionManagementServiceError, DomainValidationError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _approved_constant_set_response(result)

    @app.post(
        "/uncertainty-budgets/approved",
        response_model=ApprovedUncertaintyBudgetResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def approved_uncertainty_budget(
        request: ApprovedUncertaintyBudgetRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> ApprovedUncertaintyBudgetResponse:
        try:
            with connection_scope() as scoped_connection:
                result = record_approved_uncertainty_budget_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    version=request.version,
                    budget_type=request.budget_type,
                    method=request.method,
                    discipline=request.discipline,
                    linked_constant_set_version=request.linked_constant_set_version,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (VersionManagementServiceError, DomainValidationError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _approved_uncertainty_budget_response(result)

    @app.post(
        "/calibration-jobs",
        response_model=CalibrationJobResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def calibration_job(
        request: CalibrationJobRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> CalibrationJobResponse:
        if request.discipline not in enabled_discipline_set:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Discipline {request.discipline.value!r} is not enabled "
                    "for this deployment."
                ),
            )
        try:
            with connection_scope() as scoped_connection:
                result = create_calibration_job_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=request.job_id,
                    client_name=request.client_name,
                    client_address=request.client_address,
                    discipline=request.discipline,
                    measurement_mode=request.measurement_mode,
                    method=request.method,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (CalibrationJobServiceError, DomainValidationError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _calibration_job_response(result)

    @app.post(
        "/calibration-jobs/{job_id}/files",
        response_model=SourceFileUploadResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    async def calibration_job_file_upload(
        job_id: str,
        request: Request,
        original_filename: str,
        file_kind: UploadedFileKind,
        software_version: str,
        parser_version: str | None = None,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> SourceFileUploadResponse:
        if artifact_directory is None:
            raise HTTPException(
                status_code=409,
                detail="Artifact storage path is not configured.",
            )
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError as exc:
                raise HTTPException(
                    status_code=409,
                    detail="Upload Content-Length header is invalid.",
                ) from exc
            if declared_size > MAX_UPLOAD_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Uploaded file exceeds {MAX_UPLOAD_SIZE_BYTES} byte limit.",
                )
        try:
            content_bytes = await _read_limited_request_body(request)
            with connection_scope() as scoped_connection:
                result = upload_source_file_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=job_id,
                    file_id=f"file-{id_factory_fn()}",
                    original_filename=original_filename,
                    file_kind=file_kind,
                    content_bytes=content_bytes,
                    artifact_directory=artifact_directory,
                    software_version=software_version,
                    timestamp=clock_fn(),
                    parser_version=parser_version,
                    allow_provisional_valprobe_parser=(
                        allow_provisional_valprobe_parser
                    ),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (SourceFileUploadServiceError, DomainValidationError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _source_file_upload_response(result)

    @app.get(
        "/calibration-jobs/{job_id}/imports",
        response_model=ImportReviewResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def calibration_job_import_review(
        job_id: str,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> ImportReviewResponse:
        try:
            with connection_scope() as scoped_connection:
                result = build_import_review_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=job_id,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except ImportReviewServiceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _import_review_response(result)

    @app.post(
        "/calibration-jobs/{job_id}/temperature-data-entry",
        response_model=TemperatureDataEntryResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def temperature_data_entry(
        job_id: str,
        request: TemperatureDataEntryRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> TemperatureDataEntryResponse:
        try:
            with connection_scope() as scoped_connection:
                result = prepare_temperature_data_entry_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=job_id,
                    calibration_uploaded_file_id=request.calibration_uploaded_file_id,
                    setpoints=request.setpoints,
                    unit=request.unit,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except DataEntryServiceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _temperature_data_entry_response(result)

    @app.post(
        "/calibration-jobs/{job_id}/verification-irtd-rows",
        response_model=ManualIrtdRowsResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def manual_irtd_rows(
        job_id: str,
        request: ManualIrtdRowsRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> ManualIrtdRowsResponse:
        try:
            with connection_scope() as scoped_connection:
                result = record_manual_irtd_rows_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=job_id,
                    calibration_uploaded_file_id=request.calibration_uploaded_file_id,
                    verification_uploaded_file_id=request.verification_uploaded_file_id,
                    rows=request.rows,
                    unit=request.unit,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except VerificationTranscriptionServiceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _manual_irtd_rows_response(result)

    @app.post(
        "/calibration-jobs/{job_id}/pressure-manual-entry",
        response_model=ManualPressureEntryResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def manual_pressure_entry(
        job_id: str,
        request: ManualPressureEntryRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> ManualPressureEntryResponse:
        try:
            with connection_scope() as scoped_connection:
                result = record_manual_pressure_entry_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=job_id,
                    uploaded_file_id=request.uploaded_file_id,
                    dut_id=request.dut_id,
                    dut_make=request.dut_make,
                    dut_model=request.dut_model,
                    dut_serial_number=request.dut_serial_number,
                    dut_channel_id=request.dut_channel_id,
                    window_id=request.window_id,
                    setpoint=request.setpoint,
                    unit=request.unit,
                    readings=tuple(
                        ManualPressureReadingInput(
                            timestamp=reading.timestamp,
                            value=reading.value,
                            source_label=reading.source_label,
                            row_number=reading.row_number,
                            column_label=reading.column_label,
                        )
                        for reading in request.readings
                    ),
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except PressureManualEntryServiceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _manual_pressure_entry_response(result)

    @app.post(
        "/calibration-jobs/{job_id}/pressure-automatic-entry",
        response_model=AutomaticPressureEntryResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def automatic_pressure_entry(
        job_id: str,
        request: AutomaticPressureEntryRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> AutomaticPressureEntryResponse:
        if artifact_directory is None:
            raise HTTPException(
                status_code=409,
                detail="Artifact storage path is not configured.",
            )
        try:
            with connection_scope() as scoped_connection:
                result = record_automatic_pressure_entry_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=job_id,
                    uploaded_file_id=request.uploaded_file_id,
                    dut_id=request.dut_id,
                    dut_make=request.dut_make,
                    dut_model=request.dut_model,
                    dut_serial_number=request.dut_serial_number,
                    dut_channel_id=request.dut_channel_id,
                    window_id=request.window_id,
                    setpoint=request.setpoint,
                    unit=request.unit,
                    parser_version=request.parser_version,
                    artifact_directory=artifact_directory,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except PressureAutomaticEntryServiceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _automatic_pressure_entry_response(result)

    @app.post(
        "/calibration-jobs/{job_id}/temperature-windows",
        response_model=TemperatureWindowSelectionResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def temperature_window_selection(
        job_id: str,
        request: TemperatureWindowSelectionRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> TemperatureWindowSelectionResponse:
        try:
            with connection_scope() as scoped_connection:
                result = select_temperature_window_from_linked_readings_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    window_id=request.window_id,
                    job_id=job_id,
                    dut_id=request.dut_id,
                    dut_channel_id=request.dut_channel_id,
                    setpoint=request.setpoint,
                    unit=request.unit,
                    start_timestamp=request.start_timestamp,
                    end_timestamp=request.end_timestamp,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (MeasurementWindowSelectionError, DomainValidationError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _temperature_window_selection_response(result)

    @app.post(
        "/calibration-jobs/{job_id}/temperature-windows/complete",
        response_model=TemperatureWindowCompletionResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def temperature_window_completion(
        job_id: str,
        request: TemperatureWindowCompletionRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> TemperatureWindowCompletionResponse:
        try:
            with connection_scope() as scoped_connection:
                result = complete_temperature_window_selection_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=job_id,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except MeasurementWindowSelectionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _temperature_window_completion_response(result)

    @app.post(
        "/calibration-jobs/{job_id}/temperature-calculations",
        response_model=TemperatureCalculationResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def temperature_calculation(
        job_id: str,
        request: TemperatureCalculationRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> TemperatureCalculationResponse:
        try:
            uncertainty_inputs = tuple(
                _temperature_uncertainty_input(value)
                for value in request.uncertainty_inputs
            )
            with connection_scope() as scoped_connection:
                result = calculate_temperature_measurement_points_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=job_id,
                    uncertainty_inputs=uncertainty_inputs,
                    software_version=request.software_version,
                    calculation_engine_version=request.calculation_engine_version,
                    constant_set_version=request.constant_set_version,
                    budget_version=request.budget_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (TemperatureCalculationServiceError, TemperatureCalculationError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _temperature_calculation_response(job_id=job_id, result=result)

    @app.post(
        "/pressure/manual-calculations",
        response_model=ManualPressureCalculationResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def manual_pressure_calculation(
        request: ManualPressureCalculationRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> ManualPressureCalculationResponse:
        timestamp = clock_fn()
        try:
            with connection_scope() as scoped_connection:
                actor = resolve_actor_for_action(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    action=Action.RUN_CALCULATION,
                    timestamp=timestamp,
                )
                uncertainty_input = _pressure_uncertainty_input(request)
                result = calculate_manual_pressure_point(
                    point_id=request.point_id,
                    job_id=request.job_id,
                    dut_id=request.dut_id,
                    measurement_window_id=request.measurement_window_id,
                    reference_pressure=request.reference_pressure,
                    indication_values=request.indication_values,
                    uncertainty_input=uncertainty_input,
                    calculation_engine_version=request.calculation_engine_version,
                    constant_set_version=request.constant_set_version,
                    budget_version=request.budget_version,
                )
                audit_event_id = SQLiteAuditEventRepository(
                    scoped_connection,
                ).append(
                    _pressure_calculation_audit_event(
                        calculation_type="manual",
                        request=request,
                        result=result,
                        user_id=actor.user_id,
                        timestamp=timestamp,
                    )
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except PressureCalculationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _pressure_calculation_response(
            result=result,
            pressure_kind=request.pressure_kind,
            calculated_by=actor.user_id,
            calculated_at=timestamp,
            audit_event_id=audit_event_id,
        )

    @app.post(
        "/pressure/automatic-calculations",
        response_model=AutomaticPressureCalculationResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def automatic_pressure_calculation(
        request: AutomaticPressureCalculationRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> AutomaticPressureCalculationResponse:
        timestamp = clock_fn()
        try:
            with connection_scope() as scoped_connection:
                actor = resolve_actor_for_action(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    action=Action.RUN_CALCULATION,
                    timestamp=timestamp,
                )
                result = calculate_automatic_pressure_point(
                    point_id=request.point_id,
                    job_id=request.job_id,
                    dut_id=request.dut_id,
                    measurement_window_id=request.measurement_window_id,
                    reference_values=request.reference_values,
                    indication_values=request.indication_values,
                    uncertainty_input=_pressure_uncertainty_input(request),
                    calculation_engine_version=request.calculation_engine_version,
                    constant_set_version=request.constant_set_version,
                    budget_version=request.budget_version,
                )
                audit_event_id = SQLiteAuditEventRepository(
                    scoped_connection,
                ).append(
                    _pressure_calculation_audit_event(
                        calculation_type="automatic",
                        request=request,
                        result=result,
                        user_id=actor.user_id,
                        timestamp=timestamp,
                    )
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except PressureCalculationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return AutomaticPressureCalculationResponse(
            **_pressure_calculation_response(
                result=result,
                pressure_kind=request.pressure_kind,
                calculated_by=actor.user_id,
                calculated_at=timestamp,
                audit_event_id=audit_event_id,
            ).model_dump()
        )

    @app.post(
        "/calibration-jobs/{job_id}/pressure-calculations",
        response_model=PressureCalculationRunResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def pressure_calculation_run(
        job_id: str,
        request: PressureCalculationRunRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> PressureCalculationRunResponse:
        timestamp = clock_fn()
        try:
            with connection_scope() as scoped_connection:
                actor = resolve_actor_for_action(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    action=Action.RUN_CALCULATION,
                    timestamp=timestamp,
                )
                result = calculate_pressure_measurement_points(
                    connection=scoped_connection,
                    job_id=job_id,
                    manual_points=tuple(
                        ManualPressurePointInput(
                            point_id=point.point_id,
                            dut_id=point.dut_id,
                            measurement_window_id=point.measurement_window_id,
                            pressure_kind=point.pressure_kind,
                            reference_pressure=point.reference_pressure,
                            indication_values=point.indication_values,
                            uncertainty_input=_pressure_uncertainty_input(point),
                        )
                        for point in request.manual_points
                    ),
                    automatic_points=tuple(
                        AutomaticPressurePointInput(
                            point_id=point.point_id,
                            dut_id=point.dut_id,
                            measurement_window_id=point.measurement_window_id,
                            pressure_kind=point.pressure_kind,
                            reference_values=point.reference_values,
                            indication_values=point.indication_values,
                            uncertainty_input=_pressure_uncertainty_input(point),
                        )
                        for point in request.automatic_points
                    ),
                    software_version=request.software_version,
                    calculation_engine_version=request.calculation_engine_version,
                    constant_set_version=request.constant_set_version,
                    budget_version=request.budget_version,
                    user_id=actor.user_id,
                    timestamp=timestamp,
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except PressureCalculationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except PressureCalculationServiceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _pressure_calculation_run_response(job_id=job_id, result=result)

    @app.post(
        "/calibration-jobs/{job_id}/technical-review-submissions",
        response_model=ReviewWorkflowResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def technical_review_submission(
        job_id: str,
        request: ReviewWorkflowRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> ReviewWorkflowResponse:
        try:
            with connection_scope() as scoped_connection:
                result = submit_technical_review_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=job_id,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except ReviewWorkflowServiceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _review_workflow_response(result)

    @app.post(
        "/calibration-jobs/{job_id}/technical-review-approvals",
        response_model=ReviewWorkflowResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def technical_review_approval(
        job_id: str,
        request: ReviewWorkflowRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> ReviewWorkflowResponse:
        try:
            with connection_scope() as scoped_connection:
                result = approve_technical_review_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=job_id,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except ReviewWorkflowServiceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _review_workflow_response(result)

    @app.post(
        "/calibration-jobs/{job_id}/qa-release-approvals",
        response_model=ReviewWorkflowResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def qa_release_approval(
        job_id: str,
        request: ReviewWorkflowRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> ReviewWorkflowResponse:
        try:
            with connection_scope() as scoped_connection:
                result = approve_qa_release_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=job_id,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except ReviewWorkflowServiceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _review_workflow_response(result)

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

    @app.get(
        "/certificate-history/{job_id}",
        response_model=CertificateHistoryResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
        },
    )
    def certificate_history(
        job_id: str,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> CertificateHistoryResponse:
        try:
            with connection_scope() as scoped_connection:
                result = get_certificate_history_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    job_id=job_id,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        return _history_response(result)

    @app.get(
        "/certificate-artifacts/{artifact_id}",
        responses={
            200: {
                "content": {
                    "application/pdf": {},
                    (
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ): {},
                }
            },
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def certificate_artifact(
        artifact_id: str,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> FileResponse:
        if artifact_directory is None:
            raise HTTPException(
                status_code=409,
                detail="Artifact storage path is not configured.",
            )
        try:
            with connection_scope() as scoped_connection:
                result = get_released_certificate_artifact_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    artifact_id=artifact_id,
                    artifact_directory=artifact_directory,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (CertificatePreviewServiceError, CertificateArtifactStorageError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return FileResponse(
            path=result.path,
            media_type=_artifact_media_type(result.artifact.artifact_type),
            filename=result.artifact.filename,
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
        "/certificate-preview-pdfs",
        responses={
            200: {"content": {"application/pdf": {}}},
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def certificate_preview_pdf(
        request: CertificatePreviewPdfRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> Response:
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
            rendered = render_certificate_pdf(
                certificate_id=request.certificate_id,
                certificate_number=request.certificate_number,
                preview=result.preview,
            )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (CertificatePreviewServiceError, CertificateRenderingError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return Response(
            content=rendered.content_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{rendered.filename}"',
                "X-SIMVal-Checksum-SHA256": rendered.checksum_sha256,
                "X-SIMVal-Preview-Audit-Event-Id": str(result.audit_event_id),
            },
        )

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
        if artifact_directory is None:
            raise HTTPException(
                status_code=409,
                detail="Artifact storage path is not configured.",
            )
        try:
            expected_storage_uri = f"controlled-local://{request.filename}"
            if request.storage_uri != expected_storage_uri:
                raise CertificateReleaseServiceError(
                    "Manual release artifact storage URI must match verified local artifact."
                )
            verified_stored_artifact_path(
                base_path=artifact_directory,
                filename=request.filename,
                checksum_sha256=request.checksum_sha256,
            )
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
        except (
            CertificateArtifactStorageError,
            CertificateReleaseServiceError,
        ) as exc:
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

    @app.post(
        "/certificate-rendered-releases/allocated",
        response_model=AllocatedCertificateReleaseResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def allocated_certificate_rendered_release(
        request: AllocatedRenderedCertificateReleaseRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> AllocatedCertificateReleaseResponse:
        if artifact_directory is None:
            raise HTTPException(
                status_code=409,
                detail="Artifact storage path is not configured.",
            )
        try:
            with connection_scope() as scoped_connection:
                result = (
                    render_and_release_certificate_pdf_with_allocated_number_for_session(
                        connection=scoped_connection,
                        session_id=x_session_id,
                        job_id=request.job_id,
                        certificate_id=request.certificate_id,
                        certificate_number_prefix=(
                            request.certificate_number_prefix
                        ),
                        certificate_number_padding=(
                            request.certificate_number_padding
                        ),
                        artifact_id=request.artifact_id,
                        artifact_directory=artifact_directory,
                        template_version=request.template_version,
                        software_version=request.software_version,
                        accreditation_mark_allowed=(
                            request.accreditation_mark_allowed
                        ),
                        timestamp=clock_fn(),
                    )
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except (CertificateReleaseServiceError, CertificateArtifactStorageError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _allocated_release_response(result)

    @app.post(
        "/certificate-revisions",
        response_model=CertificateRevisionResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def certificate_revision(
        request: CertificateRevisionRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> CertificateRevisionResponse:
        try:
            with connection_scope() as scoped_connection:
                result = revise_released_certificate_for_session(
                    connection=scoped_connection,
                    session_id=x_session_id,
                    certificate_id=request.certificate_id,
                    revision_id=request.revision_id,
                    reason=request.reason,
                    software_version=request.software_version,
                    timestamp=clock_fn(),
                )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except CertificateRevisionServiceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _revision_response(result)

    return app


def create_app_from_settings(
    settings: ApiSettings,
    *,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    """Create the backend API from runtime settings."""
    entra_token_verifier: EntraTokenVerifier | None = None
    if settings.auth_provider is AuthProvider.ENTRA_ID_FREE:
        if settings.entra_id is None:
            raise ValueError("Entra ID Free settings are required.")
        entra_token_verifier = PyJwtEntraTokenVerifier(settings.entra_id)
    return create_app(
        connection_provider=lambda: sqlite_connection_scope(settings.database_path),
        clock=clock,
        artifact_directory=settings.artifact_storage_path,
        enabled_disciplines=settings.enabled_disciplines,
        entra_token_verifier=entra_token_verifier,
        entra_session_duration=settings.entra_session_duration,
        allow_provisional_valprobe_parser=settings.allow_provisional_valprobe_parser,
    )


def _user_account_response(user: UserAccount) -> UserAccountResponse:
    return UserAccountResponse(
        user_id=user.id,
        display_name=user.display_name,
        email=user.email,
        roles=tuple(role.value for role in user.roles),
        active=user.active,
        signature_label=user.signature_label,
        created_at=user.created_at.isoformat(),
    )


def _user_account_management_response(
    result: UserAccountManagementResult,
) -> UserAccountManagementResponse:
    user = result.user
    return UserAccountManagementResponse(
        user_id=user.id,
        display_name=user.display_name,
        email=user.email,
        roles=tuple(role.value for role in user.roles),
        active=user.active,
        signature_label=user.signature_label,
        created_at=user.created_at.isoformat(),
        audit_event_id=result.audit_event_id,
    )


def _entra_session_response(result: EntraSessionIssuance) -> EntraSessionResponse:
    user = result.user
    session = result.session
    return EntraSessionResponse(
        session_id=session.id,
        user_id=user.id,
        display_name=user.display_name,
        roles=tuple(role.value for role in user.roles),
        issued_at=session.issued_at.isoformat(),
        expires_at=session.expires_at.isoformat(),
        audit_event_id=result.audit_event_id,
    )


def _user_session_revocation_response(
    result: UserSessionManagementResult,
) -> UserSessionRevocationResponse:
    session = result.session
    return UserSessionRevocationResponse(
        session_id=session.id,
        user_id=session.user_id,
        issued_at=session.issued_at.isoformat(),
        expires_at=session.expires_at.isoformat(),
        revoked_at=(
            session.revoked_at.isoformat()
            if session.revoked_at is not None
            else None
        ),
        audit_event_id=result.audit_event_id,
    )


def _certificate_number_sequence_response(
    result: CertificateNumberSequenceResult,
) -> CertificateNumberSequenceResponse:
    return CertificateNumberSequenceResponse(
        prefix=result.prefix,
        next_value=result.next_value,
        status=result.status,
        created_by=result.audit_event.user_id,
        created_at=result.audit_event.timestamp.isoformat(),
        audit_event_id=result.audit_event_id,
    )


def _certificate_number_sequence_retirement_response(
    result: CertificateNumberSequenceRetirementResult,
) -> CertificateNumberSequenceRetirementResponse:
    return CertificateNumberSequenceRetirementResponse(
        prefix=result.prefix,
        next_value=result.next_value,
        previous_status=result.previous_status,
        status=result.status,
        retired_by=result.audit_event.user_id,
        retired_at=result.audit_event.timestamp.isoformat(),
        reason=result.audit_event.reason or "",
        audit_event_id=result.audit_event_id,
    )


def _certificate_number_allocation_response(
    result: CertificateNumberAllocationResult,
) -> CertificateNumberAllocationResponse:
    return CertificateNumberAllocationResponse(
        prefix=result.prefix,
        certificate_number=result.certificate_number,
        next_value_after=result.next_value_after,
        allocated_by=result.audit_event.user_id,
        allocated_at=result.audit_event.timestamp.isoformat(),
        audit_event_id=result.audit_event_id,
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


def _calibration_job_response(
    result: CalibrationJobCreation,
) -> CalibrationJobResponse:
    job = result.job
    return CalibrationJobResponse(
        job_id=job.id,
        client_name=job.client.name,
        client_address=job.client.address,
        discipline=job.discipline.value,
        measurement_mode=job.measurement_mode.value,
        method=job.method,
        state=job.state.value,
        created_by=job.created_by,
        created_at=job.created_at.isoformat(),
        audit_event_id=result.audit_event_id,
    )


def _source_file_upload_response(
    result: SourceFileUploadResult,
) -> SourceFileUploadResponse:
    uploaded_file = result.uploaded_file
    return SourceFileUploadResponse(
        uploaded_file_id=uploaded_file.id,
        job_id=uploaded_file.job_id,
        original_filename=uploaded_file.original_filename,
        file_kind=uploaded_file.file_kind.value,
        checksum_sha256=uploaded_file.checksum_sha256,
        storage_uri=uploaded_file.storage_uri,
        parser_version=uploaded_file.parser_version,
        uploaded_by=result.uploaded_by,
        uploaded_at=uploaded_file.uploaded_at.isoformat(),
        size_bytes=result.size_bytes,
        upload_audit_event_id=result.upload_audit_event_id,
        parser_status=result.parser_status,
        parser_audit_event_id=result.parser_audit_event_id,
        reading_count=result.reading_count,
        warning_count=result.warning_count,
        warnings=result.warnings,
    )


def _import_review_response(result: ImportReview) -> ImportReviewResponse:
    return ImportReviewResponse(
        job_id=result.job_id,
        reviewed_by=result.reviewed_by,
        reviewed_at=result.reviewed_at.isoformat(),
        files=tuple(
            UploadedFileReviewResponse(
                uploaded_file_id=file_review.uploaded_file.id,
                original_filename=file_review.uploaded_file.original_filename,
                file_kind=file_review.uploaded_file.file_kind.value,
                checksum_sha256=file_review.uploaded_file.checksum_sha256,
                storage_uri=file_review.uploaded_file.storage_uri,
                parser_version=file_review.uploaded_file.parser_version,
                uploaded_at=file_review.uploaded_file.uploaded_at.isoformat(),
                uploaded_by=file_review.uploaded_by,
                size_bytes=file_review.size_bytes,
                parser_status=file_review.parser_status,
                reading_count=file_review.reading_count,
                warning_count=file_review.warning_count,
            )
            for file_review in result.files
        ),
    )


def _temperature_data_entry_response(
    result: TemperatureDataEntryPreparation,
) -> TemperatureDataEntryResponse:
    return TemperatureDataEntryResponse(
        job_id=result.job_id,
        state=result.state.value,
        dut_ids=result.dut_ids,
        setpoint_ids=result.setpoint_ids,
        data_entry_audit_event_id=result.data_entry_audit_event_id,
        workflow_audit_event_id=result.workflow_audit_event_id,
    )


def _manual_irtd_rows_response(result: ManualIrtdAlignment) -> ManualIrtdRowsResponse:
    return ManualIrtdRowsResponse(
        job_id=result.job_id,
        calibration_uploaded_file_id=result.calibration_uploaded_file_id,
        verification_uploaded_file_id=result.verification_uploaded_file_id,
        irtd_reading_count=result.irtd_reading_count,
        linked_reading_count=result.linked_reading_count,
        warnings=result.warnings,
        manual_irtd_audit_event_id=result.manual_irtd_audit_event_id,
        alignment_audit_event_id=result.alignment_audit_event_id,
    )


def _manual_pressure_entry_response(
    result: ManualPressureEntry,
) -> ManualPressureEntryResponse:
    return ManualPressureEntryResponse(
        job_id=result.job_id,
        state=result.state.value,
        dut_id=result.dut_id,
        window_id=result.window_id,
        reading_count=result.reading_count,
        data_entry_audit_event_id=result.data_entry_audit_event_id,
        data_entry_workflow_audit_event_id=(
            result.data_entry_workflow_audit_event_id
        ),
        manual_reading_audit_event_id=result.manual_reading_audit_event_id,
        window_audit_event_id=result.window_audit_event_id,
        window_workflow_audit_event_id=result.window_workflow_audit_event_id,
    )


def _automatic_pressure_entry_response(
    result: AutomaticPressureEntry,
) -> AutomaticPressureEntryResponse:
    return AutomaticPressureEntryResponse(
        job_id=result.job_id,
        state=result.state.value,
        dut_id=result.dut_id,
        window_id=result.window_id,
        parser_version=result.parser_version,
        reference_values=result.reference_values,
        indication_values=result.indication_values,
        reference_reading_count=result.reference_reading_count,
        indication_reading_count=result.indication_reading_count,
        warning_count=len(result.warnings),
        warnings=result.warnings,
        parser_audit_event_id=result.parser_audit_event_id,
        job_parser_audit_event_id=result.job_parser_audit_event_id,
        data_entry_audit_event_id=result.data_entry_audit_event_id,
        data_entry_workflow_audit_event_id=(
            result.data_entry_workflow_audit_event_id
        ),
        alignment_audit_event_id=result.alignment_audit_event_id,
        window_audit_event_id=result.window_audit_event_id,
        window_workflow_audit_event_id=result.window_workflow_audit_event_id,
    )


def _temperature_window_selection_response(
    result: TemperatureMeasurementWindowSelection,
) -> TemperatureWindowSelectionResponse:
    window = result.window
    return TemperatureWindowSelectionResponse(
        job_id=window.job_id,
        window_id=window.id,
        dut_id=window.dut_id,
        dut_channel_id=window.channel_id,
        setpoint=window.setpoint,
        unit=window.unit,
        start_timestamp=window.start_timestamp,
        end_timestamp=window.end_timestamp,
        reading_count=window.reading_count,
        linked_reading_count=len(result.linked_readings),
        selection_audit_event_id=result.audit_event_id,
    )


def _temperature_window_completion_response(
    result: TemperatureWindowCompletion,
) -> TemperatureWindowCompletionResponse:
    return TemperatureWindowCompletionResponse(
        job_id=result.job.id,
        state=result.job.state.value,
        workflow_audit_event_id=result.audit_event_id,
    )


def _temperature_uncertainty_input(
    request: TemperatureUncertaintyInputRequest,
) -> TemperaturePointUncertaintyInput:
    return TemperaturePointUncertaintyInput(
        setpoint=request.setpoint,
        unit=request.unit,
        cmc_floor=request.cmc_floor,
        reference_expanded_uncertainty=request.reference_expanded_uncertainty,
        reference_coverage_factor=request.reference_coverage_factor,
        bath_expanded_uncertainty=request.bath_expanded_uncertainty,
        bath_coverage_factor=request.bath_coverage_factor,
        dut_resolution=request.dut_resolution,
        coverage_factor=request.coverage_factor,
        type_a_method=request.type_a_method,
        additional_standard_uncertainties=tuple(
            AdditionalStandardUncertainty(
                name=value.name,
                standard_uncertainty=value.standard_uncertainty,
                sensitivity_coefficient=value.sensitivity_coefficient,
            )
            for value in request.additional_standard_uncertainties
        ),
    )


def _temperature_calculation_response(
    *,
    job_id: str,
    result: TemperatureCalculationRun,
) -> TemperatureCalculationResponse:
    return TemperatureCalculationResponse(
        job_id=job_id,
        state="calculated",
        summary_ids=tuple(summary.point_id for summary in result.summaries),
        summaries=tuple(
            TemperatureCalculationSummaryResponse(
                point_id=summary.point_id,
                dut_id=summary.dut_id,
                measurement_window_id=summary.measurement_window_id,
                reference=summary.reference,
                indication=summary.indication,
                error_of_indication=summary.error_of_indication,
                display_error_of_indication=str(summary.display_error_of_indication),
                reported_expanded_uncertainty=str(
                    summary.reported_expanded_uncertainty
                ),
                unit=summary.unit,
            )
            for summary in result.summaries
        ),
        calculation_audit_event_id=result.calculation_audit_event_id,
        workflow_audit_event_id=result.workflow_audit_event_id,
    )


def _pressure_uncertainty_input(
    request: PressurePointBaseRequest,
) -> PressurePointUncertaintyInput:
    return PressurePointUncertaintyInput(
        setpoint=request.setpoint,
        unit=request.unit,
        pressure_kind=request.pressure_kind,
        cmc_floor=request.cmc_floor,
        reference_expanded_uncertainty=request.reference_expanded_uncertainty,
        reference_coverage_factor=request.reference_coverage_factor,
        dut_resolution=request.dut_resolution,
        barometer_expanded_uncertainty=request.barometer_expanded_uncertainty,
        barometer_coverage_factor=request.barometer_coverage_factor,
        coverage_factor=request.coverage_factor,
        additional_standard_uncertainties=tuple(
            PressureAdditionalStandardUncertainty(
                name=value.name,
                standard_uncertainty=value.standard_uncertainty,
                sensitivity_coefficient=value.sensitivity_coefficient,
            )
            for value in request.additional_standard_uncertainties
        ),
    )


def _pressure_calculation_response(
    *,
    result: PressurePointCalculation,
    pressure_kind: PressureKind,
    calculated_by: str,
    calculated_at: datetime,
    audit_event_id: int,
) -> ManualPressureCalculationResponse:
    summary = result.summary
    return ManualPressureCalculationResponse(
        point_id=summary.point_id,
        job_id=summary.job_id,
        dut_id=summary.dut_id,
        measurement_window_id=summary.measurement_window_id,
        pressure_kind=pressure_kind.value,
        reference=summary.reference,
        indication=summary.indication,
        error_of_indication=summary.error_of_indication,
        display_error_of_indication=str(summary.display_error_of_indication),
        reported_expanded_uncertainty=str(summary.reported_expanded_uncertainty),
        calculated_expanded_uncertainty=str(result.calculated_expanded_uncertainty),
        cmc_floor_applied=summary.cmc_floor_applied,
        unit=summary.unit,
        contributions=tuple(
            PressureContributionResponse(
                name=contribution.name,
                standard_uncertainty=contribution.standard_uncertainty,
                sensitivity_coefficient=contribution.sensitivity_coefficient,
                effective_standard_uncertainty=(
                    contribution.effective_standard_uncertainty
                ),
            )
            for contribution in result.contributions
        ),
        calculated_by=calculated_by,
        calculated_at=calculated_at.isoformat(),
        calculation_audit_event_id=audit_event_id,
    )


def _pressure_calculation_run_response(
    *,
    job_id: str,
    result: PressureCalculationRun,
) -> PressureCalculationRunResponse:
    return PressureCalculationRunResponse(
        job_id=job_id,
        state="calculated",
        summary_ids=tuple(
            point.calculation.summary.point_id for point in result.points
        ),
        summaries=tuple(
            _pressure_calculation_summary_response(point)
            for point in result.points
        ),
        calculation_audit_event_id=result.calculation_audit_event_id,
        workflow_audit_event_id=result.workflow_audit_event_id,
    )


def _pressure_calculation_summary_response(
    point,
) -> PressureCalculationSummaryResponse:
    summary = point.calculation.summary
    return PressureCalculationSummaryResponse(
        point_id=summary.point_id,
        dut_id=summary.dut_id,
        measurement_window_id=summary.measurement_window_id,
        calculation_type=point.calculation_type,
        pressure_kind=point.pressure_kind.value,
        reference=summary.reference,
        indication=summary.indication,
        error_of_indication=summary.error_of_indication,
        display_error_of_indication=str(summary.display_error_of_indication),
        reported_expanded_uncertainty=str(summary.reported_expanded_uncertainty),
        calculated_expanded_uncertainty=str(
            point.calculation.calculated_expanded_uncertainty
        ),
        cmc_floor_applied=summary.cmc_floor_applied,
        unit=summary.unit,
        contributions=tuple(
            PressureContributionResponse(
                name=contribution.name,
                standard_uncertainty=contribution.standard_uncertainty,
                sensitivity_coefficient=contribution.sensitivity_coefficient,
                effective_standard_uncertainty=(
                    contribution.effective_standard_uncertainty
                ),
            )
            for contribution in point.calculation.contributions
        ),
    )


def _pressure_calculation_audit_event(
    *,
    calculation_type: str,
    request: PressureCalculationBaseRequest,
    result: PressurePointCalculation,
    user_id: str,
    timestamp: datetime,
) -> AuditEvent:
    summary = result.summary
    return AuditEvent(
        entity_type="pressure_calculation",
        entity_id=request.point_id,
        action=AuditAction.CALCULATION_RUN,
        user_id=user_id,
        timestamp=timestamp,
        new_value={
            "calculation_type": calculation_type,
            "job_id": request.job_id,
            "dut_id": request.dut_id,
            "measurement_window_id": request.measurement_window_id,
            "pressure_kind": request.pressure_kind.value,
            "reference": summary.reference,
            "indication": summary.indication,
            "error_of_indication": summary.error_of_indication,
            "reported_expanded_uncertainty": str(
                summary.reported_expanded_uncertainty
            ),
            "calculated_expanded_uncertainty": str(
                result.calculated_expanded_uncertainty
            ),
            "cmc_floor_applied": summary.cmc_floor_applied,
            "unit": summary.unit,
            "contributions": tuple(
                {
                    "name": contribution.name,
                    "standard_uncertainty": contribution.standard_uncertainty,
                    "sensitivity_coefficient": (
                        contribution.sensitivity_coefficient
                    ),
                    "effective_standard_uncertainty": (
                        contribution.effective_standard_uncertainty
                    ),
                }
                for contribution in result.contributions
            ),
        },
        software_version=request.software_version,
        calculation_engine_version=request.calculation_engine_version,
        constant_set_version=request.constant_set_version,
        budget_version=request.budget_version,
    )


def _review_workflow_response(
    result: ReviewWorkflowTransition,
) -> ReviewWorkflowResponse:
    return ReviewWorkflowResponse(
        job_id=result.job.id,
        state=result.job.state.value,
        workflow_audit_event_id=result.audit_event_id,
    )


def _approved_constant_set_response(
    result: ConstantSetApproval,
) -> ApprovedConstantSetResponse:
    constant_set = result.constant_set
    assert constant_set.approved_by is not None
    assert constant_set.approved_at is not None
    return ApprovedConstantSetResponse(
        version=constant_set.version,
        discipline=constant_set.discipline.value,
        status=constant_set.status.value,
        effective_from=constant_set.effective_from.isoformat(),
        approved_by=constant_set.approved_by,
        approved_at=constant_set.approved_at.isoformat(),
        audit_event_id=result.audit_event_id,
    )


def _approved_uncertainty_budget_response(
    result: UncertaintyBudgetApproval,
) -> ApprovedUncertaintyBudgetResponse:
    budget = result.budget
    assert budget.approved_by is not None
    assert budget.approved_at is not None
    return ApprovedUncertaintyBudgetResponse(
        version=budget.version,
        budget_type=budget.budget_type,
        method=budget.method,
        discipline=budget.discipline.value,
        status=budget.status.value,
        linked_constant_set_version=budget.linked_constant_set_version,
        approved_by=budget.approved_by,
        approved_at=budget.approved_at.isoformat(),
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


def _allocated_release_response(
    result: AllocatedRenderedCertificateRelease,
) -> AllocatedCertificateReleaseResponse:
    base = _release_response(result.release)
    allocation = result.certificate_number_allocation
    return AllocatedCertificateReleaseResponse(
        **base.model_dump(),
        certificate_number_prefix=allocation.prefix,
        certificate_number_next_value_after=allocation.next_value_after,
        certificate_number_audit_event_id=allocation.audit_event_id,
    )


def _revision_response(
    result: CertificateRevisionRegistration,
) -> CertificateRevisionResponse:
    revision = result.revision
    workflow_state = ""
    if result.workflow_audit_event.new_value is not None:
        workflow_state = str(result.workflow_audit_event.new_value["state"])
    return CertificateRevisionResponse(
        revision_id=revision.revision_id,
        original_certificate_id=revision.original_certificate_id,
        original_certificate_number=revision.original_certificate_number,
        reason=revision.reason,
        revised_by=revision.revised_by,
        revised_at=revision.revised_at.isoformat(),
        revision_audit_event_id=result.revision_audit_event_id,
        workflow_audit_event_id=result.workflow_audit_event_id,
        workflow_state=workflow_state,
    )


def _history_response(result: CertificateHistory) -> CertificateHistoryResponse:
    return CertificateHistoryResponse(
        job_id=result.job_id,
        entries=tuple(
            CertificateHistoryEntryResponse(
                certificate_id=entry.certificate.certificate_id,
                certificate_number=entry.certificate.certificate_number,
                status=entry.certificate.status.value,
                software_version=entry.certificate.software_version,
                calculation_engine_version=(
                    entry.certificate.calculation_engine_version
                ),
                constant_set_version=entry.certificate.constant_set_version,
                budget_version=entry.certificate.budget_version,
                template_version=entry.certificate.template_version,
                released_by=entry.certificate.released_by or "",
                released_at=(
                    entry.certificate.released_at.isoformat()
                    if entry.certificate.released_at is not None
                    else ""
                ),
                artifacts=tuple(
                    _artifact_response(artifact)
                    for artifact in entry.certificate.export_artifacts
                ),
                revisions=tuple(
                    CertificateHistoryRevisionResponse(
                        revision_id=revision.revision_id,
                        reason=revision.reason,
                        revised_by=revision.revised_by,
                        revised_at=revision.revised_at.isoformat(),
                    )
                    for revision in entry.revisions
                ),
            )
            for entry in result.entries
        ),
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


def _artifact_media_type(artifact_type: ArtifactType) -> str:
    if artifact_type is ArtifactType.PDF:
        return "application/pdf"
    if artifact_type is ArtifactType.XLSX:
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return "application/octet-stream"


async def _read_limited_request_body(request: Request) -> bytes:
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_UPLOAD_SIZE_BYTES:
            raise SourceFileUploadServiceError(
                f"Uploaded file exceeds {MAX_UPLOAD_SIZE_BYTES} byte limit."
            )
    return bytes(content)


def _decimal_to_text(value: Decimal) -> str:
    return format(value, "f")


def _bearer_token_from_authorization_header(authorization: str | None) -> str:
    if authorization is None or authorization.strip() == "":
        raise AuthenticationFailureError("Authorization bearer token is required.")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise AuthenticationFailureError("Authorization header must use Bearer scheme.")
    token = authorization[len(prefix) :].strip()
    if token == "":
        raise AuthenticationFailureError("Authorization bearer token is required.")
    return token


@contextmanager
def _fixed_connection_scope(
    connection: sqlite3.Connection | None,
) -> sqlite3.Connection:
    if connection is None:
        raise ValueError("A fixed connection is required.")
    yield connection


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid_id() -> str:
    return uuid.uuid4().hex


def _design_asset_path(filename: str) -> Path:
    return Path(__file__).resolve().parents[3] / "Docs" / "Design Document" / filename
