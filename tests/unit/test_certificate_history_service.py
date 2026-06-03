from datetime import datetime, timezone

from app.backend.auth.permissions import Role
from app.backend.services.certificates import (
    get_certificate_history_for_session,
    revise_released_certificate_for_session,
)
from tests.unit.test_certificate_revision_service import _released_connection


def test_get_certificate_history_for_session_lists_artifacts_and_revisions():
    connection = _released_connection()
    revise_released_certificate_for_session(
        connection=connection,
        session_id="qa-session",
        certificate_id="cert-001",
        revision_id="rev-001",
        reason="Corrected customer address after QA approval.",
        software_version="app-0.1.0",
        timestamp=datetime(2026, 6, 1, 15, 45, tzinfo=timezone.utc),
    )

    history = get_certificate_history_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        timestamp=datetime(2026, 6, 1, 15, 45, tzinfo=timezone.utc),
    )

    assert history.job_id == "job-001"
    assert len(history.entries) == 1
    entry = history.entries[0]
    assert entry.certificate.certificate_id == "cert-001"
    assert entry.certificate.primary_artifact.storage_uri == (
        "controlled-local://SIMVAL-CAL-0001.pdf"
    )
    assert entry.revisions[0].revision_id == "rev-001"
    assert entry.revisions[0].reason == "Corrected customer address after QA approval."


def test_get_certificate_history_for_session_allows_read_only_actor():
    connection = _released_connection(actor_roles=(Role.READ_ONLY,))

    history = get_certificate_history_for_session(
        connection=connection,
        session_id="qa-session",
        job_id="job-001",
        timestamp=datetime(2026, 6, 1, 15, 45, tzinfo=timezone.utc),
    )

    assert history.entries[0].certificate.certificate_number == "SIMVAL-CAL-0001"
