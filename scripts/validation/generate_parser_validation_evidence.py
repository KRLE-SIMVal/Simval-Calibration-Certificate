"""Generate ValProbe parser-validation evidence for pilot review."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
import argparse

from app.backend.validation.parser_validation import (
    build_parser_validation_evidence,
    write_parser_validation_evidence,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parser-version", required=True)
    parser.add_argument("--fixture-manifest", required=True)
    parser.add_argument("--parser-test-report", required=True)
    parser.add_argument("--controlled-fixture-report", required=True)
    parser.add_argument(
        "--controlled-fixtures-enabled",
        choices=["true", "false"],
        required=True,
    )
    parser.add_argument("--reviewer-approved", action="store_true")
    parser.add_argument("--generated-at")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    evidence = build_parser_validation_evidence(
        parser_version=args.parser_version,
        fixture_manifest_path=Path(args.fixture_manifest),
        parser_test_report_path=Path(args.parser_test_report),
        controlled_fixture_report_path=Path(args.controlled_fixture_report),
        controlled_fixtures_enabled=args.controlled_fixtures_enabled == "true",
        reviewer_approved=args.reviewer_approved,
        generated_at=_timestamp(args.generated_at),
    )
    write_parser_validation_evidence(evidence, Path(args.output))
    return 0 if evidence.status == "passed" else 2


def _timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.removesuffix("Z") + "+00:00" if value.endswith("Z") else value
    timestamp = datetime.fromisoformat(normalized)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise SystemExit("--generated-at must be timezone-aware.")
    return timestamp


if __name__ == "__main__":
    raise SystemExit(main())
