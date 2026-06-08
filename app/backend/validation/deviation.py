"""Quarterly regression deviation evidence model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any


@dataclass(frozen=True, slots=True)
class RegressionDeviation:
    generated_at: str
    title: str
    status: str
    failure_status: str
    objective: str
    test_suite: str
    run_type: str
    trigger_event: str
    quarter: str
    repository: str
    ref: str
    sha: str
    run_id: str
    run_number: str
    run_attempt: str
    run_url: str
    evidence: dict[str, Any] = field(default_factory=dict)
    impact_assessment: str = "Routine use requires QA disposition."
    required_actions: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        evidence_lines = [
            f"- {key}: {value}" for key, value in sorted(self.evidence.items())
        ]
        action_lines = [f"- {action}" for action in self.required_actions]
        return "\n".join(
            [
                f"# {self.title}",
                "",
                "## Summary",
                "",
                f"- Status: {self.status}",
                f"- Failure status: {self.failure_status}",
                f"- Objective: {self.objective}",
                f"- Test suite: {self.test_suite}",
                f"- Quarter: {self.quarter}",
                f"- Repository: {self.repository}",
                f"- Ref: {self.ref}",
                f"- Commit: {self.sha}",
                f"- Run id: {self.run_id}",
                f"- Run number: {self.run_number}",
                f"- Run attempt: {self.run_attempt}",
                f"- Run URL: {self.run_url}",
                "",
                "## Impact Assessment",
                "",
                self.impact_assessment,
                "",
                "## Evidence",
                "",
                *(evidence_lines or ["- No evidence paths were supplied."]),
                "",
                "## Required Actions",
                "",
                *action_lines,
                "",
            ]
        )


def build_regression_deviation(
    *,
    status: str,
    objective: str,
    test_suite: str,
    trigger_event: str,
    repository: str,
    ref: str,
    sha: str,
    run_id: str,
    run_number: str,
    run_attempt: str,
    run_url: str,
    run_started_at: str | datetime,
    evidence: dict[str, Any] | None = None,
    generated_at: str | datetime | None = None,
) -> RegressionDeviation:
    """Build deviation evidence for a failed scheduled quarterly regression."""
    started_at = _coerce_datetime(run_started_at)
    generated = _coerce_datetime(generated_at) if generated_at else datetime.now(timezone.utc)
    quarter = _quarter_label(started_at)
    return RegressionDeviation(
        generated_at=generated.isoformat(),
        title=f"Quarterly Regression Deviation: {quarter}",
        status="open",
        failure_status=status,
        objective=objective,
        test_suite=test_suite,
        run_type=_deviation_run_type(trigger_event, started_at),
        trigger_event=trigger_event,
        quarter=quarter,
        repository=repository,
        ref=ref,
        sha=sha,
        run_id=run_id,
        run_number=run_number,
        run_attempt=run_attempt,
        run_url=run_url,
        evidence=evidence or {},
        required_actions=[
            "Review failed regression evidence.",
            "Assess whether routine use may continue.",
            "Identify affected feature area.",
            "Create or link corrective action if a defect is confirmed.",
            "Add or update regression tests before closure if a defect is confirmed.",
        ],
    )


def write_regression_deviation(
    deviation: RegressionDeviation,
    *,
    json_path: Path,
    markdown_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(deviation.to_json() + "\n", encoding="utf-8")
    markdown_path.write_text(deviation.to_markdown(), encoding="utf-8")


def _deviation_run_type(trigger_event: str, started_at: datetime) -> str:
    if trigger_event == "schedule" and started_at.day == 1 and started_at.month in {
        1,
        4,
        7,
        10,
    }:
        return "quarterly_regression_failure"
    if trigger_event == "schedule":
        return "scheduled_regression_failure"
    return "regression_failure"


def _quarter_label(started_at: datetime) -> str:
    quarter = ((started_at.month - 1) // 3) + 1
    return f"{started_at.year}-Q{quarter}"


def _coerce_datetime(value: str | datetime) -> datetime:
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
