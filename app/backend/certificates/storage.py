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
