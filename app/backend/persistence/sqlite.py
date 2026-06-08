"""SQLite persistence for auditable backend foundation records."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json
import sqlite3
from typing import Any, Mapping

from app.backend.auth.permissions import Role
from app.backend.auth.users import UserAccount, UserSession
from app.backend.certificates.records import (
    ArtifactType,
    CertificateRecord,
    CertificateRevision,
    CertificateStatus,
    ExportArtifact,
)
from app.backend.certificates.metadata import CertificateMetadata
from app.backend.audit.events import AuditAction, AuditEvent
from app.backend.domain.entities import (
    CalibrationJob,
    Client,
    DeviceUnderTest,
    Discipline,
    LinkedTemperatureReading,
    MeasurementReading,
    MeasurementWindow,
    MeasurementMode,
    RequiredTemperatureSetpoint,
    SourceLocation,
    UploadedFile,
    UploadedFileKind,
)
from app.backend.domain.equipment import (
    EquipmentRange,
    EquipmentStatus,
    ReferenceEquipment,
    SelectedReferenceEquipment,
)
from app.backend.domain.versioning import ConstantSet, UncertaintyBudget, VersionStatus
from app.backend.domain.workflow import WorkflowState
from app.calculation_engine.common.summary import MeasurementPointSummary


SCHEMA_VERSION = "p13-sqlite-schema-v1"


class PersistenceError(RuntimeError):
    """Raised when persisted records cannot be stored or loaded safely."""


class RecordNotFoundError(PersistenceError):
    """Raised when a requested persisted record does not exist."""


class ConcurrencyError(PersistenceError):
    """Raised when the persisted state differs from the expected state."""


def initialize_schema(connection: sqlite3.Connection) -> None:
    """Create the initial controlled SQLite schema."""
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_accounts (
            id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            roles_json TEXT NOT NULL,
            active INTEGER NOT NULL CHECK (active IN (0, 1)),
            signature_label TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS ix_user_accounts_active
            ON user_accounts(active, id);

        CREATE TABLE IF NOT EXISTS user_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES user_accounts(id),
            issued_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT
        );

        CREATE INDEX IF NOT EXISTS ix_user_sessions_user
            ON user_sessions(user_id, expires_at);

        CREATE TABLE IF NOT EXISTS calibration_jobs (
            id TEXT PRIMARY KEY,
            client_name TEXT NOT NULL,
            client_address TEXT NOT NULL,
            discipline TEXT NOT NULL,
            measurement_mode TEXT NOT NULL,
            method TEXT NOT NULL,
            created_by TEXT NOT NULL,
            state TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS uploaded_files (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES calibration_jobs(id),
            original_filename TEXT NOT NULL,
            checksum_sha256 TEXT NOT NULL,
            file_kind TEXT NOT NULL,
            storage_uri TEXT NOT NULL,
            parser_version TEXT,
            uploaded_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS ix_uploaded_files_job
            ON uploaded_files(job_id, id);

        CREATE TABLE IF NOT EXISTS parsed_readings (
            uploaded_file_id TEXT NOT NULL REFERENCES uploaded_files(id),
            sequence_index INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT NOT NULL,
            source_label TEXT NOT NULL,
            row_number INTEGER,
            column_label TEXT,
            quality_flag TEXT,
            PRIMARY KEY (uploaded_file_id, sequence_index)
        );

        CREATE INDEX IF NOT EXISTS ix_parsed_readings_file_channel
            ON parsed_readings(uploaded_file_id, channel_id, timestamp);

        CREATE TABLE IF NOT EXISTS linked_temperature_readings (
            job_id TEXT NOT NULL REFERENCES calibration_jobs(id),
            sequence_index INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            dut_channel_id TEXT NOT NULL,
            indication_uploaded_file_id TEXT NOT NULL REFERENCES uploaded_files(id),
            indication_source_label TEXT NOT NULL,
            indication_row_number INTEGER,
            indication_column_label TEXT,
            indication_channel_id TEXT NOT NULL,
            indication_value REAL NOT NULL,
            indication_unit TEXT NOT NULL,
            indication_quality_flag TEXT,
            reference_uploaded_file_id TEXT NOT NULL REFERENCES uploaded_files(id),
            reference_source_label TEXT NOT NULL,
            reference_row_number INTEGER,
            reference_column_label TEXT,
            reference_channel_id TEXT NOT NULL,
            reference_value REAL NOT NULL,
            reference_unit TEXT NOT NULL,
            reference_quality_flag TEXT,
            PRIMARY KEY (job_id, sequence_index)
        );

        CREATE INDEX IF NOT EXISTS ix_linked_temperature_readings_job_channel
            ON linked_temperature_readings(job_id, dut_channel_id, timestamp);

        CREATE TABLE IF NOT EXISTS devices_under_test (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES calibration_jobs(id),
            make TEXT NOT NULL,
            model TEXT NOT NULL,
            serial_number TEXT NOT NULL,
            channel_id TEXT
        );

        CREATE INDEX IF NOT EXISTS ix_devices_under_test_job
            ON devices_under_test(job_id, id);

        CREATE UNIQUE INDEX IF NOT EXISTS ux_devices_under_test_identity
            ON devices_under_test(job_id, serial_number, coalesce(channel_id, ''));

        CREATE TABLE IF NOT EXISTS selected_reference_equipment (
            job_id TEXT NOT NULL REFERENCES calibration_jobs(id),
            equipment_id TEXT NOT NULL,
            simval_id TEXT NOT NULL,
            equipment_type TEXT NOT NULL,
            serial_number TEXT NOT NULL,
            discipline TEXT NOT NULL,
            calibration_certificate_reference TEXT NOT NULL,
            calibration_due_date TEXT NOT NULL,
            status TEXT NOT NULL,
            range_minimum REAL NOT NULL,
            range_maximum REAL NOT NULL,
            range_unit TEXT NOT NULL,
            traceability_statement TEXT NOT NULL,
            selected_by TEXT NOT NULL,
            selected_at TEXT NOT NULL,
            PRIMARY KEY (job_id, equipment_id)
        );

        CREATE INDEX IF NOT EXISTS ix_selected_reference_equipment_job
            ON selected_reference_equipment(job_id, simval_id, equipment_id);

        CREATE TABLE IF NOT EXISTS required_temperature_setpoints (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES calibration_jobs(id),
            setpoint REAL NOT NULL,
            unit TEXT NOT NULL,
            sequence_index INTEGER NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS ix_required_temperature_setpoints_job
            ON required_temperature_setpoints(job_id, sequence_index, id);

        CREATE UNIQUE INDEX IF NOT EXISTS ux_required_temperature_setpoints_sequence
            ON required_temperature_setpoints(job_id, sequence_index);

        CREATE UNIQUE INDEX IF NOT EXISTS ux_required_temperature_setpoints_value
            ON required_temperature_setpoints(job_id, setpoint, unit);

        CREATE TABLE IF NOT EXISTS measurement_windows (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES calibration_jobs(id),
            dut_id TEXT NOT NULL REFERENCES devices_under_test(id),
            setpoint REAL NOT NULL,
            unit TEXT NOT NULL,
            selected_by TEXT NOT NULL,
            selected_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS ix_measurement_windows_job
            ON measurement_windows(job_id, selected_at, id);

        CREATE TABLE IF NOT EXISTS measurement_window_readings (
            window_id TEXT NOT NULL REFERENCES measurement_windows(id),
            sequence_index INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT NOT NULL,
            uploaded_file_id TEXT NOT NULL REFERENCES uploaded_files(id),
            source_label TEXT NOT NULL,
            row_number INTEGER,
            column_label TEXT,
            quality_flag TEXT,
            PRIMARY KEY (window_id, sequence_index)
        );

        CREATE TABLE IF NOT EXISTS measurement_point_summaries (
            point_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES calibration_jobs(id),
            dut_id TEXT NOT NULL REFERENCES devices_under_test(id),
            measurement_window_id TEXT NOT NULL REFERENCES measurement_windows(id),
            reference REAL NOT NULL,
            indication REAL NOT NULL,
            unit TEXT NOT NULL,
            error_of_indication REAL NOT NULL,
            calculated_expanded_uncertainty TEXT NOT NULL,
            cmc_floor TEXT NOT NULL,
            reported_expanded_uncertainty TEXT NOT NULL,
            display_error_of_indication TEXT NOT NULL,
            calculation_engine_version TEXT NOT NULL,
            constant_set_version TEXT NOT NULL,
            budget_version TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS ix_measurement_point_summaries_job
            ON measurement_point_summaries(job_id, point_id);

        CREATE TABLE IF NOT EXISTS constant_sets (
            version TEXT PRIMARY KEY,
            discipline TEXT NOT NULL,
            status TEXT NOT NULL,
            effective_from TEXT NOT NULL,
            approved_by TEXT,
            approved_at TEXT
        );

        CREATE INDEX IF NOT EXISTS ix_constant_sets_status
            ON constant_sets(status, version);

        CREATE TABLE IF NOT EXISTS uncertainty_budgets (
            version TEXT PRIMARY KEY,
            budget_type TEXT NOT NULL,
            method TEXT NOT NULL,
            discipline TEXT NOT NULL,
            status TEXT NOT NULL,
            linked_constant_set_version TEXT NOT NULL REFERENCES constant_sets(version),
            approved_by TEXT,
            approved_at TEXT
        );

        CREATE INDEX IF NOT EXISTS ix_uncertainty_budgets_status
            ON uncertainty_budgets(status, version);

        CREATE TABLE IF NOT EXISTS certificates (
            certificate_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES calibration_jobs(id),
            certificate_number TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            software_version TEXT NOT NULL,
            calculation_engine_version TEXT NOT NULL,
            constant_set_version TEXT NOT NULL,
            budget_version TEXT NOT NULL,
            template_version TEXT NOT NULL,
            approved_by TEXT,
            approved_at TEXT,
            released_by TEXT,
            released_at TEXT
        );

        CREATE INDEX IF NOT EXISTS ix_certificates_job
            ON certificates(job_id, certificate_id);

        CREATE TABLE IF NOT EXISTS certificate_metadata (
            job_id TEXT PRIMARY KEY REFERENCES calibration_jobs(id),
            certificate_date TEXT NOT NULL,
            calibration_date TEXT NOT NULL,
            receipt_date TEXT NOT NULL,
            task_number TEXT NOT NULL,
            purchase_order TEXT NOT NULL,
            client_name TEXT NOT NULL,
            client_address TEXT NOT NULL,
            procedure TEXT NOT NULL,
            place TEXT NOT NULL,
            approved_by_label TEXT NOT NULL,
            remarks TEXT NOT NULL,
            traceability_statement TEXT NOT NULL,
            uncertainty_statement TEXT NOT NULL,
            ambient_conditions TEXT NOT NULL,
            temperature_scale TEXT NOT NULL,
            recorded_by TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS certificate_number_sequences (
            prefix TEXT PRIMARY KEY,
            next_value INTEGER NOT NULL CHECK (next_value > 0),
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'retired'))
        );

        CREATE TABLE IF NOT EXISTS certificate_calculation_summaries (
            certificate_id TEXT NOT NULL REFERENCES certificates(certificate_id),
            sequence_index INTEGER NOT NULL,
            point_id TEXT NOT NULL REFERENCES measurement_point_summaries(point_id),
            PRIMARY KEY (certificate_id, sequence_index)
        );

        CREATE TABLE IF NOT EXISTS export_artifacts (
            artifact_id TEXT PRIMARY KEY,
            certificate_id TEXT NOT NULL REFERENCES certificates(certificate_id),
            sequence_index INTEGER NOT NULL,
            artifact_type TEXT NOT NULL,
            filename TEXT NOT NULL,
            checksum_sha256 TEXT NOT NULL,
            storage_uri TEXT NOT NULL,
            generated_by TEXT NOT NULL,
            generated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS ix_export_artifacts_certificate
            ON export_artifacts(certificate_id, sequence_index);

        CREATE TABLE IF NOT EXISTS certificate_revisions (
            revision_id TEXT PRIMARY KEY,
            original_certificate_id TEXT NOT NULL REFERENCES certificates(certificate_id),
            original_certificate_number TEXT NOT NULL,
            reason TEXT NOT NULL,
            revised_by TEXT NOT NULL,
            revised_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS ix_certificate_revisions_original
            ON certificate_revisions(original_certificate_id, revision_id);

        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            action TEXT NOT NULL,
            user_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            previous_value_json TEXT,
            new_value_json TEXT,
            reason TEXT,
            software_version TEXT,
            calculation_engine_version TEXT,
            constant_set_version TEXT,
            budget_version TEXT
        );

        CREATE INDEX IF NOT EXISTS ix_audit_events_entity
            ON audit_events(entity_type, entity_id, id);

        CREATE TRIGGER IF NOT EXISTS audit_events_no_update
            BEFORE UPDATE ON audit_events
            BEGIN
                SELECT RAISE(ABORT, 'audit events are append-only');
            END;

        CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
            BEFORE DELETE ON audit_events
            BEGIN
                SELECT RAISE(ABORT, 'audit events are append-only');
            END;

        CREATE TRIGGER IF NOT EXISTS certificates_released_no_update
            BEFORE UPDATE ON certificates
            WHEN OLD.status = 'released'
            BEGIN
                SELECT RAISE(ABORT, 'released certificates are immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS certificates_released_no_delete
            BEFORE DELETE ON certificates
            WHEN OLD.status = 'released'
            BEGIN
                SELECT RAISE(ABORT, 'released certificates are immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS certificate_metadata_no_update
            BEFORE UPDATE ON certificate_metadata
            BEGIN
                SELECT RAISE(ABORT, 'certificate metadata is immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS certificate_metadata_no_delete
            BEFORE DELETE ON certificate_metadata
            BEGIN
                SELECT RAISE(ABORT, 'certificate metadata is immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS measurement_point_summaries_no_update
            BEFORE UPDATE ON measurement_point_summaries
            BEGIN
                SELECT RAISE(ABORT, 'calculation summaries are immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS measurement_point_summaries_no_delete
            BEFORE DELETE ON measurement_point_summaries
            BEGIN
                SELECT RAISE(ABORT, 'calculation summaries are immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS export_artifacts_no_update
            BEFORE UPDATE ON export_artifacts
            BEGIN
                SELECT RAISE(ABORT, 'export artifacts are immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS export_artifacts_no_delete
            BEFORE DELETE ON export_artifacts
            BEGIN
                SELECT RAISE(ABORT, 'export artifacts are immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS constant_sets_no_update
            BEFORE UPDATE ON constant_sets
            BEGIN
                SELECT RAISE(ABORT, 'constant sets are immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS constant_sets_no_delete
            BEFORE DELETE ON constant_sets
            BEGIN
                SELECT RAISE(ABORT, 'constant sets are immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS uncertainty_budgets_no_update
            BEFORE UPDATE ON uncertainty_budgets
            BEGIN
                SELECT RAISE(ABORT, 'uncertainty budgets are immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS uncertainty_budgets_no_delete
            BEFORE DELETE ON uncertainty_budgets
            BEGIN
                SELECT RAISE(ABORT, 'uncertainty budgets are immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS parsed_readings_no_update
            BEFORE UPDATE ON parsed_readings
            BEGIN
                SELECT RAISE(ABORT, 'parsed readings are immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS parsed_readings_no_delete
            BEFORE DELETE ON parsed_readings
            BEGIN
                SELECT RAISE(ABORT, 'parsed readings are immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS linked_temperature_readings_source_jobs
            BEFORE INSERT ON linked_temperature_readings
            WHEN (
                SELECT job_id FROM uploaded_files
                WHERE id = NEW.indication_uploaded_file_id
            ) != NEW.job_id
            OR (
                SELECT job_id FROM uploaded_files
                WHERE id = NEW.reference_uploaded_file_id
            ) != NEW.job_id
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'linked temperature source files must belong to the job'
                );
            END;

        CREATE TRIGGER IF NOT EXISTS linked_temperature_readings_no_update
            BEFORE UPDATE ON linked_temperature_readings
            BEGIN
                SELECT RAISE(ABORT, 'linked temperature readings are immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS linked_temperature_readings_no_delete
            BEFORE DELETE ON linked_temperature_readings
            BEGIN
                SELECT RAISE(ABORT, 'linked temperature readings are immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS required_temperature_setpoints_no_update
            BEFORE UPDATE ON required_temperature_setpoints
            BEGIN
                SELECT RAISE(ABORT, 'required temperature setpoints are immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS required_temperature_setpoints_no_delete
            BEFORE DELETE ON required_temperature_setpoints
            BEGIN
                SELECT RAISE(ABORT, 'required temperature setpoints are immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS selected_reference_equipment_no_update
            BEFORE UPDATE ON selected_reference_equipment
            BEGIN
                SELECT RAISE(ABORT, 'selected reference equipment is immutable');
            END;

        CREATE TRIGGER IF NOT EXISTS selected_reference_equipment_no_delete
            BEFORE DELETE ON selected_reference_equipment
            BEGIN
                SELECT RAISE(ABORT, 'selected reference equipment is immutable');
            END;
        """
    )
    _ensure_certificate_number_sequence_status_column(connection)
    connection.execute(
        """
        INSERT OR IGNORE INTO schema_migrations (
            version,
            applied_at
        )
        VALUES (?, ?)
        """,
        (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
    )
    connection.commit()


def list_schema_versions(connection: sqlite3.Connection) -> tuple[str, ...]:
    """Return applied schema version markers in deterministic order."""
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT version
        FROM schema_migrations
        ORDER BY version ASC
        """
    ).fetchall()
    return tuple(row["version"] for row in rows)


def _ensure_certificate_number_sequence_status_column(
    connection: sqlite3.Connection,
) -> None:
    connection.row_factory = sqlite3.Row
    columns = {
        str(row["name"])
        for row in connection.execute(
            "PRAGMA table_info(certificate_number_sequences)"
        ).fetchall()
    }
    if "status" in columns:
        return
    connection.execute(
        """
        ALTER TABLE certificate_number_sequences
        ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'retired'))
        """
    )


class SQLiteUserAccountRepository:
    """Repository for persisted user identities."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self._connection = connection
        self._autocommit = autocommit

    def add(self, user: UserAccount) -> None:
        try:
            self._connection.execute(
                """
                INSERT INTO user_accounts (
                    id,
                    display_name,
                    email,
                    roles_json,
                    active,
                    signature_label,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.id,
                    user.display_name,
                    user.email,
                    _roles_to_json(user.roles),
                    1 if user.active else 0,
                    user.signature_label,
                    _datetime_to_text(user.created_at, "User created_at"),
                ),
            )
            self._commit_if_needed()
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not store user account.") from error

    def get(self, user_id: str) -> UserAccount:
        row = self._connection.execute(
            """
            SELECT
                id,
                display_name,
                email,
                roles_json,
                active,
                signature_label,
                created_at
            FROM user_accounts
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"User account {user_id!r} was not found.")
        return _user_account_from_row(row)

    def list_active(self) -> tuple[UserAccount, ...]:
        rows = self._connection.execute(
            """
            SELECT
                id,
                display_name,
                email,
                roles_json,
                active,
                signature_label,
                created_at
            FROM user_accounts
            WHERE active = 1
            ORDER BY id ASC
            """
        ).fetchall()
        return tuple(_user_account_from_row(row) for row in rows)

    def update_roles(
        self,
        *,
        user_id: str,
        roles: tuple[Role, ...],
    ) -> UserAccount:
        current = self.get(user_id)
        updated = UserAccount(
            id=current.id,
            display_name=current.display_name,
            email=current.email,
            roles=roles,
            active=current.active,
            signature_label=current.signature_label,
            created_at=current.created_at,
        )
        try:
            self._connection.execute(
                """
                UPDATE user_accounts
                SET roles_json = ?
                WHERE id = ?
                """,
                (_roles_to_json(updated.roles), user_id),
            )
            self._commit_if_needed()
            return self.get(user_id)
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not update user account roles.") from error

    def set_active(
        self,
        *,
        user_id: str,
        active: bool,
    ) -> UserAccount:
        current = self.get(user_id)
        updated = UserAccount(
            id=current.id,
            display_name=current.display_name,
            email=current.email,
            roles=current.roles,
            active=active,
            signature_label=current.signature_label,
            created_at=current.created_at,
        )
        try:
            self._connection.execute(
                """
                UPDATE user_accounts
                SET active = ?
                WHERE id = ?
                """,
                (1 if updated.active else 0, user_id),
            )
            self._commit_if_needed()
            return self.get(user_id)
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not update user account active state.") from error

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


