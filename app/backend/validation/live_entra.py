"""Live Entra authentication evidence for controlled production go-live."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
from typing import Any


class LiveEntraEvidenceError(ValueError):
    """Raised when live Entra evidence inputs are incomplete."""


@dataclass(frozen=True, slots=True)
class LiveEntraEvidenceFile:
    key: str
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class LiveEntraEvidence:
    generated_at: str
    status: str
    blockers: tuple[str, ...]
    provider: str | None
    tenant_id_verified: bool
    client_id_verified: bool
    audience_verified: bool
    session_exchange_status: str | None
    get_me_status: str | None
    user_session_created_audit_event_retained: bool
    local_role_mapping_reviewed: bool
    reviewer_approved: bool
    evidence_files: tuple[LiveEntraEvidenceFile, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def build_live_entra_evidence(
    *,
    auth_evidence_path: Path,
    reviewer_approved: bool = False,
    generated_at: datetime | None = None,
) -> LiveEntraEvidence:
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise LiveEntraEvidenceError(
            "Live Entra evidence timestamp must be timezone-aware."
        )
    payload = _json_file(auth_evidence_path)
    provider = payload.get("provider")
    tenant_id_verified = payload.get("tenant_id_verified") is True
    client_id_verified = payload.get("client_id_verified") is True
    audience_verified = payload.get("audience_verified") is True
    session_exchange_status = payload.get("session_exchange_status")
    get_me_status = payload.get("get_me_status")
    user_session_audit = (
        payload.get("user_session_created_audit_event_retained") is True
    )
    role_mapping_reviewed = payload.get("local_role_mapping_reviewed") is True
    blockers = _blockers(
        provider=provider,
        tenant_id_verified=tenant_id_verified,
        client_id_verified=client_id_verified,
        audience_verified=audience_verified,
        session_exchange_status=session_exchange_status,
        get_me_status=get_me_status,
        user_session_audit=user_session_audit,
        role_mapping_reviewed=role_mapping_reviewed,
        reviewer_approved=reviewer_approved,
    )
    return LiveEntraEvidence(
        generated_at=generated.astimezone(timezone.utc).isoformat(),
        status="passed" if len(blockers) == 0 else "blocked",
        blockers=blockers,
        provider=provider if isinstance(provider, str) else None,
        tenant_id_verified=tenant_id_verified,
        client_id_verified=client_id_verified,
        audience_verified=audience_verified,
        session_exchange_status=(
            session_exchange_status if isinstance(session_exchange_status, str) else None
        ),
        get_me_status=get_me_status if isinstance(get_me_status, str) else None,
        user_session_created_audit_event_retained=user_session_audit,
        local_role_mapping_reviewed=role_mapping_reviewed,
        reviewer_approved=reviewer_approved,
        evidence_files=(_evidence_file("live_entra", auth_evidence_path),),
    )


def write_live_entra_evidence(
    evidence: LiveEntraEvidence,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(evidence.to_json() + "\n", encoding="utf-8")


def _blockers(
    *,
    provider: Any,
    tenant_id_verified: bool,
    client_id_verified: bool,
    audience_verified: bool,
    session_exchange_status: Any,
    get_me_status: Any,
    user_session_audit: bool,
    role_mapping_reviewed: bool,
    reviewer_approved: bool,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if provider != "entra_id_free":
        blockers.append("live_entra_provider_not_approved")
    if not tenant_id_verified:
        blockers.append("live_entra_tenant_not_verified")
    if not client_id_verified:
        blockers.append("live_entra_client_not_verified")
    if not audience_verified:
        blockers.append("live_entra_audience_not_verified")
    if session_exchange_status != "passed":
        blockers.append("live_entra_session_exchange_not_passed")
    if get_me_status != "passed":
        blockers.append("live_entra_get_me_not_passed")
    if not user_session_audit:
        blockers.append("live_entra_session_audit_event_missing")
    if not role_mapping_reviewed:
        blockers.append("live_entra_role_mapping_review_missing")
    if not reviewer_approved:
        blockers.append("live_entra_reviewer_approval_missing")
    return tuple(blockers)


def _json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise LiveEntraEvidenceError("Live Entra evidence file does not exist.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LiveEntraEvidenceError(
            "Live Entra evidence file is not valid JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise LiveEntraEvidenceError(
            "Live Entra evidence file must contain a JSON object."
        )
    return payload


def _evidence_file(key: str, path: Path) -> LiveEntraEvidenceFile:
    resolved_path = path.resolve()
    return LiveEntraEvidenceFile(
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
