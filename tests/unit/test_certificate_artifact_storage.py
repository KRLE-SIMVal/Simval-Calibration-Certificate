import pytest

from app.backend.certificates.records import ArtifactType
from app.backend.certificates.rendering import RenderedCertificateArtifact
from app.backend.certificates.storage import (
    CertificateArtifactStorageError,
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


def _artifact() -> RenderedCertificateArtifact:
    return RenderedCertificateArtifact(
        artifact_type=ArtifactType.PDF,
        filename="SIMVAL-CAL-0001.pdf",
        content_bytes=b"controlled-pdf-bytes",
        checksum_sha256="a450087916096dec4d60102f169d5293165ecbdc2eb86a5765c948d22d27be01",
    )
