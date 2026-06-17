"""Runtime-profile evidence for controlled pilot validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json

from app.backend.api.settings import AuthProvider, ApiSettings, RuntimeProfile
from app.backend.domain.entities import Discipline


class RuntimeProfileEvidenceError(ValueError):
    """Raised when runtime-profile evidence cannot be generated."""


@dataclass(frozen=True, slots=True)
class RuntimeProfileEvidence:
    generated_at: str
    status: str
    blockers: tuple[str, ...]
    runtime_profile: str
    auth_provider: str
    enabled_disciplines: tuple[str, ...]
    database_path_configured: bool
    artifact_storage_path_configured: bool
    entra_configured: bool
    entra_session_hours: int

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def build_runtime_profile_evidence(
    *,
    settings: ApiSettings,
    generated_at: datetime | None = None,
) -> RuntimeProfileEvidence:
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None or generated.utcoffset() is None:
        raise RuntimeProfileEvidenceError(
            "Runtime-profile evidence timestamp must be timezone-aware."
        )
    blockers = _blockers(settings)
    return RuntimeProfileEvidence(
        generated_at=generated.astimezone(timezone.utc).isoformat(),
        status="passed" if len(blockers) == 0 else "blocked",
        blockers=blockers,
        runtime_profile=settings.runtime_profile.value,
        auth_provider=settings.auth_provider.value,
        enabled_disciplines=tuple(
            sorted(discipline.value for discipline in settings.enabled_disciplines)
        ),
        database_path_configured=True,
        artifact_storage_path_configured=True,
        entra_configured=settings.entra_id is not None,
        entra_session_hours=int(settings.entra_session_duration.total_seconds() // 3600),
    )


def write_runtime_profile_evidence(
    evidence: RuntimeProfileEvidence,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(evidence.to_json() + "\n", encoding="utf-8")


def _blockers(settings: ApiSettings) -> tuple[str, ...]:
    blockers: list[str] = []
    if settings.runtime_profile is not RuntimeProfile.PRODUCTION:
        blockers.append("runtime_profile_not_production")
    if settings.auth_provider is not AuthProvider.ENTRA_ID_FREE:
        blockers.append("auth_provider_not_entra_id_free")
    if settings.enabled_disciplines != frozenset({Discipline.TEMPERATURE}):
        blockers.append("enabled_disciplines_not_temperature_only")
    if settings.entra_id is None:
        blockers.append("entra_configuration_missing")
    return tuple(blockers)
