"""ValProbe parser-validation evidence for controlled pilot use."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json


class ParserValidationEvidenceError(ValueError):
    """Raised when parser-validation evidence inputs are incomplete."""


@dataclass(frozen=True, slots=True)
class ParserValidationEvidenceFile:
    key: str
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ParserValidationEvidence:
    generated_at: str
    status: str
    blockers: tuple[str, ...]
    parser_version: str
    controlled_fixtures_enabled: bool
    reviewer_approved: bool
    evidence_files: tuple[ParserValidationEvidenceFile, ...]
    required_coverage: tuple[str, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def build_parser_validation_evidence(
    *,
    parser_version: str,
    fixture_manifest_path: Path,
    parser_test_report_path: Path,
    controlled_fixture_report_path: Path,
    controlled_fixtures_enabled: bool,
    reviewer_approved: bool = False,
    generated_at: datetime | None = None,
) -> ParserValidationEvidence:
    _require_text(parser_version, "Parser version")
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise ParserValidationEvidenceError(
            "Parser-validation evidence timestamp must be timezone-aware."
        )
    evidence_files = (
        _evidence_file("fixture_manifest", fixture_manifest_path),
        _evidence_file("parser_test_report", parser_test_report_path),
        _evidence_file("controlled_fixture_report", controlled_fixture_report_path),
    )
    blockers = _blockers(
        controlled_fixtures_enabled=controlled_fixtures_enabled,
        reviewer_approved=reviewer_approved,
    )
    return ParserValidationEvidence(
        generated_at=generated.astimezone(timezone.utc).isoformat(),
        status="passed" if len(blockers) == 0 else "blocked",
        blockers=blockers,
        parser_version=parser_version,
        controlled_fixtures_enabled=controlled_fixtures_enabled,
        reviewer_approved=reviewer_approved,
        evidence_files=evidence_files,
        required_coverage=(
            "approved_controlled_valprobe_workbook_fixture",
            "sanitized_workbook_parsing",
            "missing_temperature_sheet_rejection",
            "nonnumeric_measurement_warning",
            "unsafe_xml_declaration_rejection",
            "malformed_xml_rejection",
            "raw_upload_traceability",
        ),
    )


def write_parser_validation_evidence(
    evidence: ParserValidationEvidence,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(evidence.to_json() + "\n", encoding="utf-8")


def _blockers(
    *,
    controlled_fixtures_enabled: bool,
    reviewer_approved: bool,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if not controlled_fixtures_enabled:
        blockers.append("controlled_fixture_execution_missing")
    if not reviewer_approved:
        blockers.append("parser_validation_reviewer_approval_missing")
    return tuple(blockers)


def _evidence_file(key: str, path: Path) -> ParserValidationEvidenceFile:
    if key.strip() == "":
        raise ParserValidationEvidenceError("Parser evidence key is required.")
    resolved_path = path.resolve()
    if not resolved_path.is_file():
        raise ParserValidationEvidenceError(
            f"Parser validation evidence file does not exist: {path}"
        )
    return ParserValidationEvidenceFile(
        key=key,
        path=path.as_posix(),
        sha256=_sha256(resolved_path),
        size_bytes=resolved_path.stat().st_size,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise ParserValidationEvidenceError(f"{field_name} is required.")
