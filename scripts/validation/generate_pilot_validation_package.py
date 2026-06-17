"""Generate a pilot validation package from required pilot evidence files."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import argparse

from app.backend.validation.package import (
    build_validation_package,
    write_validation_package,
)
from app.backend.validation.pilot import pilot_evidence_paths_by_stage


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-version", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source-commit")
    parser.add_argument("--pilot-plan", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--known-limitation", action="append", default=[])
    args = parser.parse_args(argv)

    references = _evidence_references(args.evidence)
    paths_by_stage = pilot_evidence_paths_by_stage(references)
    package = build_validation_package(
        status="draft_pending_review",
        release_version=args.release_version,
        objective="Controlled pilot validation package",
        source_commit=args.source_commit,
        iq_paths=(Path(args.pilot_plan), *paths_by_stage["IQ"]),
        oq_paths=paths_by_stage["OQ"],
        pq_paths=paths_by_stage["PQ"],
        known_limitations=(
            "Routine production remains blocked until the production readiness report has no blockers.",
            *tuple(args.known_limitation),
        ),
    )
    write_validation_package(package, Path(args.output_dir))
    return 0


def _evidence_references(values: list[str]) -> dict[str, Path]:
    references: dict[str, Path] = {}
    for item in values:
        key, separator, value = item.partition("=")
        if separator == "" or key.strip() == "" or value.strip() == "":
            raise SystemExit(f"Invalid evidence entry: {item}")
        references[key] = Path(value)
    return references


if __name__ == "__main__":
    raise SystemExit(main())
