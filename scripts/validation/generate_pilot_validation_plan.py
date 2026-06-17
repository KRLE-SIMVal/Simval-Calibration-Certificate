"""Generate a controlled pilot-validation plan."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
import argparse

from app.backend.validation.pilot import (
    build_pilot_validation_plan,
    write_pilot_validation_plan,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-version", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--status", default="draft_pending_review")
    parser.add_argument(
        "--scope",
        default="temperature-only controlled validation pilot",
    )
    parser.add_argument("--generated-at")
    args = parser.parse_args(argv)

    plan = build_pilot_validation_plan(
        release_version=args.release_version,
        status=args.status,
        scope=args.scope,
        generated_at=_timestamp(args.generated_at),
    )
    write_pilot_validation_plan(plan, Path(args.output_dir))
    return 0


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
