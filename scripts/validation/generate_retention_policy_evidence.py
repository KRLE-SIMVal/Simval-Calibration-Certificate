"""Generate retention-policy evidence for production go-live review."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
import argparse

from app.backend.validation.retention_policy import (
    build_retention_policy_evidence,
    write_retention_policy_evidence,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy-file", required=True)
    parser.add_argument("--reviewer-approved", action="store_true")
    parser.add_argument("--generated-at")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    evidence = build_retention_policy_evidence(
        policy_path=Path(args.policy_file),
        reviewer_approved=args.reviewer_approved,
        generated_at=_timestamp(args.generated_at),
    )
    write_retention_policy_evidence(evidence, Path(args.output))
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
