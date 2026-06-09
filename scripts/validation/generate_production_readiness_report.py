"""Generate production readiness go-live evidence from runtime settings."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json

from app.backend.api.database import sqlite_connection_scope
from app.backend.api.settings import ApiSettings
from app.backend.operations.production_readiness import (
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
    parser.add_argument("--retention-policy-approved", action="store_true")
    parser.add_argument("--final-human-approval-recorded", action="store_true")
    parser.add_argument("--evidence", action="append", default=[])
    args = parser.parse_args(argv)

    settings = ApiSettings.from_environment()
    runtime_readiness = check_runtime_readiness(
        connection_scope=lambda: sqlite_connection_scope(settings.database_path),
        artifact_directory=settings.artifact_storage_path,
    )
    evidence = ProductionReadinessEvidence(
        live_entra_verified=args.live_entra_verified,
        tls_host_verified=args.tls_host_verified,
        backup_restore_verified=args.backup_restore_verified,
        reviewer_independence_verified=args.reviewer_independence_verified,
        retention_policy_approved=args.retention_policy_approved,
        final_human_approval_recorded=args.final_human_approval_recorded,
        references=_evidence_references(args.evidence),
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
