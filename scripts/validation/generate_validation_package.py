"""Generate a SIMVal validation package from retained evidence files."""

from __future__ import annotations

from pathlib import Path
import argparse
from collections.abc import Sequence

from app.backend.validation.package import (
    build_validation_package,
    write_validation_package,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", required=True)
    parser.add_argument("--release-version", required=True)
    parser.add_argument("--objective", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source-commit")
    parser.add_argument("--iq", action="append", default=[])
    parser.add_argument("--oq", action="append", default=[])
    parser.add_argument("--pq", action="append", default=[])
    parser.add_argument("--known-limitation", action="append", default=[])
    args = parser.parse_args(argv)

    package = build_validation_package(
        status=args.status,
        release_version=args.release_version,
        objective=args.objective,
        iq_paths=tuple(Path(path) for path in args.iq),
        oq_paths=tuple(Path(path) for path in args.oq),
        pq_paths=tuple(Path(path) for path in args.pq),
        known_limitations=tuple(args.known_limitation),
        source_commit=args.source_commit,
    )
    write_validation_package(package, Path(args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
