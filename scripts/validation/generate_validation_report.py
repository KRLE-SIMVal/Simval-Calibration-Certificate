"""Generate a validation evidence report for automated test runs."""

from __future__ import annotations

from pathlib import Path
import argparse
import os
from collections.abc import Sequence

from app.backend.validation.report import (
    build_validation_report,
    write_validation_report,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", required=True)
    parser.add_argument("--objective", required=True)
    parser.add_argument("--test-suite", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument(
        "--trigger-event", default=os.environ.get("GITHUB_EVENT_NAME", "local")
    )
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID"))
    parser.add_argument("--run-number", default=os.environ.get("GITHUB_RUN_NUMBER"))
    parser.add_argument("--run-attempt", default=os.environ.get("GITHUB_RUN_ATTEMPT"))
    parser.add_argument("--actor", default=os.environ.get("GITHUB_ACTOR"))
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--ref", default=os.environ.get("GITHUB_REF"))
    parser.add_argument("--sha", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--run-started-at")
    parser.add_argument(
        "--controlled-fixtures-enabled",
        choices=["true", "false"],
        default=None,
    )
    args = parser.parse_args(argv)

    evidence = {}
    for item in args.evidence:
        key, _, value = item.partition("=")
        if not key or not value:
            raise SystemExit(f"Invalid evidence entry: {item}")
        evidence[key] = value

    report = build_validation_report(
        status=args.status,
        objective=args.objective,
        test_suite=args.test_suite,
        evidence=evidence,
        trigger_event=args.trigger_event,
        run_id=args.run_id,
        run_number=args.run_number,
        run_attempt=args.run_attempt,
        actor=args.actor,
        repository=args.repository,
        ref=args.ref,
        sha=args.sha,
        run_started_at=args.run_started_at,
        controlled_fixtures_enabled=_parse_optional_bool(
            args.controlled_fixtures_enabled
        ),
    )
    write_validation_report(report, Path(args.output))
    return 0


def _parse_optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value == "true"


if __name__ == "__main__":
    raise SystemExit(main())
