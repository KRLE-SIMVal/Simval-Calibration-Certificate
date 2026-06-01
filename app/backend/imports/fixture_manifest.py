"""Controlled fixture manifest helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json


@dataclass(frozen=True, slots=True)
class FixtureRecord:
    fixture_id: str
    path: Path
    sha256: str
    intended_use: str
    confidentiality: str
    allowed_in_ci: bool


def load_manifest(path: Path) -> list[FixtureRecord]:
    """Load controlled fixture metadata from JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    records: list[FixtureRecord] = []
    for item in data["fixtures"]:
        records.append(
            FixtureRecord(
                fixture_id=item["fixture_id"],
                path=Path(item["path"]),
                sha256=item["sha256"],
                intended_use=item["intended_use"],
                confidentiality=item["confidentiality"],
                allowed_in_ci=bool(item["allowed_in_ci"]),
            )
        )
    return records


def sha256_file(path: Path) -> str:
    """Return SHA-256 hash for path."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()