class SQLiteUserSessionRepository:
    """Repository for persisted authenticated sessions."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self._connection = connection
        self._autocommit = autocommit

    def add(self, session: UserSession) -> None:
        try:
            self._connection.execute(
                """
                INSERT INTO user_sessions (
                    id,
                    user_id,
                    issued_at,
                    expires_at,
                    revoked_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.user_id,
                    _datetime_to_text(session.issued_at, "Session issued_at"),
                    _datetime_to_text(session.expires_at, "Session expires_at"),
                    _optional_datetime_to_text(
                        session.revoked_at,
                        "Session revoked_at",
                    ),
                ),
            )
            self._commit_if_needed()
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not store user session.") from error

    def get(self, session_id: str) -> UserSession:
        row = self._connection.execute(
            """
            SELECT
                id,
                user_id,
                issued_at,
                expires_at,
                revoked_at
            FROM user_sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"User session {session_id!r} was not found.")
        return _user_session_from_row(row)

    def revoke(self, *, session_id: str, revoked_at: datetime) -> UserSession:
        try:
            cursor = self._connection.execute(
                """
                UPDATE user_sessions
                SET revoked_at = ?
                WHERE id = ?
                  AND revoked_at IS NULL
                """,
                (
                    _datetime_to_text(revoked_at, "Session revoked_at"),
                    session_id,
                ),
            )
            if cursor.rowcount != 1:
                self.get(session_id)
                raise PersistenceError("User session is already revoked.")
            self._commit_if_needed()
            return self.get(session_id)
        except (RecordNotFoundError, PersistenceError):
            self._rollback_if_needed()
            raise
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not revoke user session.") from error

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


class SQLiteCalibrationJobRepository:
    """Repository for calibration job metadata and workflow state."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        self._connection = connection
        self._autocommit = autocommit

    def add(self, job: CalibrationJob) -> None:
        try:
            self._connection.execute(
                """
                INSERT INTO calibration_jobs (
                    id,
                    client_name,
                    client_address,
                    discipline,
                    measurement_mode,
                    method,
                    created_by,
                    state,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.client.name,
                    job.client.address,
                    job.discipline.value,
                    job.measurement_mode.value,
                    job.method,
                    job.created_by,
                    job.state.value,
                    _datetime_to_text(job.created_at, "Calibration job created_at"),
                ),
            )
            self._commit_if_needed()
        except sqlite3.IntegrityError as error:
            self._rollback_if_needed()
            raise PersistenceError(f"Calibration job {job.id!r} already exists.") from error
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not store calibration job.") from error

    def get(self, job_id: str) -> CalibrationJob:
        row = self._connection.execute(
            """
            SELECT
                id,
                client_name,
                client_address,
                discipline,
                measurement_mode,
                method,
                created_by,
                state,
                created_at
            FROM calibration_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"Calibration job {job_id!r} was not found.")
        return _job_from_row(row)

    def update_state(
        self,
        *,
        job_id: str,
        expected_state: WorkflowState,
        new_state: WorkflowState,
    ) -> CalibrationJob:
        try:
            cursor = self._connection.execute(
                """
                UPDATE calibration_jobs
                SET state = ?
                WHERE id = ?
                  AND state = ?
                """,
                (new_state.value, job_id, expected_state.value),
            )
            if cursor.rowcount != 1:
                row = self._connection.execute(
                    "SELECT state FROM calibration_jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
                if row is None:
                    raise RecordNotFoundError(
                        f"Calibration job {job_id!r} was not found."
                    )
                raise ConcurrencyError(
                    "Calibration job state changed before the update could be saved."
                )
            self._commit_if_needed()
            return self.get(job_id)
        except PersistenceError:
            self._rollback_if_needed()
            raise
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not update calibration job state.") from error

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


class SQLiteUploadedFileRepository:
    """Repository for raw uploaded file evidence."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self._connection = connection
        self._autocommit = autocommit

    def add(self, uploaded_file: UploadedFile) -> None:
        try:
            self._connection.execute(
                """
                INSERT INTO uploaded_files (
                    id,
                    job_id,
                    original_filename,
                    checksum_sha256,
                    file_kind,
                    storage_uri,
                    parser_version,
                    uploaded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uploaded_file.id,
                    uploaded_file.job_id,
                    uploaded_file.original_filename,
                    uploaded_file.checksum_sha256,
                    uploaded_file.file_kind.value,
                    uploaded_file.storage_uri,
                    uploaded_file.parser_version,
                    _datetime_to_text(uploaded_file.uploaded_at, "Uploaded file uploaded_at"),
                ),
            )
            self._commit_if_needed()
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not store uploaded file evidence.") from error

    def get(self, uploaded_file_id: str) -> UploadedFile:
        row = self._connection.execute(
            """
            SELECT
                id,
                job_id,
                original_filename,
                checksum_sha256,
                file_kind,
                storage_uri,
                parser_version,
                uploaded_at
            FROM uploaded_files
            WHERE id = ?
            """,
            (uploaded_file_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"Uploaded file {uploaded_file_id!r} was not found."
            )
        return _uploaded_file_from_row(row)

    def list_for_job(self, job_id: str) -> tuple[UploadedFile, ...]:
        rows = self._connection.execute(
            """
            SELECT
                id,
                job_id,
                original_filename,
                checksum_sha256,
                file_kind,
                storage_uri,
                parser_version,
                uploaded_at
            FROM uploaded_files
            WHERE job_id = ?
            ORDER BY id ASC
            """,
            (job_id,),
        ).fetchall()
        return tuple(_uploaded_file_from_row(row) for row in rows)

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


class SQLiteParsedReadingRepository:
    """Repository for immutable raw readings produced by import parsers."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self._connection = connection
        self._autocommit = autocommit

    def add_many(self, readings: tuple[MeasurementReading, ...]) -> None:
        if len(readings) == 0:
            return
        next_indexes = self._next_indexes_by_uploaded_file(readings)
        try:
            for reading in readings:
                uploaded_file_id = reading.source.uploaded_file_id
                sequence_index = next_indexes[uploaded_file_id]
                next_indexes[uploaded_file_id] += 1
                self._connection.execute(
                    """
                    INSERT INTO parsed_readings (
                        uploaded_file_id,
                        sequence_index,
                        timestamp,
                        channel_id,
                        value,
                        unit,
                        source_label,
                        row_number,
                        column_label,
                        quality_flag
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uploaded_file_id,
                        sequence_index,
                        _datetime_to_text(reading.timestamp, "Parsed reading timestamp"),
                        reading.channel_id,
                        reading.value,
                        reading.unit,
                        reading.source.source_label,
                        reading.source.row_number,
                        reading.source.column_label,
                        reading.quality_flag,
                    ),
                )
            self._commit_if_needed()
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not store parsed readings.") from error

    def list_for_uploaded_file(
        self,
        uploaded_file_id: str,
    ) -> tuple[MeasurementReading, ...]:
        rows = self._connection.execute(
            """
            SELECT
                timestamp,
                channel_id,
                value,
                unit,
                uploaded_file_id,
                source_label,
                row_number,
                column_label,
                quality_flag
            FROM parsed_readings
            WHERE uploaded_file_id = ?
            ORDER BY sequence_index ASC
            """,
            (uploaded_file_id,),
        ).fetchall()
        return tuple(_reading_from_row(row) for row in rows)

    def _next_indexes_by_uploaded_file(
        self,
        readings: tuple[MeasurementReading, ...],
    ) -> dict[str, int]:
        next_indexes: dict[str, int] = {}
        for reading in readings:
            uploaded_file_id = reading.source.uploaded_file_id
            if uploaded_file_id in next_indexes:
                continue
            row = self._connection.execute(
                """
                SELECT coalesce(max(sequence_index), -1) + 1 AS next_index
                FROM parsed_readings
                WHERE uploaded_file_id = ?
                """,
                (uploaded_file_id,),
            ).fetchone()
            next_indexes[uploaded_file_id] = int(row["next_index"])
        return next_indexes

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


class SQLiteLinkedTemperatureReadingRepository:
    """Repository for immutable logger/IRTD links produced during import review."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self._connection = connection
        self._autocommit = autocommit

    def add_many(
        self,
        *,
        job_id: str,
        linked_readings: tuple[LinkedTemperatureReading, ...],
    ) -> None:
        _require_text(job_id, "Linked temperature reading job id")
        if len(linked_readings) == 0:
            return
        next_index = self._next_index_for_job(job_id)
        try:
            for offset, linked_reading in enumerate(linked_readings):
                self._connection.execute(
                    """
                    INSERT INTO linked_temperature_readings (
                        job_id,
                        sequence_index,
                        timestamp,
                        dut_channel_id,
                        indication_uploaded_file_id,
                        indication_source_label,
                        indication_row_number,
                        indication_column_label,
                        indication_channel_id,
                        indication_value,
                        indication_unit,
                        indication_quality_flag,
                        reference_uploaded_file_id,
                        reference_source_label,
                        reference_row_number,
                        reference_column_label,
                        reference_channel_id,
                        reference_value,
                        reference_unit,
                        reference_quality_flag
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _linked_temperature_reading_values(
                        job_id=job_id,
                        sequence_index=next_index + offset,
                        linked_reading=linked_reading,
                    ),
                )
            self._commit_if_needed()
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError(
                "Could not store linked temperature readings."
            ) from error

    def list_for_job(self, job_id: str) -> tuple[LinkedTemperatureReading, ...]:
        rows = self._connection.execute(
            """
            SELECT
                timestamp,
                dut_channel_id,
                indication_uploaded_file_id,
                indication_source_label,
                indication_row_number,
                indication_column_label,
                indication_channel_id,
                indication_value,
                indication_unit,
                indication_quality_flag,
                reference_uploaded_file_id,
                reference_source_label,
                reference_row_number,
                reference_column_label,
                reference_channel_id,
                reference_value,
                reference_unit,
                reference_quality_flag
            FROM linked_temperature_readings
            WHERE job_id = ?
            ORDER BY sequence_index ASC
            """,
            (job_id,),
        ).fetchall()
        return tuple(_linked_temperature_reading_from_row(row) for row in rows)

    def _next_index_for_job(self, job_id: str) -> int:
        row = self._connection.execute(
            """
            SELECT coalesce(max(sequence_index), -1) + 1 AS next_index
            FROM linked_temperature_readings
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()
        return int(row["next_index"])

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


class SQLiteDeviceUnderTestRepository:
    """Repository for device-under-test records."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self._connection = connection
        self._autocommit = autocommit

    def add(self, dut: DeviceUnderTest) -> None:
        try:
            self._connection.execute(
                """
                INSERT INTO devices_under_test (
                    id,
                    job_id,
                    make,
                    model,
                    serial_number,
                    channel_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    dut.id,
                    dut.job_id,
                    dut.make,
                    dut.model,
                    dut.serial_number,
                    dut.channel_id,
                ),
            )
            self._commit_if_needed()
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not store device under test.") from error

    def get(self, dut_id: str) -> DeviceUnderTest:
        row = self._connection.execute(
            """
            SELECT
                id,
                job_id,
                make,
                model,
                serial_number,
                channel_id
            FROM devices_under_test
            WHERE id = ?
            """,
            (dut_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"DUT {dut_id!r} was not found.")
        return _dut_from_row(row)

    def list_for_job(self, job_id: str) -> tuple[DeviceUnderTest, ...]:
        rows = self._connection.execute(
            """
            SELECT
                id,
                job_id,
                make,
                model,
                serial_number,
                channel_id
            FROM devices_under_test
            WHERE job_id = ?
            ORDER BY id ASC
            """,
            (job_id,),
        ).fetchall()
        return tuple(_dut_from_row(row) for row in rows)

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


class SQLiteSelectedReferenceEquipmentRepository:
    """Repository for immutable selected reference-equipment snapshots."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self._connection = connection
        self._autocommit = autocommit

    def add(self, selection: SelectedReferenceEquipment) -> None:
        equipment = selection.equipment
        try:
            self._connection.execute(
                """
                INSERT INTO selected_reference_equipment (
                    job_id,
                    equipment_id,
                    simval_id,
                    equipment_type,
                    serial_number,
                    discipline,
                    calibration_certificate_reference,
                    calibration_due_date,
                    status,
                    range_minimum,
                    range_maximum,
                    range_unit,
                    traceability_statement,
                    selected_by,
                    selected_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    selection.job_id,
                    equipment.id,
                    equipment.simval_id,
                    equipment.equipment_type,
                    equipment.serial_number,
                    equipment.discipline.value,
                    equipment.calibration_certificate_reference,
                    _date_to_text(
                        equipment.calibration_due_date,
                        "Reference equipment due date",
                    ),
                    equipment.status.value,
                    equipment.usable_range.minimum,
                    equipment.usable_range.maximum,
                    equipment.usable_range.unit,
                    equipment.traceability_statement,
                    selection.selected_by,
                    _datetime_to_text(
                        selection.selected_at,
                        "Selected reference equipment timestamp",
                    ),
                ),
            )
            self._commit_if_needed()
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError(
                "Could not store selected reference equipment."
            ) from error

    def list_for_job(self, job_id: str) -> tuple[SelectedReferenceEquipment, ...]:
        rows = self._connection.execute(
            """
            SELECT
                job_id,
                equipment_id,
                simval_id,
                equipment_type,
                serial_number,
                discipline,
                calibration_certificate_reference,
                calibration_due_date,
                status,
                range_minimum,
                range_maximum,
                range_unit,
                traceability_statement,
                selected_by,
                selected_at
            FROM selected_reference_equipment
            WHERE job_id = ?
            ORDER BY simval_id ASC, equipment_id ASC
            """,
            (job_id,),
        ).fetchall()
        return tuple(_selected_reference_equipment_from_row(row) for row in rows)

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


class SQLiteRequiredTemperatureSetpointRepository:
    """Repository for immutable required temperature setpoint plans."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self._connection = connection
        self._autocommit = autocommit

    def add_many(self, setpoints: tuple[RequiredTemperatureSetpoint, ...]) -> None:
        if len(setpoints) == 0:
            return
        try:
            for setpoint in setpoints:
                self._connection.execute(
                    """
                    INSERT INTO required_temperature_setpoints (
                        id,
                        job_id,
                        setpoint,
                        unit,
                        sequence_index,
                        created_by,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        setpoint.id,
                        setpoint.job_id,
                        setpoint.setpoint,
                        setpoint.unit,
                        setpoint.sequence_index,
                        setpoint.created_by,
                        _datetime_to_text(
                            setpoint.created_at,
                            "Required temperature setpoint created_at",
                        ),
                    ),
                )
            self._commit_if_needed()
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError(
                "Could not store required temperature setpoint plan."
            ) from error

    def get(self, setpoint_id: str) -> RequiredTemperatureSetpoint:
        row = self._connection.execute(
            """
            SELECT
                id,
                job_id,
                setpoint,
                unit,
                sequence_index,
                created_by,
                created_at
            FROM required_temperature_setpoints
            WHERE id = ?
            """,
            (setpoint_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"Required temperature setpoint {setpoint_id!r} was not found."
            )
        return _required_temperature_setpoint_from_row(row)

    def list_for_job(self, job_id: str) -> tuple[RequiredTemperatureSetpoint, ...]:
        rows = self._connection.execute(
            """
            SELECT
                id,
                job_id,
                setpoint,
                unit,
                sequence_index,
                created_by,
                created_at
            FROM required_temperature_setpoints
            WHERE job_id = ?
            ORDER BY sequence_index ASC, id ASC
            """,
            (job_id,),
        ).fetchall()
        return tuple(_required_temperature_setpoint_from_row(row) for row in rows)

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


class SQLiteMeasurementWindowRepository:
    """Repository for selected measurement windows and their source readings."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self._connection = connection
        self._autocommit = autocommit

    def add(self, window: MeasurementWindow) -> None:
        try:
            self._connection.execute(
                """
                INSERT INTO measurement_windows (
                    id,
                    job_id,
                    dut_id,
                    setpoint,
                    unit,
                    selected_by,
                    selected_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    window.id,
                    window.job_id,
                    window.dut_id,
                    window.setpoint,
                    window.unit,
                    window.selected_by,
                    _datetime_to_text(window.selected_at, "Measurement window selected_at"),
                ),
            )
            for sequence_index, reading in enumerate(window.readings):
                self._connection.execute(
                    """
                    INSERT INTO measurement_window_readings (
                        window_id,
                        sequence_index,
                        timestamp,
                        channel_id,
                        value,
                        unit,
                        uploaded_file_id,
                        source_label,
                        row_number,
                        column_label,
                        quality_flag
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        window.id,
                        sequence_index,
                        _datetime_to_text(reading.timestamp, "Reading timestamp"),
                        reading.channel_id,
                        reading.value,
                        reading.unit,
                        reading.source.uploaded_file_id,
                        reading.source.source_label,
                        reading.source.row_number,
                        reading.source.column_label,
                        reading.quality_flag,
                    ),
                )
            self._commit_if_needed()
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not store measurement window.") from error

    def get(self, window_id: str) -> MeasurementWindow:
        row = self._connection.execute(
            """
            SELECT
                id,
                job_id,
                dut_id,
                setpoint,
                unit,
                selected_by,
                selected_at
            FROM measurement_windows
            WHERE id = ?
            """,
            (window_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"Measurement window {window_id!r} was not found."
            )
        return _measurement_window_from_row(
            row,
            self._reading_rows_for_window(window_id),
        )

    def list_for_job(self, job_id: str) -> tuple[MeasurementWindow, ...]:
        rows = self._connection.execute(
            """
            SELECT id
            FROM measurement_windows
            WHERE job_id = ?
            ORDER BY selected_at ASC, id ASC
            """,
            (job_id,),
        ).fetchall()
        return tuple(self.get(row["id"]) for row in rows)

    def _reading_rows_for_window(self, window_id: str) -> tuple[sqlite3.Row, ...]:
        rows = self._connection.execute(
            """
            SELECT
                timestamp,
                channel_id,
                value,
                unit,
                uploaded_file_id,
                source_label,
                row_number,
                column_label,
                quality_flag
            FROM measurement_window_readings
            WHERE window_id = ?
            ORDER BY sequence_index ASC
            """,
            (window_id,),
        ).fetchall()
        return tuple(rows)

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


class SQLiteMeasurementPointSummaryRepository:
    """Repository for immutable measurement-point calculation summaries."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self._connection = connection
        self._autocommit = autocommit

    def add(self, summary: MeasurementPointSummary) -> None:
        try:
            self._connection.execute(
                """
                INSERT INTO measurement_point_summaries (
                    point_id,
                    job_id,
                    dut_id,
                    measurement_window_id,
                    reference,
                    indication,
                    unit,
                    error_of_indication,
                    calculated_expanded_uncertainty,
                    cmc_floor,
                    reported_expanded_uncertainty,
                    display_error_of_indication,
                    calculation_engine_version,
                    constant_set_version,
                    budget_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.point_id,
                    summary.job_id,
                    summary.dut_id,
                    summary.measurement_window_id,
                    summary.reference,
                    summary.indication,
                    summary.unit,
                    summary.error_of_indication,
                    str(summary.calculated_expanded_uncertainty),
                    str(summary.cmc_floor),
                    str(summary.reported_expanded_uncertainty),
                    str(summary.display_error_of_indication),
                    summary.calculation_engine_version,
                    summary.constant_set_version,
                    summary.budget_version,
                ),
            )
            self._commit_if_needed()
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not store calculation summary.") from error

    def get(self, point_id: str) -> MeasurementPointSummary:
        row = self._connection.execute(
            """
            SELECT
                point_id,
                job_id,
                dut_id,
                measurement_window_id,
                reference,
                indication,
                unit,
                error_of_indication,
                calculated_expanded_uncertainty,
                cmc_floor,
                reported_expanded_uncertainty,
                display_error_of_indication,
                calculation_engine_version,
                constant_set_version,
                budget_version
            FROM measurement_point_summaries
            WHERE point_id = ?
            """,
            (point_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"Calculation summary {point_id!r} was not found."
            )
        return _measurement_point_summary_from_row(row)

    def list_for_job(self, job_id: str) -> tuple[MeasurementPointSummary, ...]:
        rows = self._connection.execute(
            """
            SELECT
                point_id,
                job_id,
                dut_id,
                measurement_window_id,
                reference,
                indication,
                unit,
                error_of_indication,
                calculated_expanded_uncertainty,
                cmc_floor,
                reported_expanded_uncertainty,
                display_error_of_indication,
                calculation_engine_version,
                constant_set_version,
                budget_version
            FROM measurement_point_summaries
            WHERE job_id = ?
            ORDER BY point_id ASC
            """,
            (job_id,),
        ).fetchall()
        return tuple(_measurement_point_summary_from_row(row) for row in rows)

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


class SQLiteConstantSetRepository:
    """Repository for immutable constant-set version records."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self._connection = connection
        self._autocommit = autocommit

    def add(self, constant_set: ConstantSet) -> None:
        try:
            self._connection.execute(
                """
                INSERT INTO constant_sets (
                    version,
                    discipline,
                    status,
                    effective_from,
                    approved_by,
                    approved_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    constant_set.version,
                    constant_set.discipline.value,
                    constant_set.status.value,
                    _datetime_to_text(
                        constant_set.effective_from,
                        "Constant set effective_from",
                    ),
                    constant_set.approved_by,
                    _optional_datetime_to_text(
                        constant_set.approved_at,
                        "Constant set approved_at",
                    ),
                ),
            )
            self._commit_if_needed()
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not store constant set.") from error

    def get(self, version: str) -> ConstantSet:
        row = self._connection.execute(
            """
            SELECT
                version,
                discipline,
                status,
                effective_from,
                approved_by,
                approved_at
            FROM constant_sets
            WHERE version = ?
            """,
            (version,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"Constant set {version!r} was not found.")
        return _constant_set_from_row(row)

    def list_approved(self) -> tuple[ConstantSet, ...]:
        rows = self._connection.execute(
            """
            SELECT
                version,
                discipline,
                status,
                effective_from,
                approved_by,
                approved_at
            FROM constant_sets
            WHERE status = ?
            ORDER BY version ASC
            """,
            (VersionStatus.APPROVED.value,),
        ).fetchall()
        return tuple(_constant_set_from_row(row) for row in rows)

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


class SQLiteUncertaintyBudgetRepository:
    """Repository for immutable uncertainty-budget version records."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self._connection = connection
        self._autocommit = autocommit

    def add(self, budget: UncertaintyBudget) -> None:
        try:
            self._connection.execute(
                """
                INSERT INTO uncertainty_budgets (
                    version,
                    budget_type,
                    method,
                    discipline,
                    status,
                    linked_constant_set_version,
                    approved_by,
                    approved_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    budget.version,
                    budget.budget_type,
                    budget.method,
                    budget.discipline.value,
                    budget.status.value,
                    budget.linked_constant_set_version,
                    budget.approved_by,
                    _optional_datetime_to_text(
                        budget.approved_at,
                        "Uncertainty budget approved_at",
                    ),
                ),
            )
            self._commit_if_needed()
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not store uncertainty budget.") from error

    def get(self, version: str) -> UncertaintyBudget:
        row = self._connection.execute(
            """
            SELECT
                version,
                budget_type,
                method,
                discipline,
                status,
                linked_constant_set_version,
                approved_by,
                approved_at
            FROM uncertainty_budgets
            WHERE version = ?
            """,
            (version,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"Uncertainty budget {version!r} was not found."
            )
        return _uncertainty_budget_from_row(row)

    def list_approved(self) -> tuple[UncertaintyBudget, ...]:
        rows = self._connection.execute(
            """
            SELECT
                version,
                budget_type,
                method,
                discipline,
                status,
                linked_constant_set_version,
                approved_by,
                approved_at
            FROM uncertainty_budgets
            WHERE status = ?
            ORDER BY version ASC
            """,
            (VersionStatus.APPROVED.value,),
        ).fetchall()
        return tuple(_uncertainty_budget_from_row(row) for row in rows)

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


class SQLiteCertificateNumberAllocator:
    """Internal certificate number sequence allocator."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self._connection = connection
        self._autocommit = autocommit

    def create_sequence(self, *, prefix: str, next_value: int) -> None:
        _require_text(prefix, "Certificate number prefix")
        if next_value < 1:
            raise PersistenceError("Certificate number next value must be positive.")
        try:
            self._connection.execute(
                """
                INSERT INTO certificate_number_sequences (
                    prefix,
                    next_value,
                    status
                )
                VALUES (?, ?, ?)
                """,
                (prefix, next_value, "active"),
            )
            self._commit_if_needed()
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError(
                "Could not create certificate number sequence."
            ) from error

    def allocate_next(self, *, prefix: str, padding: int) -> str:
        _require_text(prefix, "Certificate number prefix")
        if padding < 1 or padding > 12:
            raise PersistenceError("Certificate number padding must be between 1 and 12.")
        try:
            row = self._connection.execute(
                """
                SELECT
                    next_value,
                    status
                FROM certificate_number_sequences
                WHERE prefix = ?
                """,
                (prefix,),
            ).fetchone()
            if row is None:
                raise RecordNotFoundError(
                    f"Certificate number sequence {prefix!r} was not found."
                )
            status = str(row["status"])
            if status != "active":
                raise PersistenceError(
                    f"Certificate number sequence {prefix!r} is not active."
                )
            next_value = int(row["next_value"])
            self._connection.execute(
                """
                UPDATE certificate_number_sequences
                SET next_value = ?
                WHERE prefix = ?
                """,
                (next_value + 1, prefix),
            )
            self._commit_if_needed()
            return f"{prefix}-{next_value:0{padding}d}"
        except PersistenceError:
            self._rollback_if_needed()
            raise
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError(
                "Could not allocate certificate number."
            ) from error

    def next_value(self, prefix: str) -> int:
        _require_text(prefix, "Certificate number prefix")
        row = self._connection.execute(
            """
            SELECT next_value
            FROM certificate_number_sequences
            WHERE prefix = ?
            """,
            (prefix,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"Certificate number sequence {prefix!r} was not found."
            )
        return int(row["next_value"])

    def status(self, prefix: str) -> str:
        _require_text(prefix, "Certificate number prefix")
        row = self._connection.execute(
            """
            SELECT status
            FROM certificate_number_sequences
            WHERE prefix = ?
            """,
            (prefix,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"Certificate number sequence {prefix!r} was not found."
            )
        return str(row["status"])

    def retire_sequence(self, prefix: str) -> None:
        _require_text(prefix, "Certificate number prefix")
        try:
            cursor = self._connection.execute(
                """
                UPDATE certificate_number_sequences
                SET status = 'retired'
                WHERE prefix = ?
                  AND status = 'active'
                """,
                (prefix,),
            )
            if cursor.rowcount != 1:
                row = self._connection.execute(
                    """
                    SELECT status
                    FROM certificate_number_sequences
                    WHERE prefix = ?
                    """,
                    (prefix,),
                ).fetchone()
                if row is None:
                    raise RecordNotFoundError(
                        f"Certificate number sequence {prefix!r} was not found."
                    )
                raise PersistenceError(
                    f"Certificate number sequence {prefix!r} is not active."
                )
            self._commit_if_needed()
        except PersistenceError:
            self._rollback_if_needed()
            raise
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError(
                "Could not retire certificate number sequence."
            ) from error

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


class SQLiteCertificateMetadataRepository:
    """Repository for immutable certificate metadata snapshots."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self._connection = connection
        self._autocommit = autocommit

    def add(self, metadata: CertificateMetadata) -> None:
        try:
            self._connection.execute(
                """
                INSERT INTO certificate_metadata (
                    job_id,
                    certificate_date,
                    calibration_date,
                    receipt_date,
                    task_number,
                    purchase_order,
                    client_name,
                    client_address,
                    procedure,
                    place,
                    approved_by_label,
                    remarks,
                    traceability_statement,
                    uncertainty_statement,
                    ambient_conditions,
                    temperature_scale,
                    recorded_by,
                    recorded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata.job_id,
                    _date_to_text(metadata.certificate_date, "Certificate date"),
                    _date_to_text(metadata.calibration_date, "Calibration date"),
                    _date_to_text(metadata.receipt_date, "Receipt date"),
                    metadata.task_number,
                    metadata.purchase_order,
                    metadata.client_name,
                    metadata.client_address,
                    metadata.procedure,
                    metadata.place,
                    metadata.approved_by_label,
                    metadata.remarks,
                    metadata.traceability_statement,
                    metadata.uncertainty_statement,
                    metadata.ambient_conditions,
                    metadata.temperature_scale,
                    metadata.recorded_by,
                    _datetime_to_text(metadata.recorded_at, "Metadata recorded_at"),
                ),
            )
            self._commit_if_needed()
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not store certificate metadata.") from error

    def get(self, job_id: str) -> CertificateMetadata:
        row = self._connection.execute(
            """
            SELECT
                job_id,
                certificate_date,
                calibration_date,
                receipt_date,
                task_number,
                purchase_order,
                client_name,
                client_address,
                procedure,
                place,
                approved_by_label,
                remarks,
                traceability_statement,
                uncertainty_statement,
                ambient_conditions,
                temperature_scale,
                recorded_by,
                recorded_at
            FROM certificate_metadata
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"Certificate metadata for job {job_id!r} was not found."
            )
        return _certificate_metadata_from_row(row)

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


class SQLiteCertificateRecordRepository:
    """Repository for certificate records and generated export artifacts."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self._connection = connection
        self._autocommit = autocommit

    def add(self, certificate: CertificateRecord) -> None:
        try:
            self._connection.execute(
                """
                INSERT INTO certificates (
                    certificate_id,
                    job_id,
                    certificate_number,
                    status,
                    software_version,
                    calculation_engine_version,
                    constant_set_version,
                    budget_version,
                    template_version,
                    approved_by,
                    approved_at,
                    released_by,
                    released_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    certificate.certificate_id,
                    certificate.job_id,
                    certificate.certificate_number,
                    certificate.status.value,
                    certificate.software_version,
                    certificate.calculation_engine_version,
                    certificate.constant_set_version,
                    certificate.budget_version,
                    certificate.template_version,
                    certificate.approved_by,
                    _optional_datetime_to_text(
                        certificate.approved_at,
                        "Certificate approved_at",
                    ),
                    certificate.released_by,
                    _optional_datetime_to_text(
                        certificate.released_at,
                        "Certificate released_at",
                    ),
                ),
            )
            for sequence_index, point_id in enumerate(certificate.calculation_summary_ids):
                self._connection.execute(
                    """
                    INSERT INTO certificate_calculation_summaries (
                        certificate_id,
                        sequence_index,
                        point_id
                    )
                    VALUES (?, ?, ?)
                    """,
                    (certificate.certificate_id, sequence_index, point_id),
                )
            for sequence_index, artifact in enumerate(certificate.export_artifacts):
                self._connection.execute(
                    """
                    INSERT INTO export_artifacts (
                        artifact_id,
                        certificate_id,
                        sequence_index,
                        artifact_type,
                        filename,
                        checksum_sha256,
                        storage_uri,
                        generated_by,
                        generated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact.artifact_id,
                        artifact.certificate_id,
                        sequence_index,
                        artifact.artifact_type.value,
                        artifact.filename,
                        artifact.checksum_sha256,
                        artifact.storage_uri,
                        artifact.generated_by,
                        _datetime_to_text(
                            artifact.generated_at,
                            "Export artifact generated_at",
                        ),
                    ),
                )
            self._commit_if_needed()
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not store certificate record.") from error

    def get(self, certificate_id: str) -> CertificateRecord:
        row = self._connection.execute(
            """
            SELECT
                certificate_id,
                job_id,
                certificate_number,
                status,
                software_version,
                calculation_engine_version,
                constant_set_version,
                budget_version,
                template_version,
                approved_by,
                approved_at,
                released_by,
                released_at
            FROM certificates
            WHERE certificate_id = ?
            """,
            (certificate_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"Certificate {certificate_id!r} was not found."
            )
        return _certificate_from_row(
            row,
            self._summary_ids_for_certificate(certificate_id),
            self._artifacts_for_certificate(certificate_id),
        )

    def list_for_job(self, job_id: str) -> tuple[CertificateRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT certificate_id
            FROM certificates
            WHERE job_id = ?
            ORDER BY certificate_number ASC, certificate_id ASC
            """,
            (job_id,),
        ).fetchall()
        return tuple(self.get(row["certificate_id"]) for row in rows)

    def _summary_ids_for_certificate(self, certificate_id: str) -> tuple[str, ...]:
        rows = self._connection.execute(
            """
            SELECT point_id
            FROM certificate_calculation_summaries
            WHERE certificate_id = ?
            ORDER BY sequence_index ASC
            """,
            (certificate_id,),
        ).fetchall()
        return tuple(row["point_id"] for row in rows)

    def _artifacts_for_certificate(
        self,
        certificate_id: str,
    ) -> tuple[ExportArtifact, ...]:
        rows = self._connection.execute(
            """
            SELECT
                artifact_id,
                certificate_id,
                artifact_type,
                filename,
                checksum_sha256,
                storage_uri,
                generated_by,
                generated_at
            FROM export_artifacts
            WHERE certificate_id = ?
            ORDER BY sequence_index ASC
            """,
            (certificate_id,),
        ).fetchall()
        return tuple(_export_artifact_from_row(row) for row in rows)

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


class SQLiteCertificateRevisionRepository:
    """Repository for certificate revision evidence."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self._connection = connection
        self._autocommit = autocommit

    def add(self, revision: CertificateRevision) -> None:
        try:
            self._connection.execute(
                """
                INSERT INTO certificate_revisions (
                    revision_id,
                    original_certificate_id,
                    original_certificate_number,
                    reason,
                    revised_by,
                    revised_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    revision.revision_id,
                    revision.original_certificate_id,
                    revision.original_certificate_number,
                    revision.reason,
                    revision.revised_by,
                    _datetime_to_text(revision.revised_at, "Revision revised_at"),
                ),
            )
            self._commit_if_needed()
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not store certificate revision.") from error

    def get(self, revision_id: str) -> CertificateRevision:
        row = self._connection.execute(
            """
            SELECT
                revision_id,
                original_certificate_id,
                original_certificate_number,
                reason,
                revised_by,
                revised_at
            FROM certificate_revisions
            WHERE revision_id = ?
            """,
            (revision_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"Certificate revision {revision_id!r} was not found."
            )
        return _certificate_revision_from_row(row)

    def list_for_original(
        self,
        original_certificate_id: str,
    ) -> tuple[CertificateRevision, ...]:
        rows = self._connection.execute(
            """
            SELECT
                revision_id,
                original_certificate_id,
                original_certificate_number,
                reason,
                revised_by,
                revised_at
            FROM certificate_revisions
            WHERE original_certificate_id = ?
            ORDER BY revision_id ASC
            """,
            (original_certificate_id,),
        ).fetchall()
        return tuple(_certificate_revision_from_row(row) for row in rows)

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


class SQLiteAuditEventRepository:
    """Append-only repository for audit events."""

    def __init__(self, connection: sqlite3.Connection, *, autocommit: bool = True) -> None:
        connection.row_factory = sqlite3.Row
        self._connection = connection
        self._autocommit = autocommit

    def append(self, event: AuditEvent) -> int:
        try:
            cursor = self._connection.execute(
                """
                INSERT INTO audit_events (
                    entity_type,
                    entity_id,
                    action,
                    user_id,
                    timestamp,
                    previous_value_json,
                    new_value_json,
                    reason,
                    software_version,
                    calculation_engine_version,
                    constant_set_version,
                    budget_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.entity_type,
                    event.entity_id,
                    event.action.value,
                    event.user_id,
                    _datetime_to_text(event.timestamp, "Audit event timestamp"),
                    _mapping_to_json(event.previous_value),
                    _mapping_to_json(event.new_value),
                    event.reason,
                    event.software_version,
                    event.calculation_engine_version,
                    event.constant_set_version,
                    event.budget_version,
                ),
            )
            event_id = int(cursor.lastrowid)
            self._commit_if_needed()
            return event_id
        except sqlite3.DatabaseError as error:
            self._rollback_if_needed()
            raise PersistenceError("Could not append audit event.") from error

    def list_for_entity(self, entity_type: str, entity_id: str) -> tuple[AuditEvent, ...]:
        rows = self._connection.execute(
            """
            SELECT
                entity_type,
                entity_id,
                action,
                user_id,
                timestamp,
                previous_value_json,
                new_value_json,
                reason,
                software_version,
                calculation_engine_version,
                constant_set_version,
                budget_version
            FROM audit_events
            WHERE entity_type = ?
              AND entity_id = ?
            ORDER BY id ASC
            """,
            (entity_type, entity_id),
        ).fetchall()
        return tuple(_audit_event_from_row(row) for row in rows)

    def _commit_if_needed(self) -> None:
        if self._autocommit:
            self._connection.commit()

    def _rollback_if_needed(self) -> None:
        if self._autocommit:
            self._connection.rollback()


def _job_from_row(row: sqlite3.Row) -> CalibrationJob:
    return CalibrationJob(
        id=row["id"],
        client=Client(name=row["client_name"], address=row["client_address"]),
        discipline=Discipline(row["discipline"]),
        measurement_mode=MeasurementMode(row["measurement_mode"]),
        method=row["method"],
        created_by=row["created_by"],
        state=WorkflowState(row["state"]),
        created_at=_datetime_from_text(row["created_at"], "Calibration job created_at"),
    )


def _user_account_from_row(row: sqlite3.Row) -> UserAccount:
    return UserAccount(
        id=row["id"],
        display_name=row["display_name"],
        email=row["email"],
        roles=_roles_from_json(row["roles_json"]),
        active=bool(row["active"]),
        signature_label=row["signature_label"],
        created_at=_datetime_from_text(row["created_at"], "User created_at"),
    )


def _user_session_from_row(row: sqlite3.Row) -> UserSession:
    return UserSession(
        id=row["id"],
        user_id=row["user_id"],
        issued_at=_datetime_from_text(row["issued_at"], "Session issued_at"),
        expires_at=_datetime_from_text(row["expires_at"], "Session expires_at"),
        revoked_at=_optional_datetime_from_text(
            row["revoked_at"],
            "Session revoked_at",
        ),
    )


def _uploaded_file_from_row(row: sqlite3.Row) -> UploadedFile:
    return UploadedFile(
        id=row["id"],
        job_id=row["job_id"],
        original_filename=row["original_filename"],
        checksum_sha256=row["checksum_sha256"],
        file_kind=UploadedFileKind(row["file_kind"]),
        storage_uri=row["storage_uri"],
        parser_version=row["parser_version"],
        uploaded_at=_datetime_from_text(row["uploaded_at"], "Uploaded file uploaded_at"),
    )


def _dut_from_row(row: sqlite3.Row) -> DeviceUnderTest:
    return DeviceUnderTest(
        id=row["id"],
        job_id=row["job_id"],
        make=row["make"],
        model=row["model"],
        serial_number=row["serial_number"],
        channel_id=row["channel_id"],
    )


def _selected_reference_equipment_from_row(
    row: sqlite3.Row,
) -> SelectedReferenceEquipment:
    return SelectedReferenceEquipment(
        job_id=row["job_id"],
        equipment=ReferenceEquipment(
            id=row["equipment_id"],
            simval_id=row["simval_id"],
            equipment_type=row["equipment_type"],
            serial_number=row["serial_number"],
            discipline=Discipline(row["discipline"]),
            calibration_certificate_reference=(
                row["calibration_certificate_reference"]
            ),
            calibration_due_date=_date_from_text(
                row["calibration_due_date"],
                "Reference equipment due date",
            ),
            status=EquipmentStatus(row["status"]),
            usable_range=EquipmentRange(
                minimum=row["range_minimum"],
                maximum=row["range_maximum"],
                unit=row["range_unit"],
            ),
            traceability_statement=row["traceability_statement"],
        ),
        selected_by=row["selected_by"],
        selected_at=_datetime_from_text(
            row["selected_at"],
            "Selected reference equipment timestamp",
        ),
    )


def _required_temperature_setpoint_from_row(
    row: sqlite3.Row,
) -> RequiredTemperatureSetpoint:
    return RequiredTemperatureSetpoint(
        id=row["id"],
        job_id=row["job_id"],
        setpoint=row["setpoint"],
        unit=row["unit"],
        sequence_index=row["sequence_index"],
        created_by=row["created_by"],
        created_at=_datetime_from_text(
            row["created_at"],
            "Required temperature setpoint created_at",
        ),
    )


def _measurement_window_from_row(
    row: sqlite3.Row,
    reading_rows: tuple[sqlite3.Row, ...],
) -> MeasurementWindow:
    return MeasurementWindow(
        id=row["id"],
        job_id=row["job_id"],
        dut_id=row["dut_id"],
        setpoint=row["setpoint"],
        unit=row["unit"],
        selected_by=row["selected_by"],
        selected_at=_datetime_from_text(
            row["selected_at"],
            "Measurement window selected_at",
        ),
        readings=tuple(_reading_from_row(reading_row) for reading_row in reading_rows),
    )


def _reading_from_row(row: sqlite3.Row) -> MeasurementReading:
    return MeasurementReading(
        timestamp=_datetime_from_text(row["timestamp"], "Reading timestamp"),
        channel_id=row["channel_id"],
        value=row["value"],
        unit=row["unit"],
        source=SourceLocation(
            uploaded_file_id=row["uploaded_file_id"],
            source_label=row["source_label"],
            row_number=row["row_number"],
            column_label=row["column_label"],
        ),
        quality_flag=row["quality_flag"],
    )


def _linked_temperature_reading_values(
    *,
    job_id: str,
    sequence_index: int,
    linked_reading: LinkedTemperatureReading,
) -> tuple[object, ...]:
    indication = linked_reading.indication
    reference = linked_reading.reference
    return (
        job_id,
        sequence_index,
        _datetime_to_text(linked_reading.timestamp, "Linked temperature timestamp"),
        linked_reading.dut_channel_id,
        indication.source.uploaded_file_id,
        indication.source.source_label,
        indication.source.row_number,
        indication.source.column_label,
        indication.channel_id,
        indication.value,
        indication.unit,
        indication.quality_flag,
        reference.source.uploaded_file_id,
        reference.source.source_label,
        reference.source.row_number,
        reference.source.column_label,
        reference.channel_id,
        reference.value,
        reference.unit,
        reference.quality_flag,
    )


def _linked_temperature_reading_from_row(
    row: sqlite3.Row,
) -> LinkedTemperatureReading:
    timestamp = _datetime_from_text(
        row["timestamp"],
        "Linked temperature timestamp",
    )
    return LinkedTemperatureReading(
        timestamp=timestamp,
        dut_channel_id=row["dut_channel_id"],
        indication=MeasurementReading(
            timestamp=timestamp,
            channel_id=row["indication_channel_id"],
            value=row["indication_value"],
            unit=row["indication_unit"],
            source=SourceLocation(
                uploaded_file_id=row["indication_uploaded_file_id"],
                source_label=row["indication_source_label"],
                row_number=row["indication_row_number"],
                column_label=row["indication_column_label"],
            ),
            quality_flag=row["indication_quality_flag"],
        ),
        reference=MeasurementReading(
            timestamp=timestamp,
            channel_id=row["reference_channel_id"],
            value=row["reference_value"],
            unit=row["reference_unit"],
            source=SourceLocation(
                uploaded_file_id=row["reference_uploaded_file_id"],
                source_label=row["reference_source_label"],
                row_number=row["reference_row_number"],
                column_label=row["reference_column_label"],
            ),
            quality_flag=row["reference_quality_flag"],
        ),
    )


def _measurement_point_summary_from_row(row: sqlite3.Row) -> MeasurementPointSummary:
    return MeasurementPointSummary(
        point_id=row["point_id"],
        job_id=row["job_id"],
        dut_id=row["dut_id"],
        measurement_window_id=row["measurement_window_id"],
        reference=row["reference"],
        indication=row["indication"],
        unit=row["unit"],
        error_of_indication=row["error_of_indication"],
        calculated_expanded_uncertainty=Decimal(
            row["calculated_expanded_uncertainty"]
        ),
        cmc_floor=Decimal(row["cmc_floor"]),
        reported_expanded_uncertainty=Decimal(
            row["reported_expanded_uncertainty"]
        ),
        display_error_of_indication=Decimal(row["display_error_of_indication"]),
        calculation_engine_version=row["calculation_engine_version"],
        constant_set_version=row["constant_set_version"],
        budget_version=row["budget_version"],
    )


def _constant_set_from_row(row: sqlite3.Row) -> ConstantSet:
    return ConstantSet(
        version=row["version"],
        discipline=Discipline(row["discipline"]),
        status=VersionStatus(row["status"]),
        effective_from=_datetime_from_text(
            row["effective_from"],
            "Constant set effective_from",
        ),
        approved_by=row["approved_by"],
        approved_at=_optional_datetime_from_text(
            row["approved_at"],
            "Constant set approved_at",
        ),
    )


def _uncertainty_budget_from_row(row: sqlite3.Row) -> UncertaintyBudget:
    return UncertaintyBudget(
        version=row["version"],
        budget_type=row["budget_type"],
        method=row["method"],
        discipline=Discipline(row["discipline"]),
        status=VersionStatus(row["status"]),
        linked_constant_set_version=row["linked_constant_set_version"],
        approved_by=row["approved_by"],
        approved_at=_optional_datetime_from_text(
            row["approved_at"],
            "Uncertainty budget approved_at",
        ),
    )


def _certificate_metadata_from_row(row: sqlite3.Row) -> CertificateMetadata:
    return CertificateMetadata(
        job_id=row["job_id"],
        certificate_date=_date_from_text(row["certificate_date"], "Certificate date"),
        calibration_date=_date_from_text(row["calibration_date"], "Calibration date"),
        receipt_date=_date_from_text(row["receipt_date"], "Receipt date"),
        task_number=row["task_number"],
        purchase_order=row["purchase_order"],
        client_name=row["client_name"],
        client_address=row["client_address"],
        procedure=row["procedure"],
        place=row["place"],
        approved_by_label=row["approved_by_label"],
        remarks=row["remarks"],
        traceability_statement=row["traceability_statement"],
        uncertainty_statement=row["uncertainty_statement"],
        ambient_conditions=row["ambient_conditions"],
        temperature_scale=row["temperature_scale"],
        recorded_by=row["recorded_by"],
        recorded_at=_datetime_from_text(row["recorded_at"], "Metadata recorded_at"),
    )


def _certificate_from_row(
    row: sqlite3.Row,
    calculation_summary_ids: tuple[str, ...],
    export_artifacts: tuple[ExportArtifact, ...],
) -> CertificateRecord:
    return CertificateRecord(
        certificate_id=row["certificate_id"],
        job_id=row["job_id"],
        certificate_number=row["certificate_number"],
        status=CertificateStatus(row["status"]),
        calculation_summary_ids=calculation_summary_ids,
        export_artifacts=export_artifacts,
        software_version=row["software_version"],
        calculation_engine_version=row["calculation_engine_version"],
        constant_set_version=row["constant_set_version"],
        budget_version=row["budget_version"],
        template_version=row["template_version"],
        approved_by=row["approved_by"],
        approved_at=_optional_datetime_from_text(
            row["approved_at"],
            "Certificate approved_at",
        ),
        released_by=row["released_by"],
        released_at=_optional_datetime_from_text(
            row["released_at"],
            "Certificate released_at",
        ),
    )


def _export_artifact_from_row(row: sqlite3.Row) -> ExportArtifact:
    return ExportArtifact(
        artifact_id=row["artifact_id"],
        certificate_id=row["certificate_id"],
        artifact_type=ArtifactType(row["artifact_type"]),
        filename=row["filename"],
        checksum_sha256=row["checksum_sha256"],
        storage_uri=row["storage_uri"],
        generated_by=row["generated_by"],
        generated_at=_datetime_from_text(
            row["generated_at"],
            "Export artifact generated_at",
        ),
    )


def _certificate_revision_from_row(row: sqlite3.Row) -> CertificateRevision:
    return CertificateRevision(
        revision_id=row["revision_id"],
        original_certificate_id=row["original_certificate_id"],
        original_certificate_number=row["original_certificate_number"],
        reason=row["reason"],
        revised_by=row["revised_by"],
        revised_at=_datetime_from_text(row["revised_at"], "Revision revised_at"),
    )


def _date_to_text(value: date, field_name: str) -> str:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise PersistenceError(f"{field_name} must be a date.")
    return value.isoformat()


def _date_from_text(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise PersistenceError(f"{field_name} is not a valid ISO date.") from error


def _audit_event_from_row(row: sqlite3.Row) -> AuditEvent:
    return AuditEvent(
        entity_type=row["entity_type"],
        entity_id=row["entity_id"],
        action=AuditAction(row["action"]),
        user_id=row["user_id"],
        timestamp=_datetime_from_text(row["timestamp"], "Audit event timestamp"),
        previous_value=_json_to_mapping(row["previous_value_json"]),
        new_value=_json_to_mapping(row["new_value_json"]),
        reason=row["reason"],
        software_version=row["software_version"],
        calculation_engine_version=row["calculation_engine_version"],
        constant_set_version=row["constant_set_version"],
        budget_version=row["budget_version"],
    )


def _datetime_to_text(value: datetime, field_name: str) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PersistenceError(f"{field_name} must be timezone-aware.")
    return value.isoformat()


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise PersistenceError(f"{field_name} is required.")


def _datetime_from_text(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise PersistenceError(f"{field_name} is not a valid ISO datetime.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PersistenceError(f"{field_name} must be timezone-aware.")
    return parsed


def _optional_datetime_to_text(value: datetime | None, field_name: str) -> str | None:
    if value is None:
        return None
    return _datetime_to_text(value, field_name)


def _optional_datetime_from_text(value: str | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    return _datetime_from_text(value, field_name)


def _mapping_to_json(value: Mapping[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"))


def _json_to_mapping(value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise PersistenceError("Audit event JSON value must be an object.")
    return parsed


def _roles_to_json(roles: tuple[Role, ...]) -> str:
    return json.dumps([role.value for role in roles], separators=(",", ":"))


def _roles_from_json(value: str) -> tuple[Role, ...]:
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise PersistenceError("User roles JSON must be a list.")
    try:
        return tuple(Role(role) for role in parsed)
    except ValueError as error:
        raise PersistenceError("User roles JSON contains an unknown role.") from error
