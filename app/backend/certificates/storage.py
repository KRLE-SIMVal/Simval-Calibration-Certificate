"""Controlled local storage for rendered certificate artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.backend.certificates.rendering import RenderedCertificateArtifact


class CertificateArtifactStorageError(ValueError):
    """Raised when rendered artifact bytes cannot be stored safely."""


@dataclass(frozen=True, slots=True)
class StoredCertificateArtifact:
    filename: str
    storage_uri: str
    checksum_sha256: str


@dataclass(frozen=True, slots=True)
class PendingCertificateArtifact:
    filename: str
    pending_path: Path
    target_path: Path
    storage_uri: str
    checksum_sha256: str

    @property
    def stored_artifact(self) -> StoredCertificateArtifact:
        return StoredCertificateArtifact(
            filename=self.filename,
            storage_uri=self.storage_uri,
            checksum_sha256=self.checksum_sha256,
        )


def store_rendered_artifact(
    *,
    base_path: Path,
    artifact: RenderedCertificateArtifact,
) -> StoredCertificateArtifact:
    """Store rendered bytes once under a controlled local artifact directory."""
    if artifact.filename != Path(artifact.filename).name:
        raise CertificateArtifactStorageError(
            "Artifact filename must not contain path components."
        )
    base_path.mkdir(parents=True, exist_ok=True)
    target_path = (base_path / artifact.filename).resolve()
    resolved_base = base_path.resolve()
    if resolved_base not in target_path.parents:
        raise CertificateArtifactStorageError(
            "Artifact path must stay within the configured base path."
        )
    try:
        with target_path.open("xb") as handle:
            handle.write(artifact.content_bytes)
    except FileExistsError as exc:
        raise CertificateArtifactStorageError(
            "Artifact file already exists and cannot be overwritten."
        ) from exc
    return StoredCertificateArtifact(
        filename=artifact.filename,
        storage_uri=f"controlled-local://{artifact.filename}",
        checksum_sha256=artifact.checksum_sha256,
    )


def stage_rendered_artifact(
    *,
    base_path: Path,
    artifact: RenderedCertificateArtifact,
) -> PendingCertificateArtifact:
    """Write artifact bytes to a pending file before DB release finalization."""
    target_path = _target_path(base_path=base_path, filename=artifact.filename)
    pending_path = target_path.with_name(f".{target_path.name}.pending")
    if target_path.exists():
        raise CertificateArtifactStorageError(
            "Artifact file already exists and cannot be overwritten."
        )
    try:
        with pending_path.open("xb") as handle:
            handle.write(artifact.content_bytes)
    except FileExistsError as exc:
        raise CertificateArtifactStorageError(
            "Pending artifact file already exists and cannot be overwritten."
        ) from exc
    return PendingCertificateArtifact(
        filename=artifact.filename,
        pending_path=pending_path,
        target_path=target_path,
        storage_uri=f"controlled-local://{artifact.filename}",
        checksum_sha256=artifact.checksum_sha256,
    )


def finalize_staged_artifact(
    pending_artifact: PendingCertificateArtifact,
) -> StoredCertificateArtifact:
    """Finalize a pending artifact without overwriting an existing final file."""
    if pending_artifact.target_path.exists():
        raise CertificateArtifactStorageError(
            "Artifact file already exists and cannot be overwritten."
        )
    try:
        with pending_artifact.target_path.open("xb") as target:
            target.write(pending_artifact.pending_path.read_bytes())
        pending_artifact.pending_path.unlink()
    except FileExistsError as exc:
        raise CertificateArtifactStorageError(
            "Artifact file already exists and cannot be overwritten."
        ) from exc
    except OSError as exc:
        raise CertificateArtifactStorageError(
            "Could not finalize pending artifact file."
        ) from exc
    return pending_artifact.stored_artifact


def discard_staged_artifact(pending_artifact: PendingCertificateArtifact) -> None:
    """Remove a pending artifact after release failure."""
    try:
        pending_artifact.pending_path.unlink(missing_ok=True)
    except OSError as exc:
        raise CertificateArtifactStorageError(
            "Could not discard pending artifact file."
        ) from exc


def _target_path(*, base_path: Path, filename: str) -> Path:
    if filename != Path(filename).name:
        raise CertificateArtifactStorageError(
            "Artifact filename must not contain path components."
        )
    base_path.mkdir(parents=True, exist_ok=True)
    target_path = (base_path / filename).resolve()
    resolved_base = base_path.resolve()
    if resolved_base not in target_path.parents:
        raise CertificateArtifactStorageError(
            "Artifact path must stay within the configured base path."
        )
    return target_path
