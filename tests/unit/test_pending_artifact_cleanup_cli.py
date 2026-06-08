import json
import os

import pytest

from scripts.maintenance.cleanup_stale_pending_artifacts import main


def test_pending_artifact_cleanup_cli_writes_json_evidence(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    pending_file = artifact_dir / ".SIMVAL-CAL-0001.pdf.pending"
    pending_file.write_bytes(b"stale")
    os.utime(pending_file, (1_700_000_000, 1_700_000_000))
    output = tmp_path / "cleanup-report.json"

    result = main(
        [
            "--artifact-dir",
            str(artifact_dir),
            "--older-than-minutes",
            "1",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result == 0
    assert payload["removed_count"] == 1
    assert payload["removed_files"] == [pending_file.resolve().as_posix()]
    assert not pending_file.exists()


def test_pending_artifact_cleanup_cli_rejects_nonpositive_age(tmp_path):
    with pytest.raises(SystemExit, match="older-than-minutes"):
        main(
            [
                "--artifact-dir",
                str(tmp_path),
                "--older-than-minutes",
                "0",
            ]
        )
