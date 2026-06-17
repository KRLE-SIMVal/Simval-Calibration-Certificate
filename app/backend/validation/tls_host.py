"""TLS and host-boundary evidence for controlled production go-live."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
from typing import Any


class TlsHostEvidenceError(ValueError):
    """Raised when TLS/host evidence inputs are incomplete."""


@dataclass(frozen=True, slots=True)
class TlsHostEvidenceFile:
    key: str
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class TlsHostEvidence:
    generated_at: str
    status: str
    blockers: tuple[str, ...]
    https_endpoint_verified: bool
    approved_hostname_verified: bool
    tls_certificate_valid: bool
    direct_api_exposure_reviewed: bool
    direct_unauthenticated_api_exposure_blocked: bool
    reviewer_approved: bool
    evidence_files: tuple[TlsHostEvidenceFile, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def build_tls_host_evidence(
    *,
    host_evidence_path: Path,
    reviewer_approved: bool = False,
    generated_at: datetime | None = None,
) -> TlsHostEvidence:
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise TlsHostEvidenceError(
            "TLS/host evidence timestamp must be timezone-aware."
        )
    payload = _json_file(host_evidence_path)
    https_endpoint_verified = payload.get("https_endpoint_verified") is True
    approved_hostname_verified = payload.get("approved_hostname_verified") is True
    tls_certificate_valid = payload.get("tls_certificate_valid") is True
    direct_api_reviewed = payload.get("direct_api_exposure_reviewed") is True
    direct_api_blocked = (
        payload.get("direct_unauthenticated_api_exposure_blocked") is True
    )
    blockers = _blockers(
        https_endpoint_verified=https_endpoint_verified,
        approved_hostname_verified=approved_hostname_verified,
        tls_certificate_valid=tls_certificate_valid,
        direct_api_reviewed=direct_api_reviewed,
        direct_api_blocked=direct_api_blocked,
        reviewer_approved=reviewer_approved,
    )
    return TlsHostEvidence(
        generated_at=generated.astimezone(timezone.utc).isoformat(),
        status="passed" if len(blockers) == 0 else "blocked",
        blockers=blockers,
        https_endpoint_verified=https_endpoint_verified,
        approved_hostname_verified=approved_hostname_verified,
        tls_certificate_valid=tls_certificate_valid,
        direct_api_exposure_reviewed=direct_api_reviewed,
        direct_unauthenticated_api_exposure_blocked=direct_api_blocked,
        reviewer_approved=reviewer_approved,
        evidence_files=(_evidence_file("tls_host", host_evidence_path),),
    )


def write_tls_host_evidence(
    evidence: TlsHostEvidence,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(evidence.to_json() + "\n", encoding="utf-8")


def _blockers(
    *,
    https_endpoint_verified: bool,
    approved_hostname_verified: bool,
    tls_certificate_valid: bool,
    direct_api_reviewed: bool,
    direct_api_blocked: bool,
    reviewer_approved: bool,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if not https_endpoint_verified:
        blockers.append("tls_host_https_endpoint_not_verified")
    if not approved_hostname_verified:
        blockers.append("tls_host_approved_hostname_not_verified")
    if not tls_certificate_valid:
        blockers.append("tls_host_certificate_not_valid")
    if not direct_api_reviewed:
        blockers.append("tls_host_direct_api_exposure_not_reviewed")
    if not direct_api_blocked:
        blockers.append("tls_host_direct_unauthenticated_api_not_blocked")
    if not reviewer_approved:
        blockers.append("tls_host_reviewer_approval_missing")
    return tuple(blockers)


def _json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise TlsHostEvidenceError("TLS/host evidence file does not exist.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TlsHostEvidenceError(
            "TLS/host evidence file is not valid JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise TlsHostEvidenceError(
            "TLS/host evidence file must contain a JSON object."
        )
    return payload


def _evidence_file(key: str, path: Path) -> TlsHostEvidenceFile:
    resolved_path = path.resolve()
    return TlsHostEvidenceFile(
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
