from datetime import datetime, timezone

import pytest

from app.backend.domain.entities import (
    CalibrationJob,
    Client,
    DeviceUnderTest,
    Discipline,
    DomainValidationError,
    MeasurementMode,
    MeasurementReading,
    MeasurementWindow,
    SourceLocation,
    UploadedFile,
    UploadedFileKind,
)
from app.backend.domain.workflow import WorkflowState


def test_calibration_job_requires_controlled_metadata():
    client = Client(name="SIMVal customer", address="Validated Road 1")

    job = CalibrationJob(
        id="job-001",
        client=client,
        discipline=Discipline.TEMPERATURE,
        measurement_mode=MeasurementMode.AUTOMATIC,
        method="ValProbe RT linked XLSX/PDF workflow",
        created_by="user-001",
    )

    assert job.state is WorkflowState.DRAFT
    assert job.created_at.tzinfo is not None


def test_calibration_job_rejects_missing_client_name():
    with pytest.raises(DomainValidationError):
        Client(name=" ", address="Validated Road 1")


def test_uploaded_file_records_raw_file_integrity_evidence():
    uploaded_file = UploadedFile(
        id="file-001",
        job_id="job-001",
        original_filename="Calibration_input_file_Valprobe RT Loggers.xlsx",
        checksum_sha256="a" * 64,
        file_kind=UploadedFileKind.CALIBRATION_XLSX,
        storage_uri="controlled-local://Calibration_input_file_Valprobe RT Loggers.xlsx",
        parser_version="valprobe-xlsx-contract-v1",
    )

    assert uploaded_file.checksum_sha256 == "a" * 64
    assert uploaded_file.uploaded_at.tzinfo is not None


def test_uploaded_file_rejects_invalid_checksum():
    with pytest.raises(DomainValidationError):
        UploadedFile(
            id="file-001",
            job_id="job-001",
            original_filename="input.xlsx",
            checksum_sha256="not-a-sha256",
            file_kind=UploadedFileKind.CALIBRATION_XLSX,
            storage_uri="controlled-local://input.xlsx",
        )


def test_uploaded_file_normalizes_checksum_to_lowercase():
    uploaded_file = UploadedFile(
        id="file-001",
        job_id="job-001",
        original_filename="input.xlsx",
        checksum_sha256="A" * 64,
        file_kind=UploadedFileKind.CALIBRATION_XLSX,
        storage_uri="controlled-local://input.xlsx",
    )

    assert uploaded_file.checksum_sha256 == "a" * 64


def test_device_under_test_identity_includes_logger_channel():
    dut = DeviceUnderTest(
        id="dut-001",
        job_id="job-001",
        make="Kaye",
        model="ValProbe RT",
        serial_number="MJT1",
        channel_id="MJT1-A",
    )

    assert dut.identity_key == ("job-001", "MJT1", "MJT1-A")


def test_source_location_rejects_invalid_row_number():
    with pytest.raises(DomainValidationError):
        SourceLocation(
            uploaded_file_id="file-001",
            source_label="Temperature",
            row_number=0,
            column_label="B",
        )


def test_imported_reading_requires_source_traceability():
    source = SourceLocation(
        uploaded_file_id="file-001",
        source_label="Temperature",
        row_number=12,
        column_label="B",
    )

    reading = MeasurementReading(
        timestamp=datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc),
        channel_id="MJT1-A",
        value=-80.036,
        unit="deg C",
        source=source,
    )

    assert reading.source.row_number == 12
    assert reading.source.column_label == "B"


def test_imported_reading_rejects_naive_timestamp():
    with pytest.raises(DomainValidationError):
        MeasurementReading(
            timestamp=datetime(2026, 4, 8, 15, 45),
            channel_id="MJT1-A",
            value=-80.036,
            unit="deg C",
            source=SourceLocation(
                uploaded_file_id="file-001",
                source_label="Temperature",
                row_number=12,
                column_label="B",
            ),
        )


def test_imported_reading_rejects_nonfinite_value():
    with pytest.raises(DomainValidationError):
        MeasurementReading(
            timestamp=datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc),
            channel_id="MJT1-A",
            value=float("inf"),
            unit="deg C",
            source=SourceLocation(
                uploaded_file_id="file-001",
                source_label="Temperature",
                row_number=12,
                column_label="B",
            ),
        )


