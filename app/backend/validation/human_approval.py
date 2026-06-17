"""Human go/no-go approval evidence for controlled production go-live."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
from typing import Any


class HumanApprovalEvidenceError(ValueError):
    """Raised when human approval evidence inputs are incomplete."""


REQUIRED_APPROVAL_ROLES: tuple[str, ...] = (
    "system_owner",
    "qa_laboratory_reviewer",
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class HumanApprovalEvidenceFile:
    key: str
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class HumanApprovalRoleRecord:
    role: str
    decision: str | None
    approved_at: str | None
    actor_digest: str | None


@dataclass(frozen=True, slots=True)
class HumanApprovalEvidence:
    generated_at: str
    status: str
    blockers: tuple[str, ...]
    software_version: str
    approval_software_version: str | None
    evidence_pack_reviewed: bool
    readiness_report_sha256_present: bool
    remaining_deviation_count: int
    reviewer_roles: tuple[HumanApprovalRoleRecord, ...]
    evidence_files: tuple[HumanApprovalEvidenceFile, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def build_human_approval_evidence(
    *,
    approval_path: Path,
    software_version: str,
    generated_at: datetime | None = None,
) -> HumanApprovalEvidence:
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise HumanApprovalEvidenceError(
            "Human approval evidence timestamp must be timezone-aware."
        )
    if software_version.strip() == "":
        raise HumanApprovalEvidenceError("Software version is required.")

    approval_payload = _json_file(approval_path)
    approval_software_version = approval_payload.get("software_version")
    evidence_pack_reviewed = approval_payload.get("evidence_pack_reviewed") is True
    readiness_report_sha256 = approval_payload.get("readiness_report_sha256")
    readiness_report_sha256_present = (
        isinstance(readiness_report_sha256, str)
        and _SHA256_PATTERN.fullmatch(readiness_report_sha256.lower()) is not None
    )
    reviewer_roles = tuple(
        _role_record(approval_payload, role) for role in REQUIRED_APPROVAL_ROLES
    )
    remaining_deviations = _remaining_deviations(approval_payload)
    blockers = _blockers(
        software_version=software_version.strip(),
        approval_software_version=approval_software_version,
        evidence_pack_reviewed=evidence_pack_reviewed,
        readiness_report_sha256_present=readiness_report_sha256_present,
        reviewer_roles=reviewer_roles,
        remaining_deviations=remaining_deviations,
    )
    return HumanApprovalEvidence(
        generated_at=generated.astimezone(timezone.utc).isoformat(),
        status="passed" if len(blockers) == 0 else "blocked",
        blockers=blockers,
        software_version=software_version.strip(),
        approval_software_version=(
            approval_software_version
            if isinstance(approval_software_version, str)
            else None
        ),
        evidence_pack_reviewed=evidence_pack_reviewed,
        readiness_report_sha256_present=readiness_report_sha256_present,
        remaining_deviation_count=len(remaining_deviations),
        reviewer_roles=reviewer_roles,
        evidence_files=(_evidence_file("human_approval", approval_path),),
    )


def write_human_approval_evidence(
    evidence: HumanApprovalEvidence,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(evidence.to_json() + "\n", encoding="utf-8")


def _role_record(
    approval_payload: dict[str, Any],
    role: str,
) -> HumanApprovalRoleRecord:
    approvals = approval_payload.get("approvals")
    role_payload = approvals.get(role) if isinstance(approvals, dict) else None
    if not isinstance(role_payload, dict):
        return HumanApprovalRoleRecord(
            role=role,
            decision=None,
            approved_at=None,
            actor_digest=None,
        )
    actor_identifier = role_payload.get("actor_identifier")
    return HumanApprovalRoleRecord(
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


def _remaining_deviations(
    approval_payload: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    deviations = approval_payload.get("remaining_deviations", [])
    if not isinstance(deviations, list):
        return ({"invalid": True},)
    records: list[dict[str, Any]] = []
    for item in deviations:
        if isinstance(item, dict):
            records.append(item)
        else:
            records.append({"invalid": True})
    return tuple(records)


def _blockers(
    *,
    software_version: str,
    approval_software_version: Any,
    evidence_pack_reviewed: bool,
    readiness_report_sha256_present: bool,
    reviewer_roles: tuple[HumanApprovalRoleRecord, ...],
    remaining_deviations: tuple[dict[str, Any], ...],
) -> tuple[str, ...]:
    blockers: list[str] = []
    if approval_software_version != software_version:
        blockers.append("human_approval_software_version_mismatch")
    if not evidence_pack_reviewed:
        blockers.append("human_approval_evidence_pack_not_reviewed")
    if not readiness_report_sha256_present:
        blockers.append("human_approval_readiness_report_reference_missing")
    if any(record.decision is None for record in reviewer_roles):
        blockers.append("human_approval_required_role_missing")
    if any(
        record.decision != "approve"
        or record.actor_digest is None
        or not _valid_timestamp_text(record.approved_at)
        for record in reviewer_roles
    ):
        blockers.append("human_approval_required_role_not_approved")
    if any(
        deviation.get("disposition") != "accepted_for_go_live"
        for deviation in remaining_deviations
    ):
        blockers.append("human_approval_open_deviations_unaccepted")
    return tuple(dict.fromkeys(blockers))


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
        raise HumanApprovalEvidenceError("Human approval file does not exist.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HumanApprovalEvidenceError(
            "Human approval file is not valid JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise HumanApprovalEvidenceError(
            "Human approval file must contain a JSON object."
        )
    return payload


def _digest_actor(actor: str) -> str:
    return hashlib.sha256(actor.strip().encode("utf-8")).hexdigest()


def _evidence_file(key: str, path: Path) -> HumanApprovalEvidenceFile:
    resolved_path = path.resolve()
    return HumanApprovalEvidenceFile(
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
