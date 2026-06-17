"""Pressure certificate template approval evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
from typing import Any


class PressureTemplateApprovalEvidenceError(ValueError):
    """Raised when pressure template approval evidence is incomplete."""


REQUIRED_APPROVAL_ROLES: tuple[str, ...] = (
    "qa_laboratory_reviewer",
    "laboratory_chief",
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class PressureTemplateApprovalEvidenceFile:
    key: str
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class PressureTemplateApprovalRoleRecord:
    role: str
    decision: str | None
    approved_at: str | None
    actor_digest: str | None


@dataclass(frozen=True, slots=True)
class PressureTemplateApprovalEvidence:
    generated_at: str
    status: str
    blockers: tuple[str, ...]
    template_version: str
    approval_template_version: str | None
    discipline: str | None
    certificate_artifact_sha256_present: bool
    certificate_artifact_reviewed: bool
    method_specific_statements_reviewed: bool
    danak_mark_scope_reviewed: bool
    ab11_reporting_reviewed: bool
    reviewer_roles: tuple[PressureTemplateApprovalRoleRecord, ...]
    evidence_files: tuple[PressureTemplateApprovalEvidenceFile, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def build_pressure_template_approval_evidence(
    *,
    approval_path: Path,
    template_version: str,
    generated_at: datetime | None = None,
) -> PressureTemplateApprovalEvidence:
    """Build sanitized evidence from a controlled pressure-template approval."""
    _require_text(template_version, "Template version")
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise PressureTemplateApprovalEvidenceError(
            "Pressure template approval evidence timestamp must be timezone-aware."
        )

    payload = _json_file(approval_path)
    approval_template_version = payload.get("template_version")
    discipline = payload.get("discipline")
    artifact_sha256 = payload.get("certificate_artifact_sha256")
    artifact_sha256_present = (
        isinstance(artifact_sha256, str)
        and _SHA256_PATTERN.fullmatch(artifact_sha256.lower()) is not None
    )
    certificate_artifact_reviewed = payload.get("certificate_artifact_reviewed") is True
    method_statements_reviewed = (
        payload.get("method_specific_statements_reviewed") is True
    )
    danak_scope_reviewed = payload.get("danak_mark_scope_reviewed") is True
    ab11_reporting_reviewed = payload.get("ab11_reporting_reviewed") is True
    reviewer_roles = tuple(
        _role_record(payload, role) for role in REQUIRED_APPROVAL_ROLES
    )
    blockers = _blockers(
        template_version=template_version,
        approval_template_version=approval_template_version,
        discipline=discipline,
        artifact_sha256_present=artifact_sha256_present,
        certificate_artifact_reviewed=certificate_artifact_reviewed,
        method_statements_reviewed=method_statements_reviewed,
        danak_scope_reviewed=danak_scope_reviewed,
        ab11_reporting_reviewed=ab11_reporting_reviewed,
        reviewer_roles=reviewer_roles,
    )
    return PressureTemplateApprovalEvidence(
        generated_at=generated.astimezone(timezone.utc).isoformat(),
        status="passed" if len(blockers) == 0 else "blocked",
        blockers=blockers,
        template_version=template_version,
        approval_template_version=(
            approval_template_version
            if isinstance(approval_template_version, str)
            else None
        ),
        discipline=discipline if isinstance(discipline, str) else None,
        certificate_artifact_sha256_present=artifact_sha256_present,
        certificate_artifact_reviewed=certificate_artifact_reviewed,
        method_specific_statements_reviewed=method_statements_reviewed,
        danak_mark_scope_reviewed=danak_scope_reviewed,
        ab11_reporting_reviewed=ab11_reporting_reviewed,
        reviewer_roles=reviewer_roles,
        evidence_files=(
            _evidence_file("pressure_template_approval", approval_path),
        ),
    )


def write_pressure_template_approval_evidence(
    evidence: PressureTemplateApprovalEvidence,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(evidence.to_json() + "\n", encoding="utf-8")


def _blockers(
    *,
    template_version: str,
    approval_template_version: Any,
    discipline: Any,
    artifact_sha256_present: bool,
    certificate_artifact_reviewed: bool,
    method_statements_reviewed: bool,
    danak_scope_reviewed: bool,
    ab11_reporting_reviewed: bool,
    reviewer_roles: tuple[PressureTemplateApprovalRoleRecord, ...],
) -> tuple[str, ...]:
    blockers: list[str] = []
    if approval_template_version != template_version:
        blockers.append("pressure_template_version_mismatch")
    if discipline != "pressure":
        blockers.append("pressure_template_discipline_not_pressure")
    if not artifact_sha256_present:
        blockers.append("pressure_template_artifact_reference_missing")
    if not certificate_artifact_reviewed:
        blockers.append("pressure_template_artifact_not_reviewed")
    if not method_statements_reviewed:
        blockers.append("pressure_template_method_statements_not_reviewed")
    if not danak_scope_reviewed:
        blockers.append("pressure_template_danak_scope_not_reviewed")
    if not ab11_reporting_reviewed:
        blockers.append("pressure_template_ab11_reporting_not_reviewed")
    if any(record.decision is None for record in reviewer_roles):
        blockers.append("pressure_template_required_role_missing")
    if any(
        record.decision != "approve"
        or record.actor_digest is None
        or not _valid_timestamp_text(record.approved_at)
        for record in reviewer_roles
    ):
        blockers.append("pressure_template_required_role_not_approved")
    return tuple(dict.fromkeys(blockers))


def _role_record(
    approval_payload: dict[str, Any],
    role: str,
) -> PressureTemplateApprovalRoleRecord:
    approvals = approval_payload.get("approvals")
    role_payload = approvals.get(role) if isinstance(approvals, dict) else None
    if not isinstance(role_payload, dict):
        return PressureTemplateApprovalRoleRecord(
            role=role,
            decision=None,
            approved_at=None,
            actor_digest=None,
        )
    actor_identifier = role_payload.get("actor_identifier")
    return PressureTemplateApprovalRoleRecord(
        role=role,
        decision=(
            role_payload.get("decision")
            if isinstance(role_payload.get("decision"), str)
            else None
        ),
        approved_at=(
            role_payload.get("approved_at")
            if isinstance(role_payload.get("approved_at"), str)
            else None
        ),
        actor_digest=(
            _digest_actor(actor_identifier)
            if isinstance(actor_identifier, str) and actor_identifier.strip() != ""
            else None
        ),
    )


def _valid_timestamp_text(value: str | None) -> bool:
    if value is None:
        return False
    try:
        normalized = (
            value.removesuffix("Z") + "+00:00" if value.endswith("Z") else value
        )
        timestamp = datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return timestamp.tzinfo is not None and timestamp.utcoffset() is not None


def _json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PressureTemplateApprovalEvidenceError(
            "Pressure template approval file does not exist."
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PressureTemplateApprovalEvidenceError(
            "Pressure template approval file is not valid JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise PressureTemplateApprovalEvidenceError(
            "Pressure template approval file must contain a JSON object."
        )
    return payload


def _digest_actor(actor: str) -> str:
    return hashlib.sha256(actor.strip().encode("utf-8")).hexdigest()


def _evidence_file(
    key: str,
    path: Path,
) -> PressureTemplateApprovalEvidenceFile:
    resolved_path = path.resolve()
    return PressureTemplateApprovalEvidenceFile(
        key=key,
        path=path.name,
        sha256=_sha256(resolved_path),
        size_bytes=resolved_path.stat().st_size,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise PressureTemplateApprovalEvidenceError(f"{field_name} is required.")
