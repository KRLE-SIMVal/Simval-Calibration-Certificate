"""Generate production readiness go-live evidence from runtime settings."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json

from app.backend.api.database import sqlite_connection_scope
from app.backend.api.settings import ApiSettings
from app.backend.operations.production_readiness import (
    EvidenceReferenceRecord,
    ProductionReadinessEvidence,
    build_production_readiness_report,
)
from app.backend.operations.readiness import check_runtime_readiness


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--software-version", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--generated-at")
    parser.add_argument("--live-entra-verified", action="store_true")
    parser.add_argument("--tls-host-verified", action="store_true")
    parser.add_argument("--backup-restore-verified", action="store_true")
    parser.add_argument("--reviewer-independence-verified", action="store_true")
    parser.add_argument("--valprobe-parser-validated", action="store_true")
    parser.add_argument("--retention-policy-approved", action="store_true")
    parser.add_argument("--final-human-approval-recorded", action="store_true")
    parser.add_argument("--evidence", action="append", default=[])
    args = parser.parse_args(argv)

    settings = ApiSettings.from_environment()
    runtime_readiness = check_runtime_readiness(
        connection_scope=lambda: sqlite_connection_scope(settings.database_path),
        artifact_directory=settings.artifact_storage_path,
    )
    references = _evidence_references(args.evidence)
    reference_manifest, unavailable_references = _evidence_reference_manifest(
        references,
    )
    evidence_content_blockers = _evidence_content_blockers(
        references=references,
        software_version=args.software_version,
    )
    evidence = ProductionReadinessEvidence(
        live_entra_verified=args.live_entra_verified,
        tls_host_verified=args.tls_host_verified,
        backup_restore_verified=args.backup_restore_verified,
        reviewer_independence_verified=args.reviewer_independence_verified,
        valprobe_parser_validated=args.valprobe_parser_validated,
        retention_policy_approved=args.retention_policy_approved,
        final_human_approval_recorded=args.final_human_approval_recorded,
        references=references,
        reference_manifest=reference_manifest,
        unavailable_references=unavailable_references,
        evidence_content_blockers=evidence_content_blockers,
    )
    report = build_production_readiness_report(
        settings=settings,
        runtime_readiness=runtime_readiness,
        evidence=evidence,
        generated_at=_timestamp(args.generated_at),
        software_version=args.software_version,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if report.ready_for_go_live_review else 2


def _evidence_references(values: list[str]) -> dict[str, str]:
    references = {}
    for item in values:
        key, separator, value = item.partition("=")
        if separator == "" or key.strip() == "" or value.strip() == "":
            raise SystemExit(f"Invalid evidence entry: {item}")
        references[key] = value
    return references


def _evidence_reference_manifest(
    references: dict[str, str],
) -> tuple[tuple[EvidenceReferenceRecord, ...], tuple[str, ...]]:
    records: list[EvidenceReferenceRecord] = []
    unavailable: list[str] = []
    for key, reference in sorted(references.items()):
        path = Path(reference)
        if not path.exists():
            unavailable.append(key)
            continue
        if path.is_file():
            records.append(
                EvidenceReferenceRecord(
                    key=key,
                    reference=reference,
                    kind="file",
                    sha256=_sha256(path),
                    size_bytes=path.stat().st_size,
                )
            )
            continue
        if path.is_dir():
            records.append(
                EvidenceReferenceRecord(
                    key=key,
                    reference=reference,
                    kind="directory",
                )
            )
            continue
        unavailable.append(key)
    return tuple(records), tuple(unavailable)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _evidence_content_blockers(
    *,
    references: dict[str, str],
    software_version: str,
) -> tuple[str, ...]:
    blockers: list[str] = []
    smoke_reference = references.get("smoke_evidence")
    if smoke_reference is None:
        blockers.append("production_smoke_evidence_missing")
    else:
        blockers.extend(
            _smoke_evidence_content_blockers(
                smoke_reference=smoke_reference,
                software_version=software_version,
            )
        )
    blockers.extend(
        _passed_status_evidence_blockers(
            references=references,
            evidence_keys=(
                "backup_restore",
                "reviewer_independence",
                "valprobe_parser_validation",
                "retention_policy",
                "human_approval",
                "live_entra",
                "tls_host",
            ),
        )
    )
    return tuple(blockers)


def _smoke_evidence_content_blockers(
    *,
    smoke_reference: str,
    software_version: str,
) -> tuple[str, ...]:
    blockers: list[str] = []
    smoke_path = Path(smoke_reference)
    payload = _json_evidence_payload(smoke_path)
    if payload is None:
        return ("production_smoke_evidence_invalid",)
    if _contains_sensitive_smoke_detail(payload):
        blockers.append("production_smoke_evidence_exposes_sensitive_detail")
    if payload.get("status") != "passed":
        blockers.append("production_smoke_failed")
    if payload.get("software_version") != software_version:
        blockers.append("production_smoke_software_version_mismatch")
    scope = payload.get("scope")
    if not isinstance(scope, dict) or scope.get("enabled_disciplines") != [
        "temperature"
    ]:
        blockers.append("production_smoke_scope_not_temperature_only")
    endpoints = payload.get("endpoints")
    if not isinstance(endpoints, list):
        blockers.append("production_smoke_endpoint_failure")
    else:
        endpoint_status = {
            endpoint.get("path"): endpoint.get("ok")
            for endpoint in endpoints
            if isinstance(endpoint, dict)
        }
        expected_paths = {"/health", "/readiness", "/app", "/app/workflow"}
        if endpoint_status.keys() != expected_paths or not all(
            endpoint_status[path] is True for path in expected_paths
        ):
            blockers.append("production_smoke_endpoint_failure")
    return tuple(blockers)


def _passed_status_evidence_blockers(
    *,
    references: dict[str, str],
    evidence_keys: tuple[str, ...],
) -> tuple[str, ...]:
    blockers: list[str] = []
    for key in evidence_keys:
        reference = references.get(key)
        if reference is None:
            continue
        payload = _json_evidence_payload(Path(reference))
        if payload is None:
            blockers.append(f"{key}_evidence_invalid")
            continue
        if payload.get("status") != "passed":
            blockers.append(f"{key}_evidence_not_passed")
    return tuple(blockers)


def _json_evidence_payload(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _contains_sensitive_smoke_detail(payload: dict) -> bool:
    serialized = json.dumps(payload, sort_keys=True).lower()
    forbidden_markers = (
        "simval_database_path",
        "simval_artifact_storage_path",
        "password",
        "secret",
        "bearer ",
        ".sqlite",
        "c:\\",
    )
    return any(marker in serialized for marker in forbidden_markers)


def _timestamp(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    normalized = value.removesuffix("Z") + "+00:00" if value.endswith("Z") else value
    timestamp = datetime.fromisoformat(normalized)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise SystemExit("--generated-at must be timezone-aware.")
    return timestamp


if __name__ == "__main__":
    raise SystemExit(main())
