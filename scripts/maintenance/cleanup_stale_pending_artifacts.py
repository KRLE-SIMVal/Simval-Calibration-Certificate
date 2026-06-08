"""Remove stale staged certificate artifact files."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import json
from collections.abc import Sequence

from app.backend.certificates.storage import cleanup_stale_pending_artifacts


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--older-than-minutes", type=int, required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    if args.older_than_minutes < 1:
        raise SystemExit("--older-than-minutes must be at least 1")
    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=args.older_than_minutes,
    )
    result = cleanup_stale_pending_artifacts(
        base_path=Path(args.artifact_dir),
        cutoff=cutoff,
    )
    payload = {
        "artifact_dir": result.base_path.as_posix(),
        "cutoff": result.cutoff.isoformat(),
        "removed_count": result.removed_count,
        "removed_files": [path.as_posix() for path in result.removed_files],
    }
    output = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
