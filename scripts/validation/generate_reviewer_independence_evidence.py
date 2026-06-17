"""Generate reviewer-independence evidence for pilot review."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
import argparse

from app.backend.validation.reviewer_independence import (
    build_reviewer_independence_evidence,
    write_reviewer_independence_evidence,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow-evidence", required=True)
    parser.add_argument("--operator-user", required=True)
    parser.add_argument("--technical-reviewer-user", required=True)
    parser.add_argument("--qa-approver-user", required=True)
    parser.add_argument("--release-user", required=True)
    parser.add_argument("--blocked-same-user-attempts", type=int, required=True)
    parser.add_argument("--controlled-deviation-approved", action="store_true")
    parser.add_argument("--reviewer-approved", action="store_true")
    parser.add_argument("--generated-at")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    evidence = build_reviewer_independence_evidence(
        workflow_evidence_path=Path(args.workflow_evidence),
        operator_user=args.operator_user,
        technical_reviewer_user=args.technical_reviewer_user,
        qa_approver_user=args.qa_approver_user,
        release_user=args.release_user,
        blocked_same_user_attempts=args.blocked_same_user_attempts,
        controlled_deviation_approved=args.controlled_deviation_approved,
        reviewer_approved=args.reviewer_approved,
        generated_at=_timestamp(args.generated_at),
    )
    write_reviewer_independence_evidence(evidence, Path(args.output))
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
