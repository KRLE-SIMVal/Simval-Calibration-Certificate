"""Generate sanitized runtime-profile evidence for pilot validation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
import argparse

from app.backend.api.settings import ApiSettings
from app.backend.validation.runtime_profile import (
    build_runtime_profile_evidence,
    write_runtime_profile_evidence,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--generated-at")
    args = parser.parse_args(argv)

    evidence = build_runtime_profile_evidence(
        settings=ApiSettings.from_environment(),
        generated_at=_timestamp(args.generated_at),
    )
    write_runtime_profile_evidence(evidence, Path(args.output))
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
