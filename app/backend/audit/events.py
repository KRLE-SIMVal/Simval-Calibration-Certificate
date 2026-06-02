"""Append-only audit event model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


class AuditAction(StrEnum):
    JOB_CREATED = "job_created"
    METADATA_CHANGED = "metadata_changed"
    FILE_UPLOADED = "file_uploaded"
    PARSER_RESULT_RECORDED = "parser_result_recorded"
    IMPORT_ALIGNMENT_RECORDED = "import_alignment_recorded"
    MANUAL_READING_CHANGED = "manual_reading_changed"
    MEASUREMENT_WINDOW_CHANGED = "measurement_window_changed"
    CALCULATION_RUN = "calculation_run"
    CONSTANT_SET_CHANGED = "constant_set_changed"
    BUDGET_CHANGED = "budget_changed"
    TECHNICAL_REVIEW_APPROVED = "technical_review_approved"
    QA_APPROVED = "qa_approved"
    CERTIFICATE_PREVIEW_GENERATED = "certificate_preview_generated"
    CERTIFICATE_RELEASED = "certificate_released"
    CERTIFICATE_REVISED = "certificate_revised"
    CERTIFICATE_VOIDED = "certificate_voided"
    EXPORT_ARTIFACT_GENERATED = "export_artifact_generated"
    USER_ACCOUNT_CREATED = "user_account_created"
    USER_ACCOUNT_ROLES_CHANGED = "user_account_roles_changed"
    USER_ACCOUNT_DEACTIVATED = "user_account_deactivated"
    USER_SESSION_REVOKED = "user_session_revoked"
    WORKFLOW_TRANSITIONED = "workflow_transitioned"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    entity_type: str
    entity_id: str
    action: AuditAction
    user_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    previous_value: Mapping[str, Any] | None = None
    new_value: Mapping[str, Any] | None = None
    reason: str | None = None
    software_version: str | None = None
    calculation_engine_version: str | None = None
    constant_set_version: str | None = None
    budget_version: str | None = None

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("AuditEvent timestamp must be timezone-aware.")
        if self.reason is not None and self.reason.strip() == "":
            raise ValueError("AuditEvent reason cannot be blank.")
        if self.previous_value is not None:
            object.__setattr__(
                self, "previous_value", MappingProxyType(dict(self.previous_value))
            )
        if self.new_value is not None:
            object.__setattr__(self, "new_value", MappingProxyType(dict(self.new_value)))
