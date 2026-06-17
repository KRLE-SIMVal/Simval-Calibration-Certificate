"""Retention-policy validation evidence for controlled production go-live."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
from typing import Any


class RetentionPolicyEvidenceError(ValueError):
    """Raised when retention-policy evidence inputs are incomplete."""


REQUIRED_RETENTION_CATEGORIES: tuple[str, ...] = (
    "certificates",
    "raw_source_files",
    "validation_packages",
    "audit_events",
    "database_backups",
    "generated_artifacts",
)

REQUIRED_CATEGORY_FIELDS: tuple[str, ...] = (
    "retention_period",
    "owner_role",
    "storage_location_type",
)


@dataclass(frozen=True, slots=True)
class RetentionPolicyEvidenceFile:
    key: str
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class RetentionCategoryCoverage:
    category: str
    present: bool
    required_fields_present: tuple[str, ...]
    missing_required_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetentionPolicyEvidence:
    generated_at: str
    status: str
    blockers: tuple[str, ...]
    required_categories: tuple[str, ...]
    missing_categories: tuple[str, ...]
    incomplete_categories: tuple[str, ...]
    reviewer_approved: bool
    category_coverage: tuple[RetentionCategoryCoverage, ...]
    evidence_files: tuple[RetentionPolicyEvidenceFile, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def build_retention_policy_evidence(
    *,
    policy_path: Path,
    reviewer_approved: bool = False,
    generated_at: datetime | None = None,
) -> RetentionPolicyEvidence:
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise RetentionPolicyEvidenceError(
            "Retention-policy evidence timestamp must be timezone-aware."
        )
    policy_payload = _json_file(policy_path)
    coverage = tuple(
        _category_coverage(policy_payload, category)
        for category in REQUIRED_RETENTION_CATEGORIES
    )
    missing_categories = tuple(
        item.category for item in coverage if not item.present
    )
    incomplete_categories = tuple(
        item.category
        for item in coverage
        if item.present and len(item.missing_required_fields) > 0
    )
    blockers = _blockers(
        missing_categories=missing_categories,
        incomplete_categories=incomplete_categories,
        reviewer_approved=reviewer_approved,
    )
    return RetentionPolicyEvidence(
        generated_at=generated.astimezone(timezone.utc).isoformat(),
        status="passed" if len(blockers) == 0 else "blocked",
        blockers=blockers,
        required_categories=REQUIRED_RETENTION_CATEGORIES,
        missing_categories=missing_categories,
        incomplete_categories=incomplete_categories,
        reviewer_approved=reviewer_approved,
        category_coverage=coverage,
        evidence_files=(_evidence_file("retention_policy", policy_path),),
    )


def write_retention_policy_evidence(
    evidence: RetentionPolicyEvidence,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(evidence.to_json() + "\n", encoding="utf-8")


def _category_coverage(
    policy_payload: dict[str, Any],
    category: str,
) -> RetentionCategoryCoverage:
    category_payload = policy_payload.get(category)
    if not isinstance(category_payload, dict):
        return RetentionCategoryCoverage(
            category=category,
            present=False,
            required_fields_present=(),
            missing_required_fields=REQUIRED_CATEGORY_FIELDS,
        )
    present_fields = tuple(
        field
        for field in REQUIRED_CATEGORY_FIELDS
        if _nonblank_text(category_payload.get(field))
    )
    missing_fields = tuple(
        field for field in REQUIRED_CATEGORY_FIELDS if field not in present_fields
    )
    return RetentionCategoryCoverage(
        category=category,
        present=True,
        required_fields_present=present_fields,
        missing_required_fields=missing_fields,
    )


def _blockers(
    *,
    missing_categories: tuple[str, ...],
    incomplete_categories: tuple[str, ...],
    reviewer_approved: bool,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if len(missing_categories) > 0:
        blockers.append("retention_policy_required_categories_missing")
    if len(incomplete_categories) > 0:
        blockers.append("retention_policy_required_categories_incomplete")
    if not reviewer_approved:
        blockers.append("retention_policy_reviewer_approval_missing")
    return tuple(blockers)


def _json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RetentionPolicyEvidenceError("Retention-policy file does not exist.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RetentionPolicyEvidenceError(
            "Retention-policy file is not valid JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise RetentionPolicyEvidenceError(
            "Retention-policy file must contain a JSON object."
        )
    return payload


def _nonblank_text(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _evidence_file(key: str, path: Path) -> RetentionPolicyEvidenceFile:
    resolved_path = path.resolve()
    return RetentionPolicyEvidenceFile(
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
