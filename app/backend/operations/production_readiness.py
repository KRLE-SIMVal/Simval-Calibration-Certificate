"""Production readiness evidence report for go-live review."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from app.backend.api.settings import AuthProvider, ApiSettings, RuntimeProfile
from app.backend.domain.entities import Discipline
from app.backend.operations.readiness import RuntimeReadiness


class ProductionReadinessError(ValueError):
    """Raised when production-readiness evidence inputs are incomplete."""


@dataclass(frozen=True, slots=True)
class EvidenceReferenceRecord:
    key: str
    reference: str
    kind: str
    sha256: str | None = None
    size_bytes: int | None = None

    def __post_init__(self) -> None:
        _require_text(self.key, "Evidence reference key")
        _require_text(self.reference, "Evidence reference value")
        if self.kind not in {"file", "directory"}:
            raise ProductionReadinessError("Evidence reference kind is invalid.")
        if self.kind == "file":
            _require_text(self.sha256 or "", "Evidence file SHA-256")
            if self.size_bytes is None or self.size_bytes < 0:
                raise ProductionReadinessError(
                    "Evidence file size must be non-negative."
                )

    def to_payload(self) -> dict:
        payload = {
            "key": self.key,
            "reference": self.reference,
            "kind": self.kind,
        }
        if self.sha256 is not None:
            payload["sha256"] = self.sha256
        if self.size_bytes is not None:
            payload["size_bytes"] = self.size_bytes
        return payload


@dataclass(frozen=True, slots=True)
class ProductionReadinessEvidence:
    live_entra_verified: bool = False
    tls_host_verified: bool = False
    backup_restore_verified: bool = False
    reviewer_independence_verified: bool = False
    valprobe_parser_validated: bool = False
    retention_policy_approved: bool = False
    final_human_approval_recorded: bool = False
    references: Mapping[str, str] | None = None
    reference_manifest: tuple[EvidenceReferenceRecord, ...] = ()
    unavailable_references: tuple[str, ...] = ()
    evidence_content_blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.references is not None:
            for key, value in self.references.items():
                _require_text(key, "Evidence reference key")
                _require_text(value, "Evidence reference value")
        seen_manifest_keys: set[str] = set()
        for record in self.reference_manifest:
            if record.key in seen_manifest_keys:
                raise ProductionReadinessError(
                    "Evidence reference manifest contains duplicate keys."
                )
            seen_manifest_keys.add(record.key)
        for key in self.unavailable_references:
            _require_text(key, "Unavailable evidence reference key")
        for blocker in self.evidence_content_blockers:
            _require_text(blocker, "Evidence content blocker")

    def to_payload(self) -> dict:
        return {
            "live_entra_verified": self.live_entra_verified,
            "tls_host_verified": self.tls_host_verified,
            "backup_restore_verified": self.backup_restore_verified,
            "reviewer_independence_verified": self.reviewer_independence_verified,
            "valprobe_parser_validated": self.valprobe_parser_validated,
            "retention_policy_approved": self.retention_policy_approved,
            "final_human_approval_recorded": self.final_human_approval_recorded,
            "references": dict(self.references or {}),
            "reference_manifest": [
                record.to_payload() for record in self.reference_manifest
            ],
            "unavailable_references": list(self.unavailable_references),
            "evidence_content_blockers": list(self.evidence_content_blockers),
        }


@dataclass(frozen=True, slots=True)
class ProductionReadinessReport:
    status: str
    generated_at: datetime
    software_version: str
    scope: dict
    runtime_readiness: dict
    evidence: ProductionReadinessEvidence
    blockers: tuple[str, ...]

    @property
    def ready_for_go_live_review(self) -> bool:
        return self.status == "ready_for_go_live_review"

    def to_payload(self) -> dict:
        return {
            "status": self.status,
            "generated_at": self.generated_at.isoformat(),
            "software_version": self.software_version,
            "scope": self.scope,
            "runtime_readiness": self.runtime_readiness,
            "evidence": self.evidence.to_payload(),
            "blockers": list(self.blockers),
        }


def build_production_readiness_report(
    *,
    settings: ApiSettings,
    runtime_readiness: RuntimeReadiness,
    evidence: ProductionReadinessEvidence,
    generated_at: datetime,
    software_version: str,
) -> ProductionReadinessReport:
    """Build a deterministic report from runtime status and retained evidence."""
    _require_timezone_aware(generated_at, "Readiness report timestamp")
    _require_text(software_version, "Software version")
    blockers = _blockers(
        settings=settings,
        runtime_readiness=runtime_readiness,
        evidence=evidence,
    )
    status = "ready_for_go_live_review" if len(blockers) == 0 else "blocked"
    return ProductionReadinessReport(
        status=status,
        generated_at=generated_at,
        software_version=software_version,
        scope=_scope_payload(settings),
        runtime_readiness=runtime_readiness.to_payload(),
        evidence=evidence,
        blockers=blockers,
    )


def _blockers(
    *,
    settings: ApiSettings,
    runtime_readiness: RuntimeReadiness,
    evidence: ProductionReadinessEvidence,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if not runtime_readiness.ready:
        blockers.append("runtime_readiness_not_ready")
    if settings.enabled_disciplines != frozenset({Discipline.TEMPERATURE}):
        blockers.append("production_scope_not_temperature_only")
    if settings.runtime_profile is not RuntimeProfile.PRODUCTION:
        blockers.append("runtime_profile_not_production")
    if settings.auth_provider is not AuthProvider.ENTRA_ID_FREE:
        blockers.append("auth_provider_not_entra_id_free")
    if settings.entra_id is None:
        blockers.append("entra_configuration_missing")
    if not evidence.live_entra_verified:
        blockers.append("live_entra_verification_missing")
    if not evidence.tls_host_verified:
        blockers.append("tls_host_verification_missing")
    if not evidence.backup_restore_verified:
        blockers.append("backup_restore_verification_missing")
    if not evidence.reviewer_independence_verified:
        blockers.append("reviewer_independence_evidence_missing")
    if not evidence.valprobe_parser_validated:
        blockers.append("valprobe_parser_validation_missing")
    if not evidence.retention_policy_approved:
        blockers.append("retention_policy_approval_missing")
    if not evidence.final_human_approval_recorded:
        blockers.append("final_human_approval_missing")
    blockers.extend(_evidence_reference_blockers(evidence))
    blockers.extend(
        f"{key}_evidence_reference_unavailable"
        for key in evidence.unavailable_references
    )
    blockers.extend(evidence.evidence_content_blockers)
    return tuple(blockers)


def _evidence_reference_blockers(
    evidence: ProductionReadinessEvidence,
) -> tuple[str, ...]:
    references = evidence.references or {}
    required_when_verified = (
        (evidence.live_entra_verified, "live_entra"),
        (evidence.tls_host_verified, "tls_host"),
        (evidence.backup_restore_verified, "backup_restore"),
        (evidence.reviewer_independence_verified, "reviewer_independence"),
        (evidence.valprobe_parser_validated, "valprobe_parser_validation"),
        (evidence.retention_policy_approved, "retention_policy"),
        (evidence.final_human_approval_recorded, "human_approval"),
    )
    return tuple(
        f"{key}_evidence_reference_missing"
        for verified, key in required_when_verified
        if verified and key not in references
    )


def _scope_payload(settings: ApiSettings) -> dict:
    return {
        "enabled_disciplines": sorted(
            discipline.value for discipline in settings.enabled_disciplines
        ),
        "runtime_profile": settings.runtime_profile.value,
        "auth_provider": settings.auth_provider.value,
        "entra_configured": settings.entra_id is not None,
        "entra_local_session_hours": int(
            settings.entra_session_duration.total_seconds() // 3600
        ),
    }


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise ProductionReadinessError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProductionReadinessError(f"{field_name} must be timezone-aware.")
