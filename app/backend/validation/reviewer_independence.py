"""Reviewer-independence validation evidence for controlled pilot use."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json


class ReviewerIndependenceEvidenceError(ValueError):
    """Raised when reviewer-independence evidence inputs are incomplete."""


@dataclass(frozen=True, slots=True)
class ReviewerIndependenceEvidenceFile:
    key: str
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ReviewerIndependenceEvidence:
    generated_at: str
    status: str
    blockers: tuple[str, ...]
    role_actor_digests: dict[str, str]
    distinct_actor_count: int
    blocked_same_user_attempts: int
    controlled_deviation_approved: bool
    reviewer_approved: bool
    evidence_files: tuple[ReviewerIndependenceEvidenceFile, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def build_reviewer_independence_evidence(
    *,
    workflow_evidence_path: Path,
    operator_user: str,
    technical_reviewer_user: str,
    qa_approver_user: str,
    release_user: str,
    blocked_same_user_attempts: int,
    controlled_deviation_approved: bool = False,
    reviewer_approved: bool = False,
    generated_at: datetime | None = None,
) -> ReviewerIndependenceEvidence:
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise ReviewerIndependenceEvidenceError(
            "Reviewer-independence evidence timestamp must be timezone-aware."
        )
    role_actors = {
        "operator": _required_text(operator_user, "Operator user"),
        "technical_reviewer": _required_text(
            technical_reviewer_user,
            "Technical reviewer user",
        ),
        "qa_approver": _required_text(qa_approver_user, "QA approver user"),
        "release_actor": _required_text(release_user, "Release user"),
    }
    if blocked_same_user_attempts < 0:
        raise ReviewerIndependenceEvidenceError(
            "Blocked same-user attempts must be non-negative."
        )
    distinct_actor_count = len(set(role_actors.values()))
    blockers = _blockers(
        distinct_actor_count=distinct_actor_count,
        blocked_same_user_attempts=blocked_same_user_attempts,
        controlled_deviation_approved=controlled_deviation_approved,
        reviewer_approved=reviewer_approved,
    )
    return ReviewerIndependenceEvidence(
        generated_at=generated.astimezone(timezone.utc).isoformat(),
        status="passed" if len(blockers) == 0 else "blocked",
        blockers=blockers,
        role_actor_digests={
            role: _digest_actor(actor) for role, actor in sorted(role_actors.items())
        },
        distinct_actor_count=distinct_actor_count,
        blocked_same_user_attempts=blocked_same_user_attempts,
        controlled_deviation_approved=controlled_deviation_approved,
        reviewer_approved=reviewer_approved,
        evidence_files=(
            _evidence_file("workflow_evidence", workflow_evidence_path),
        ),
    )


def write_reviewer_independence_evidence(
    evidence: ReviewerIndependenceEvidence,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(evidence.to_json() + "\n", encoding="utf-8")


def _blockers(
    *,
    distinct_actor_count: int,
    blocked_same_user_attempts: int,
    controlled_deviation_approved: bool,
    reviewer_approved: bool,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if distinct_actor_count < 4:
        blockers.append("regulated_roles_not_independent")
    if blocked_same_user_attempts == 0 and not controlled_deviation_approved:
        blockers.append("same_user_block_evidence_missing")
    if not reviewer_approved:
        blockers.append("reviewer_independence_approval_missing")
    return tuple(blockers)


def _evidence_file(key: str, path: Path) -> ReviewerIndependenceEvidenceFile:
    resolved_path = path.resolve()
    if not resolved_path.is_file():
        raise ReviewerIndependenceEvidenceError(
            f"Reviewer-independence evidence file does not exist: {path}"
        )
    return ReviewerIndependenceEvidenceFile(
        key=key,
        path=path.name,
        sha256=_sha256(resolved_path),
        size_bytes=resolved_path.stat().st_size,
    )


def _digest_actor(actor: str) -> str:
    return hashlib.sha256(actor.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_text(value: str, field_name: str) -> str:
    if value.strip() == "":
        raise ReviewerIndependenceEvidenceError(f"{field_name} is required.")
    return value.strip()
