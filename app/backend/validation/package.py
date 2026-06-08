"""Validation package generation for production-readiness review."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import subprocess


@dataclass(frozen=True, slots=True)
class ValidationEvidenceFile:
    path: str
    purpose: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ValidationPackage:
    generated_at: str
    status: str
    package_type: str
    release_version: str
    source_commit: str
    objective: str
    iq_evidence: tuple[ValidationEvidenceFile, ...] = field(default_factory=tuple)
    oq_evidence: tuple[ValidationEvidenceFile, ...] = field(default_factory=tuple)
    pq_evidence: tuple[ValidationEvidenceFile, ...] = field(default_factory=tuple)
    known_limitations: tuple[str, ...] = field(default_factory=tuple)
    required_reviewers: tuple[str, ...] = field(default_factory=tuple)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        return "\n".join(
            [
                "# SIMVal Validation Package",
                "",
                f"- Status: {self.status}",
                f"- Package type: {self.package_type}",
                f"- Release version: {self.release_version}",
                f"- Source commit: {self.source_commit}",
                f"- Objective: {self.objective}",
                "",
                "## IQ Evidence",
                "",
                *_evidence_markdown(self.iq_evidence),
                "",
                "## OQ Evidence",
                "",
                *_evidence_markdown(self.oq_evidence),
                "",
                "## PQ Evidence",
                "",
                *_evidence_markdown(self.pq_evidence),
                "",
                "## Known Limitations",
                "",
                *[f"- {limitation}" for limitation in self.known_limitations],
                "",
                "## Required Reviewers",
                "",
                *[f"- {reviewer}" for reviewer in self.required_reviewers],
                "",
            ]
        )

    def reviewer_disposition_template(self) -> str:
        return "\n".join(
            [
                "# Reviewer Disposition",
                "",
                f"- Release version: {self.release_version}",
                f"- Source commit: {self.source_commit}",
                "- Decision: pending",
                "- Reviewer name:",
                "- Reviewer role:",
                "- Review date:",
                "",
                "## Required Checks",
                "",
                "- Validation package reviewed.",
                "- Automated regression evidence reviewed.",
                "- Known limitations accepted or rejected.",
                "- Routine-use impact assessed.",
                "- Follow-up actions recorded.",
                "",
                "## Disposition",
                "",
                "Pending human QA/laboratory approval.",
                "",
            ]
        )


def build_validation_package(
    *,
    status: str,
    release_version: str,
    objective: str,
    iq_paths: tuple[Path, ...],
    oq_paths: tuple[Path, ...],
    pq_paths: tuple[Path, ...],
    known_limitations: tuple[str, ...],
    required_reviewers: tuple[str, ...] = (
        "Laboratory Chief",
        "QA/Compliance Reviewer",
        "Metrology Reviewer",
    ),
    generated_at: datetime | None = None,
    source_commit: str | None = None,
) -> ValidationPackage:
    generated = generated_at or datetime.now(timezone.utc)
    return ValidationPackage(
        generated_at=generated.isoformat(),
        status=status,
        package_type="iq_oq_pq_equivalent",
        release_version=release_version,
        source_commit=source_commit or _git_commit(),
        objective=objective,
        iq_evidence=tuple(
            _evidence_file(path, "Installation qualification evidence")
            for path in iq_paths
        ),
        oq_evidence=tuple(
            _evidence_file(path, "Operational qualification evidence")
            for path in oq_paths
        ),
        pq_evidence=tuple(
            _evidence_file(path, "Performance qualification evidence")
            for path in pq_paths
        ),
        known_limitations=known_limitations,
        required_reviewers=required_reviewers,
    )


def write_validation_package(package: ValidationPackage, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "validation-package.json").write_text(
        package.to_json() + "\n",
        encoding="utf-8",
    )
    (output_dir / "validation-package.md").write_text(
        package.to_markdown(),
        encoding="utf-8",
    )
    (output_dir / "reviewer-disposition.md").write_text(
        package.reviewer_disposition_template(),
        encoding="utf-8",
    )


def _evidence_file(path: Path, purpose: str) -> ValidationEvidenceFile:
    if not path.is_file():
        raise FileNotFoundError(f"Validation evidence file does not exist: {path}")
    return ValidationEvidenceFile(
        path=path.as_posix(),
        purpose=purpose,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def _evidence_markdown(
    evidence_files: tuple[ValidationEvidenceFile, ...],
) -> tuple[str, ...]:
    if not evidence_files:
        return ("- No evidence files supplied.",)
    return tuple(
        f"- {item.path} | {item.purpose} | SHA-256 {item.sha256}"
        for item in evidence_files
    )


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return "unknown"
    return result.stdout.strip() or "unknown"
