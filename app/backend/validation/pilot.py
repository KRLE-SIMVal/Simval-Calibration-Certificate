"""Controlled pilot-validation plan generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from collections.abc import Mapping
from pathlib import Path
import json


class PilotValidationPlanError(ValueError):
    """Raised when pilot-validation plan inputs are incomplete."""


@dataclass(frozen=True, slots=True)
class PilotValidationActivity:
    activity_id: str
    stage: str
    title: str
    owner_role: str
    required_evidence_key: str
    acceptance_criterion: str
    stop_condition: str

    def __post_init__(self) -> None:
        _require_text(self.activity_id, "Activity id")
        if self.stage not in {"IQ", "OQ", "PQ"}:
            raise PilotValidationPlanError("Pilot activity stage must be IQ, OQ, or PQ.")
        _require_text(self.title, "Activity title")
        _require_text(self.owner_role, "Activity owner role")
        _require_text(self.required_evidence_key, "Activity evidence key")
        _require_text(self.acceptance_criterion, "Activity acceptance criterion")
        _require_text(self.stop_condition, "Activity stop condition")


@dataclass(frozen=True, slots=True)
class PilotValidationPlan:
    generated_at: str
    release_version: str
    scope: str
    status: str
    activities: tuple[PilotValidationActivity, ...]
    required_reviewers: tuple[str, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        return "\n".join(
            [
                "# SIMVal Controlled Pilot Validation Plan",
                "",
                f"- Status: {self.status}",
                f"- Release version: {self.release_version}",
                f"- Scope: {self.scope}",
                f"- Generated at: {self.generated_at}",
                "",
                "## Activities",
                "",
                "| ID | Stage | Activity | Owner | Evidence key | Acceptance criterion | Stop condition |",
                "|---|---|---|---|---|---|---|",
                *[
                    (
                        f"| {activity.activity_id} | {activity.stage} | "
                        f"{activity.title} | {activity.owner_role} | "
                        f"`{activity.required_evidence_key}` | "
                        f"{activity.acceptance_criterion} | "
                        f"{activity.stop_condition} |"
                    )
                    for activity in self.activities
                ],
                "",
                "## Required Reviewers",
                "",
                *[f"- {reviewer}" for reviewer in self.required_reviewers],
                "",
                "## Pilot Rule",
                "",
                (
                    "Routine production use remains blocked until all activities "
                    "are accepted, unresolved deviations are dispositioned, and the "
                    "production readiness report has no blockers."
                ),
                "",
            ]
        )


def build_pilot_validation_plan(
    *,
    release_version: str,
    generated_at: datetime | None = None,
    status: str = "draft_pending_review",
    scope: str = "temperature-only controlled validation pilot",
    required_reviewers: tuple[str, ...] = (
        "Laboratory Chief",
        "QA/Compliance Reviewer",
        "Metrology Reviewer",
        "Security/GDPR Reviewer",
    ),
) -> PilotValidationPlan:
    _require_text(release_version, "Release version")
    _require_text(status, "Pilot validation status")
    _require_text(scope, "Pilot validation scope")
    if len(required_reviewers) == 0:
        raise PilotValidationPlanError("At least one required reviewer is required.")
    for reviewer in required_reviewers:
        _require_text(reviewer, "Required reviewer")
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise PilotValidationPlanError("Pilot validation timestamp must be timezone-aware.")
    return PilotValidationPlan(
        generated_at=generated.astimezone(timezone.utc).isoformat(),
        release_version=release_version,
        scope=scope,
        status=status,
        activities=_default_activities(),
        required_reviewers=required_reviewers,
    )


def write_pilot_validation_plan(plan: PilotValidationPlan, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "pilot-validation-plan.json").write_text(
        plan.to_json() + "\n",
        encoding="utf-8",
    )
    (output_dir / "pilot-validation-plan.md").write_text(
        plan.to_markdown(),
        encoding="utf-8",
    )


def pilot_evidence_paths_by_stage(
    evidence_references: Mapping[str, Path],
) -> dict[str, tuple[Path, ...]]:
    """Map required pilot evidence keys to validation-package IQ/OQ/PQ paths."""
    paths_by_stage: dict[str, list[Path]] = {"IQ": [], "OQ": [], "PQ": []}
    for activity in _default_activities():
        evidence_path = evidence_references.get(activity.required_evidence_key)
        if evidence_path is None:
            raise PilotValidationPlanError(
                f"Pilot evidence reference is required: {activity.required_evidence_key}"
            )
        paths_by_stage[activity.stage].append(evidence_path)
    return {
        stage: tuple(paths)
        for stage, paths in paths_by_stage.items()
    }


def required_pilot_evidence_keys() -> tuple[str, ...]:
    return tuple(
        activity.required_evidence_key for activity in _default_activities()
    )


def _default_activities() -> tuple[PilotValidationActivity, ...]:
    return (
        PilotValidationActivity(
            activity_id="PILOT-IQ-001",
            stage="IQ",
            title="Controlled host and runtime configuration verified",
            owner_role="Security/GDPR Reviewer",
            required_evidence_key="runtime_profile",
            acceptance_criterion=(
                "Approved host uses production profile, Entra provider, "
                "temperature-only scope, and controlled artifact/database paths."
            ),
            stop_condition=(
                "Runtime profile, authentication provider, or production scope "
                "does not match the approved configuration."
            ),
        ),
        PilotValidationActivity(
            activity_id="PILOT-OQ-001",
            stage="OQ",
            title="Automated regression and smoke evidence retained",
            owner_role="Test Engineer",
            required_evidence_key="smoke_evidence",
            acceptance_criterion=(
                "Full regression passes and smoke evidence confirms health, "
                "readiness, app shell, and workflow endpoints for the same version."
            ),
            stop_condition="Regression or smoke evidence fails or is version-mismatched.",
        ),
        PilotValidationActivity(
            activity_id="PILOT-OQ-002",
            stage="OQ",
            title="ValProbe parser validation evidence reviewed",
            owner_role="Metrology Reviewer",
            required_evidence_key="valprobe_parser_validation",
            acceptance_criterion=(
                "Approved fixture set covers supported workbook variants, "
                "malformed/unsafe rejection cases, and raw-file traceability."
            ),
            stop_condition=(
                "Parser fixture coverage is incomplete or not approved for routine use."
            ),
        ),
        PilotValidationActivity(
            activity_id="PILOT-PQ-001",
            stage="PQ",
            title="End-to-end certificate workflow run with independent reviewers",
            owner_role="Laboratory Chief",
            required_evidence_key="reviewer_independence",
            acceptance_criterion=(
                "Pilot job shows independent operator, technical reviewer, QA "
                "approver, release actor, certificate preview, and released artifact."
            ),
            stop_condition=(
                "Any regulated transition is performed by the same user without "
                "approved deviation."
            ),
        ),
        PilotValidationActivity(
            activity_id="PILOT-PQ-002",
            stage="PQ",
            title="Backup and restore drill completed from pilot database",
            owner_role="QA/Compliance Reviewer",
            required_evidence_key="backup_restore",
            acceptance_criterion=(
                "Backup and separate-path restore both pass SQLite integrity "
                "verification with retained checksums."
            ),
            stop_condition="Backup, restore, checksum, or integrity evidence fails.",
        ),
    )


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise PilotValidationPlanError(f"{field_name} is required.")
