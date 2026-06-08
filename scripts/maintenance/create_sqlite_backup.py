"""Create a controlled SQLite backup with JSON evidence."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json

from app.backend.operations.backup import create_sqlite_backup


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-path", required=True)
    parser.add_argument("--backup-dir", required=True)
    parser.add_argument("--evidence-output")
    args = parser.parse_args(argv)

    evidence = create_sqlite_backup(
        source_database_path=Path(args.database_path),
        backup_directory=Path(args.backup_dir),
        created_at=datetime.now(timezone.utc),
    )
    payload = json.dumps(evidence.to_payload(), indent=2, sort_keys=True) + "\n"
    if args.evidence_output:
        output_path = Path(args.evidence_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

