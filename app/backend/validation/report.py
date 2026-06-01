"""Validation evidence report model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import json
import platform
import subprocess
from typing import Any


@dataclass(frozen=True, slots=True)
class ValidationReport:
    generated_at: str
    status: str
    objective: str
    commit: str
    python_version: str
    test_suite: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def build_validation_report(
    *,
    status: str,
    objective: str,
    test_suite: str,
    evidence: dict[str, Any] | None = None,
) -> ValidationReport:
    """Build a deterministic validation report payload."""
    return ValidationReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        objective=objective,
        commit=_git_commit(),
        python_version=platform.python_version(),
        test_suite=test_suite,
        evidence=evidence or {},
    )


def write_validation_report(report: ValidationReport, path: Path) -> None:
    """Write validation report JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.to_json() + "\n", encoding="utf-8")


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

