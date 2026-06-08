import os
from datetime import datetime, timezone

import pytest

from app.backend.certificates.records import ArtifactType
from app.backend.certificates.rendering import RenderedCertificateArtifact
from app.backend.certificates.storage import (
    CertificateArtifactStorageError,
    cleanup_stale_pending_artifacts,
    discard_staged_artifact,
    finalize_staged_artifact,
    stage_rendered_artifact,
    store_rendered_artifact,
)


def test_store_rendered_artifact_writes_bytes_and_returns_controlled_uri(tmp_path):
    artifact = _artifact()

    stored = store_rendered_artifact(
        base_path=tmp_path,
        artifact=artifact,
    )

    artifact_path = tmp_path / "SIMVAL-CAL-0001.pdf"
    assert artifact_path.read_bytes() == b"controlled-pdf-bytes"
    assert stored.filename == "SIMVAL-CAL-0001.pdf"
    assert stored.storage_uri == "controlled-local://SIMVAL-CAL-0001.pdf"
    assert stored.checksum_sha256 == artifact.checksum_sha256


def test_store_rendered_artifact_rejects_existing_file(tmp_path):
    artifact = _artifact()
    store_rendered_artifact(base_path=tmp_path, artifact=artifact)

    with pytest.raises(CertificateArtifactStorageError):
        store_rendered_artifact(base_path=tmp_path, artifact=artifact)

    assert (tmp_path / "SIMVAL-CAL-0001.pdf").read_bytes() == b"controlled-pdf-bytes"


def test_store_rendered_artifact_rejects_path_traversal_filename(tmp_path):
    with pytest.raises(CertificateArtifactStorageError):
        store_rendered_artifact(
            base_path=tmp_path,
            artifact=RenderedCertificateArtifact(
                artifact_type=ArtifactType.PDF,
                filename="../SIMVAL-CAL-0001.pdf",
                content_bytes=b"controlled-pdf-bytes",
                checksum_sha256="a450087916096dec4d60102f169d5293165ecbdc2eb86a5765c948d22d27be01",
            ),
        )


def test_stage_and_finalize_rendered_artifact_writes_final_file_after_release(
    tmp_path,
):
    artifact = _artifact()

    pending = stage_rendered_artifact(base_path=tmp_path, artifact=artifact)

    assert pending.pending_path.exists()
    assert not (tmp_path / "SIMVAL-CAL-0001.pdf").exists()

    stored = finalize_staged_artifact(pending)

    assert not pending.pending_path.exists()
    assert (tmp_path / "SIMVAL-CAL-0001.pdf").read_bytes() == (
        b"controlled-pdf-bytes"
    )
    assert stored.storage_uri == "controlled-local://SIMVAL-CAL-0001.pdf"
    assert stored.checksum_sha256 == artifact.checksum_sha256


def test_discard_staged_artifact_removes_pending_without_final_file(tmp_path):
    pending = stage_rendered_artifact(base_path=tmp_path, artifact=_artifact())

    discard_staged_artifact(pending)

    assert not pending.pending_path.exists()
    assert not (tmp_path / "SIMVAL-CAL-0001.pdf").exists()


def test_cleanup_stale_pending_artifacts_removes_only_old_pending_files(tmp_path):
    stale_pending = tmp_path / ".SIMVAL-CAL-0001.pdf.pending"
    recent_pending = tmp_path / ".SIMVAL-CAL-0002.pdf.pending"
    final_artifact = tmp_path / "SIMVAL-CAL-0003.pdf"
    stale_pending.write_bytes(b"stale")
    recent_pending.write_bytes(b"recent")
    final_artifact.write_bytes(b"final")
    os.utime(stale_pending, (1_700_000_000, 1_700_000_000))
    os.utime(recent_pending, (1_800_000_000, 1_800_000_000))
    cutoff = datetime.fromtimestamp(1_750_000_000, tz=timezone.utc)

    result = cleanup_stale_pending_artifacts(
        base_path=tmp_path,
        cutoff=cutoff,
    )

    assert result.removed_count == 1
    assert result.removed_files == (stale_pending.resolve(),)
    assert not stale_pending.exists()
    assert recent_pending.exists()
    assert final_artifact.exists()


def test_cleanup_stale_pending_artifacts_rejects_naive_cutoff(tmp_path):
    with pytest.raises(CertificateArtifactStorageError, match="timezone-aware"):
        cleanup_stale_pending_artifacts(
            base_path=tmp_path,
            cutoff=datetime(2026, 6, 1, 12, 0),
        )


def _artifact() -> RenderedCertificateArtifact:
    return RenderedCertificateArtifact(
        artifact_type=ArtifactType.PDF,
        filename="SIMVAL-CAL-0001.pdf",
        content_bytes=b"controlled-pdf-bytes",
        checksum_sha256="a450087916096dec4d60102f169d5293165ecbdc2eb86a5765c948d22d27be01",
    )
