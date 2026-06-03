"""Validation evidence report model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import platform
import subprocess
from typing import Any


@dataclass(frozen=True, slots=True)
class ValidationReport:
    generated_at: str
    status: str
    objective: str
    run_type: str
    trigger_event: str
    quarter: str
    commit: str
    python_version: str
    test_suite: str
    ci: dict[str, str] = field(default_factory=dict)
    environment: dict[str, str] = field(default_factory=dict)
    controlled_fixture_policy: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def build_validation_report(
    *,
    status: str,
    objective: str,
    test_suite: str,
    evidence: dict[str, Any] | None = None,
    trigger_event: str = "local",
    run_id: str | None = None,
    run_number: str | None = None,
    run_attempt: str | None = None,
    actor: str | None = None,
    repository: str | None = None,
    ref: str | None = None,
    sha: str | None = None,
    run_started_at: str | datetime | None = None,
    controlled_fixtures_enabled: bool | None = None,
) -> ValidationReport:
    """Build a deterministic validation report payload."""
    generated_at = datetime.now(timezone.utc)
    started_at = _coerce_datetime(run_started_at) or generated_at
    return ValidationReport(
        generated_at=generated_at.isoformat(),
        status=status,
        objective=objective,
        run_type=_classify_run_type(trigger_event, started_at),
        trigger_event=trigger_event,
        quarter=_quarter_label(started_at),
        commit=_git_commit(),
        python_version=platform.python_version(),
        test_suite=test_suite,
        ci=_ci_metadata(
            run_id=run_id,
            run_number=run_number,
            run_attempt=run_attempt,
            actor=actor,
            repository=repository,
            ref=ref,
            sha=sha,
        ),
        environment=_environment_metadata(),
        controlled_fixture_policy=_controlled_fixture_policy(
            controlled_fixtures_enabled
        ),
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


def _coerce_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    normalized = value
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _classify_run_type(trigger_event: str, started_at: datetime) -> str:
    if trigger_event == "schedule":
        if started_at.day == 1 and started_at.month in {1, 4, 7, 10}:
            return "quarterly_regression"
        return "scheduled_regression"
    if trigger_event in {"push", "pull_request"}:
        return "change_regression"
    if trigger_event == "workflow_dispatch":
        return "manual_regression"
    return "local_regression"


def _quarter_label(started_at: datetime) -> str:
    quarter = ((started_at.month - 1) // 3) + 1
    return f"{started_at.year}-Q{quarter}"


def _ci_metadata(
    *,
    run_id: str | None,
    run_number: str | None,
    run_attempt: str | None,
    actor: str | None,
    repository: str | None,
    ref: str | None,
    sha: str | None,
) -> dict[str, str]:
    values = {
        "run_id": run_id,
        "run_number": run_number,
        "run_attempt": run_attempt,
        "actor": actor,
        "repository": repository,
        "ref": ref,
        "sha": sha,
    }
    return {key: value for key, value in values.items() if value}


def _environment_metadata() -> dict[str, str]:
    return {
        "platform": platform.platform(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
    }


def _controlled_fixture_policy(
    controlled_fixtures_enabled: bool | None,
) -> dict[str, Any]:
    enabled = (
        os.environ.get("SIMVAL_RUN_CONTROLLED_FIXTURE_TESTS") == "1"
        if controlled_fixtures_enabled is None
        else controlled_fixtures_enabled
    )
    return {
        "enabled": enabled,
        "enable_environment_variable": "SIMVAL_RUN_CONTROLLED_FIXTURE_TESTS=1",
        "default_ci_policy": "disabled",
        "reason": (
            "Controlled internal confidential fixtures are not approved "
            "for default CI execution."
        ),
    }
