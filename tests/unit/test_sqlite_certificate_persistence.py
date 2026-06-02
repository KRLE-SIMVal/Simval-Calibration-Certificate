import sqlite3
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.backend.certificates.records import (
    ArtifactType,
    CertificateRecord,
    CertificateRevision,
    CertificateStatus,
    ExportArtifact,
)
from app.backend.domain.entities import (
    CalibrationJob,
    Client,
    DeviceUnderTest,
    Discipline,
    MeasurementMode,
    MeasurementReading,
    MeasurementWindow,
    SourceLocation,
    UploadedFile,
    UploadedFileKind,
)
from app.backend.domain.workflow import WorkflowState
from app.backend.persistence.sqlite import (
    PersistenceError,
    SQLiteCalibrationJobRepository,
    SQLiteCertificateRecordRepository,
    SQLiteCertificateRevisionRepository,
    SQLiteDeviceUnderTestRepository,
    SQLiteMeasurementPointSummaryRepository,
    SQLiteMeasurementWindowRepository,
    SQLiteUploadedFileRepository,
    initialize_schema,
)
from app.calculation_engine.common.summary import MeasurementPointSummary


def _connection_with_window() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    SQLiteCalibrationJobRepository(connection).add(_job())
    SQLiteUploadedFileRepository(connection).add(_uploaded_file())
    SQLiteDeviceUnderTestRepository(connection).add(_dut())
    SQLiteMeasurementWindowRepository(connection).add(_window())
    return connection


def _connection_with_summary() -> sqlite3.Connection:
    connection = _connection_with_window()
    SQLiteMeasurementPointSummaryRepository(connection).add(_summary())
    return connection


def _job() -> CalibrationJob:
    return CalibrationJob(
        id="job-001",
        client=Client(name="SIMVal customer", address="Validated Road 1"),
        discipline=Discipline.TEMPERATURE,
        measurement_mode=MeasurementMode.AUTOMATIC,
        method="ValProbe RT linked XLSX/PDF workflow",
        created_by="operator-001",
        state=WorkflowState.DRAFT,
        created_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
    )


def _uploaded_file() -> UploadedFile:
    return UploadedFile(
        id="file-001",
        job_id="job-001",
        original_filename="Calibration_input_file_Valprobe RT Loggers.xlsx",
        checksum_sha256="a" * 64,
        file_kind=UploadedFileKind.CALIBRATION_XLSX,
        storage_uri="controlled-local://Calibration_input_file_Valprobe RT Loggers.xlsx",
        parser_version="valprobe-xlsx-contract-v1",
        uploaded_at=datetime(2026, 6, 1, 14, 5, tzinfo=timezone.utc),
    )


def _dut() -> DeviceUnderTest:
    return DeviceUnderTest(
        id="dut-001",
        job_id="job-001",
        make="Kaye",
        model="ValProbe RT",
        serial_number="MJT1",
        channel_id="MJT1-A",
    )


def _window() -> MeasurementWindow:
    return MeasurementWindow(
        id="window-001",
        job_id="job-001",
        dut_id="dut-001",
        setpoint=-90.0,
        unit="deg C",
        selected_by="operator-001",
        selected_at=datetime(2026, 6, 1, 14, 10, tzinfo=timezone.utc),
        readings=(
            MeasurementReading(
                timestamp=datetime(2026, 4, 8, 15, 45, tzinfo=timezone.utc),
                channel_id="MJT1-A",
                value=-90.130,
                unit="deg C",
                source=SourceLocation(
                    uploaded_file_id="file-001",
                    source_label="Temperature",
                    row_number=12,
                    column_label="B",
                ),
            ),
        ),
    )


def _summary() -> MeasurementPointSummary:
    return MeasurementPointSummary(
        point_id="point-001",
        job_id="job-001",
        dut_id="dut-001",
        measurement_window_id="window-001",
        reference=-90.032,
        indication=-90.130,
        unit="deg C",
        error_of_indication=-0.098,
        calculated_expanded_uncertainty=Decimal("0.0104"),
        cmc_floor=Decimal("0.011"),
        reported_expanded_uncertainty=Decimal("0.011"),
        display_error_of_indication=Decimal("-0.098"),
        calculation_engine_version="calc-engine-0.1.0",
        constant_set_version="constants-2026-001",
        budget_version="budget-temp-001",
    )


