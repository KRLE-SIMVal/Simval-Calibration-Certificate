"""Generate human go/no-go approval evidence for production review."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
import argparse

from app.backend.validation.human_approval import (
    build_human_approval_evidence,
    write_human_approval_evidence,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approval-file", required=True)
    parser.add_argument("--software-version", required=True)
    parser.add_argument("--generated-at")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    evidence = build_human_approval_evidence(
        approval_path=Path(args.approval_file),
        software_version=args.software_version,
        generated_at=_timestamp(args.generated_at),
    )
    write_human_approval_evidence(evidence, Path(args.output))
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