def test_measurement_window_keeps_single_channel_and_unit():
    first = MeasurementReading(
        timestamp=datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc),
        channel_id="MJT1-A",
        value=-80.036,
        unit="deg C",
        source=SourceLocation(
            uploaded_file_id="file-001",
            source_label="Temperature",
            row_number=12,
            column_label="B",
        ),
    )
    second = MeasurementReading(
        timestamp=datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc),
        channel_id="MJT1-A",
        value=-80.034,
        unit="deg C",
        source=SourceLocation(
            uploaded_file_id="file-001",
            source_label="Temperature",
            row_number=13,
            column_label="B",
        ),
    )

    window = MeasurementWindow(
        id="window-001",
        job_id="job-001",
        dut_id="dut-001",
        setpoint=-80.0,
        unit="deg C",
        selected_by="user-001",
        readings=(first, second),
    )

    assert window.channel_id == "MJT1-A"
    assert window.reading_count == 2
    assert window.start_timestamp == first.timestamp
    assert window.end_timestamp == second.timestamp


def test_measurement_window_rejects_mixed_channels():
    first = MeasurementReading(
        timestamp=datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc),
        channel_id="MJT1-A",
        value=-80.036,
        unit="deg C",
        source=SourceLocation(
            uploaded_file_id="file-001",
            source_label="Temperature",
            row_number=12,
            column_label="B",
        ),
    )
    second = MeasurementReading(
        timestamp=datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc),
        channel_id="NWU2-A",
        value=-80.034,
        unit="deg C",
        source=SourceLocation(
            uploaded_file_id="file-001",
            source_label="Temperature",
            row_number=13,
            column_label="C",
        ),
    )

    with pytest.raises(DomainValidationError):
        MeasurementWindow(
            id="window-001",
            job_id="job-001",
            dut_id="dut-001",
            setpoint=-80.0,
            unit="deg C",
            selected_by="user-001",
            readings=(first, second),
        )


def test_measurement_window_rejects_mixed_units():
    first = MeasurementReading(
        timestamp=datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc),
        channel_id="MJT1-A",
        value=-80.036,
        unit="deg C",
        source=SourceLocation(
            uploaded_file_id="file-001",
            source_label="Temperature",
            row_number=12,
            column_label="B",
        ),
    )
    second = MeasurementReading(
        timestamp=datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc),
        channel_id="MJT1-A",
        value=-80.034,
        unit="K",
        source=SourceLocation(
            uploaded_file_id="file-001",
            source_label="Temperature",
            row_number=13,
            column_label="B",
        ),
    )

    with pytest.raises(DomainValidationError):
        MeasurementWindow(
            id="window-001",
            job_id="job-001",
            dut_id="dut-001",
            setpoint=-80.0,
            unit="deg C",
            selected_by="user-001",
            readings=(first, second),
        )


def test_measurement_window_rejects_empty_reading_selection():
    with pytest.raises(DomainValidationError):
        MeasurementWindow(
            id="window-001",
            job_id="job-001",
            dut_id="dut-001",
            setpoint=-80.0,
            unit="deg C",
            selected_by="user-001",
            readings=(),
        )


def test_measurement_window_rejects_non_chronological_readings():
    first = MeasurementReading(
        timestamp=datetime(2026, 4, 8, 15, 46, tzinfo=timezone.utc),
        channel_id="MJT1-A",
        value=-80.034,
        unit="deg C",
        source=SourceLocation(
            uploaded_file_id="file-001",
            source_label="Temperature",
            row_number=13,
            column_label="B",
        ),
    )
    second = MeasurementReading(
        timestamp=datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc),
        channel_id="MJT1-A",
        value=-80.036,
        unit="deg C",
        source=SourceLocation(
            uploaded_file_id="file-001",
            source_label="Temperature",
            row_number=12,
            column_label="B",
        ),
    )

    with pytest.raises(DomainValidationError):
        MeasurementWindow(
            id="window-001",
            job_id="job-001",
            dut_id="dut-001",
            setpoint=-80.0,
            unit="deg C",
            selected_by="user-001",
            readings=(first, second),
        )
