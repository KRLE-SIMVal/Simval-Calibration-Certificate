import json
from datetime import datetime, timezone

from scripts.validation.generate_production_smoke_evidence import (
    SmokeHttpResponse,
    build_production_smoke_evidence,
    main,
)


def test_production_smoke_evidence_passes_for_required_runtime_endpoints():
    evidence = build_production_smoke_evidence(
        base_url="http://127.0.0.1:8010",
        software_version="0.1.0",
        generated_at=datetime(2026, 6, 9, 8, 0, tzinfo=timezone.utc),
        http_get=_passing_http_get,
    )

    payload = evidence.to_payload()

    assert evidence.passed
    assert payload["status"] == "passed"
    assert payload["base_url"] == "http://127.0.0.1:8010"
    assert payload["scope"] == {"enabled_disciplines": ["temperature"]}
    assert [endpoint["path"] for endpoint in payload["endpoints"]] == [
        "/health",
        "/readiness",
        "/app",
        "/app/workflow",
    ]
    assert all(endpoint["ok"] for endpoint in payload["endpoints"])


def test_production_smoke_evidence_fails_for_unready_runtime():
    def http_get(url: str) -> SmokeHttpResponse:
        if url.endswith("/readiness"):
            return SmokeHttpResponse(
                status_code=503,
                body=b'{"status":"not_ready","components":[]}',
                content_type="application/json",
            )
        return _passing_http_get(url)

    evidence = build_production_smoke_evidence(
        base_url="http://127.0.0.1:8010/",
        software_version="0.1.0",
        generated_at=datetime(2026, 6, 9, 8, 0, tzinfo=timezone.utc),
        http_get=http_get,
    )

    assert not evidence.passed
    readiness = [
        endpoint for endpoint in evidence.to_payload()["endpoints"]
        if endpoint["path"] == "/readiness"
    ][0]
    assert readiness["ok"] is False
    assert readiness["status_code"] == 503


def test_generate_production_smoke_evidence_cli_writes_payload(
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "smoke-evidence.json"
    monkeypatch.setattr(
        "scripts.validation.generate_production_smoke_evidence._http_get",
        lambda url, timeout_seconds: _passing_http_get(url),
    )

    result = main(
        [
            "--base-url",
            "http://127.0.0.1:8010",
            "--software-version",
            "0.1.0",
            "--generated-at",
            "2026-06-09T08:00:00Z",
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == 0
    assert payload["status"] == "passed"
    assert payload["generated_at"] == "2026-06-09T08:00:00+00:00"
    assert payload["scope"]["enabled_disciplines"] == ["temperature"]


def _passing_http_get(url: str) -> SmokeHttpResponse:
    if url.endswith("/health"):
        return SmokeHttpResponse(
            status_code=200,
            body=b'{"status":"ok"}',
            content_type="application/json",
        )
    if url.endswith("/readiness"):
        return SmokeHttpResponse(
            status_code=200,
            body=(
                b'{"status":"ready","components":['
                b'{"name":"database","status":"ok"},'
                b'{"name":"schema","status":"ok"},'
                b'{"name":"artifact_storage","status":"ok"}]}'
            ),
            content_type="application/json",
        )
    if url.endswith("/app"):
        return SmokeHttpResponse(
            status_code=200,
            body=b"<html><title>SIMVal</title></html>",
            content_type="text/html",
        )
    if url.endswith("/app/workflow"):
        return SmokeHttpResponse(
            status_code=200,
            body=(
                b'{"application":"SIMVal Calibration Certificate",'
                b'"status":"p6_browser_workflow","steps":[]}'
            ),
            content_type="application/json",
        )
    raise AssertionError(f"Unexpected URL: {url}")
