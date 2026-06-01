"""Generate a validation evidence report for automated test runs."""

from __future__ import annotations

from pathlib import Path
import argparse

from app.backend.validation.report import (
    build_validation_report,
    write_validation_report,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", required=True)
    parser.add_argument("--objective", required=True)
    parser.add_argument("--test-suite", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    args = parser.parse_args()

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
    )
    write_validation_report(report, Path(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