def _artifact() -> ExportArtifact:
    return ExportArtifact(
        artifact_id="artifact-001",
        certificate_id="cert-001",
        artifact_type=ArtifactType.PDF,
        filename="SIMVAL-CAL-0001.pdf",
        checksum_sha256="b" * 64,
        storage_uri="controlled-local://SIMVAL-CAL-0001.pdf",
        generated_by="qa-001",
        generated_at=datetime(2026, 6, 1, 15, 30, tzinfo=timezone.utc),
    )


def _certificate() -> CertificateRecord:
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


def test_sqlite_calculation_summary_repository_round_trips_versioned_summary():
    connection = _connection_with_window()
    repository = SQLiteMeasurementPointSummaryRepository(connection)
    summary = _summary()

    repository.add(summary)

    loaded = repository.get("point-001")
    assert loaded == summary
    assert loaded.reported_expanded_uncertainty == Decimal("0.011")
    assert loaded.constant_set_version == "constants-2026-001"


def test_sqlite_calculation_summary_repository_rejects_unknown_window():
    connection = sqlite3.connect(":memory:")
    initialize_schema(connection)
    repository = SQLiteMeasurementPointSummaryRepository(connection)

    with pytest.raises(PersistenceError):
        repository.add(_summary())


def test_sqlite_certificate_repository_round_trips_released_record():
    connection = _connection_with_summary()
    repository = SQLiteCertificateRecordRepository(connection)
    certificate = _certificate()

    repository.add(certificate)

    loaded = repository.get("cert-001")
    assert loaded == certificate
    assert loaded.primary_artifact.checksum_sha256 == "b" * 64
    assert loaded.calculation_summary_ids == ("point-001",)


def test_sqlite_certificate_repository_rejects_duplicate_certificate_number():
    connection = _connection_with_summary()
    repository = SQLiteCertificateRecordRepository(connection)
    repository.add(_certificate())

    with pytest.raises(PersistenceError):
        repository.add(
            replace(
                _certificate(),
                certificate_id="cert-002",
                export_artifacts=(
                    replace(
                        _artifact(),
                        artifact_id="artifact-002",
                        certificate_id="cert-002",
                    ),
                ),
            )
        )


def test_sqlite_released_certificate_rows_are_immutable_at_database_level():
    connection = _connection_with_summary()
    repository = SQLiteCertificateRecordRepository(connection)
    repository.add(_certificate())

    with pytest.raises(sqlite3.DatabaseError):
        connection.execute(
            "UPDATE certificates SET certificate_number = ? WHERE certificate_id = ?",
            ("SIMVAL-CAL-9999", "cert-001"),
        )
    connection.rollback()

    with pytest.raises(sqlite3.DatabaseError):
        connection.execute("DELETE FROM certificates WHERE certificate_id = ?", ("cert-001",))
    connection.rollback()

    assert repository.get("cert-001") == _certificate()


def test_sqlite_certificate_repository_rejects_unknown_summary_reference():
    connection = _connection_with_window()
    repository = SQLiteCertificateRecordRepository(connection)

    with pytest.raises(PersistenceError):
        repository.add(_certificate())


def test_sqlite_certificate_revision_repository_round_trips_revision_evidence():
    connection = _connection_with_summary()
    SQLiteCertificateRecordRepository(connection).add(_certificate())
    repository = SQLiteCertificateRevisionRepository(connection)
    revision = CertificateRevision(
        revision_id="rev-001",
        original_certificate_id="cert-001",
        original_certificate_number="SIMVAL-CAL-0001",
        reason="Corrected customer address after QA approval.",
        revised_by="qa-002",
        revised_at=datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc),
    )

    repository.add(revision)

    assert repository.get("rev-001") == revision
    assert repository.list_for_original("cert-001") == (revision,)
