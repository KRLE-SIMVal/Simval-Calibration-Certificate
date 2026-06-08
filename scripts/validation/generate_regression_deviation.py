"""Generate deviation evidence for a failed scheduled regression run."""

from __future__ import annotations

from pathlib import Path
import argparse
from collections.abc import Sequence

from app.backend.validation.deviation import (
    build_regression_deviation,
    write_regression_deviation,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", required=True)
    parser.add_argument("--objective", required=True)
    parser.add_argument("--test-suite", required=True)
    parser.add_argument("--trigger-event", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-number", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--run-started-at", required=True)
    parser.add_argument("--json-output", required=True)
    parser.add_argument("--markdown-output", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    args = parser.parse_args(argv)

    evidence = {}
    for item in args.evidence:
        key, _, value = item.partition("=")
        if not key or not value:
            raise SystemExit(f"Invalid evidence entry: {item}")
        evidence[key] = value

    deviation = build_regression_deviation(
        status=args.status,
        objective=args.objective,
        test_suite=args.test_suite,
        trigger_event=args.trigger_event,
        repository=args.repository,
        ref=args.ref,
        sha=args.sha,
        run_id=args.run_id,
        run_number=args.run_number,
        run_attempt=args.run_attempt,
        run_url=args.run_url,
        run_started_at=args.run_started_at,
        evidence=evidence,
    )
    write_regression_deviation(
        deviation,
        json_path=Path(args.json_output),
        markdown_path=Path(args.markdown_output),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
