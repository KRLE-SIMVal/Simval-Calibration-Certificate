"""Generate production smoke-test evidence from a running SIMVal API."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import argparse
import json


@dataclass(frozen=True, slots=True)
class SmokeHttpResponse:
    status_code: int
    body: bytes
    content_type: str


@dataclass(frozen=True, slots=True)
class SmokeEndpointResult:
    path: str
    status_code: int | None
    ok: bool
    detail: str

    def to_payload(self) -> dict:
        return {
            "path": self.path,
            "status_code": self.status_code,
            "ok": self.ok,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class ProductionSmokeEvidence:
    status: str
    generated_at: datetime
    software_version: str
    base_url: str
    scope: dict
    endpoints: tuple[SmokeEndpointResult, ...]

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    def to_payload(self) -> dict:
        return {
            "status": self.status,
            "generated_at": self.generated_at.isoformat(),
            "software_version": self.software_version,
            "base_url": self.base_url,
            "scope": self.scope,
            "endpoints": [endpoint.to_payload() for endpoint in self.endpoints],
        }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--software-version", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--generated-at")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--enabled-discipline", action="append", default=[])
    args = parser.parse_args(argv)

    evidence = build_production_smoke_evidence(
        base_url=args.base_url,
        software_version=args.software_version,
        generated_at=_timestamp(args.generated_at),
        enabled_disciplines=tuple(args.enabled_discipline) or ("temperature",),
        http_get=lambda url: _http_get(url, timeout_seconds=args.timeout_seconds),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(evidence.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if evidence.passed else 2


def build_production_smoke_evidence(
    *,
    base_url: str,
    software_version: str,
    generated_at: datetime,
    http_get: Callable[[str], SmokeHttpResponse],
    enabled_disciplines: tuple[str, ...] = ("temperature",),
) -> ProductionSmokeEvidence:
    _require_text(base_url, "Base URL")
    _require_text(software_version, "Software version")
    _require_timezone_aware(generated_at, "Smoke evidence timestamp")
    normalized_base_url = base_url.rstrip("/") + "/"
    endpoint_checks = (
        ("/health", _health_check),
        ("/readiness", _readiness_check),
        ("/app", _app_check),
        ("/app/workflow", _workflow_check),
    )
    endpoints = tuple(
        _check_endpoint(
            base_url=normalized_base_url,
            path=path,
            validator=validator,
            http_get=http_get,
        )
        for path, validator in endpoint_checks
    )
    status = "passed" if all(endpoint.ok for endpoint in endpoints) else "failed"
    return ProductionSmokeEvidence(
        status=status,
        generated_at=generated_at,
        software_version=software_version,
        base_url=normalized_base_url.rstrip("/"),
        scope={"enabled_disciplines": sorted(enabled_disciplines)},
        endpoints=endpoints,
    )


def _check_endpoint(
    *,
    base_url: str,
    path: str,
    validator: Callable[[SmokeHttpResponse], tuple[bool, str]],
    http_get: Callable[[str], SmokeHttpResponse],
) -> SmokeEndpointResult:
    try:
        response = http_get(urljoin(base_url, path.removeprefix("/")))
    except (OSError, URLError, TimeoutError) as error:
        return SmokeEndpointResult(
            path=path,
            status_code=None,
            ok=False,
            detail=f"Endpoint request failed: {type(error).__name__}.",
        )
    ok, detail = validator(response)
    return SmokeEndpointResult(
        path=path,
        status_code=response.status_code,
        ok=ok,
        detail=detail,
    )


def _health_check(response: SmokeHttpResponse) -> tuple[bool, str]:
    if response.status_code != 200:
        return False, "Health endpoint did not return HTTP 200."
    payload = _json_payload(response)
    if payload.get("status") != "ok":
        return False, "Health endpoint did not report status ok."
    return True, "Health endpoint reported status ok."


def _readiness_check(response: SmokeHttpResponse) -> tuple[bool, str]:
    if response.status_code != 200:
        return False, "Readiness endpoint did not return HTTP 200."
    payload = _json_payload(response)
    if payload.get("status") != "ready":
        return False, "Readiness endpoint did not report status ready."
    components = payload.get("components")
    if not isinstance(components, list):
        return False, "Readiness endpoint did not return components."
    component_status = {
        component.get("name"): component.get("status")
        for component in components
        if isinstance(component, dict)
    }
    expected = {
        "database": "ok",
        "schema": "ok",
        "artifact_storage": "ok",
    }
    if component_status != expected:
        return False, "Readiness components are not all expected ok values."
    return True, "Readiness endpoint reported expected runtime components."


def _app_check(response: SmokeHttpResponse) -> tuple[bool, str]:
    if response.status_code != 200:
        return False, "Browser app endpoint did not return HTTP 200."
    text = response.body.decode("utf-8", errors="replace")
    if "SIMVal" not in text:
        return False, "Browser app endpoint did not include SIMVal marker."
    return True, "Browser app endpoint returned the SIMVal shell."


def _workflow_check(response: SmokeHttpResponse) -> tuple[bool, str]:
    if response.status_code != 200:
        return False, "Workflow contract endpoint did not return HTTP 200."
    payload = _json_payload(response)
    if (
        not isinstance(payload, dict)
        or payload.get("application") != "SIMVal Calibration Certificate"
        or not isinstance(payload.get("steps"), list)
    ):
        return False, "Workflow contract endpoint did not include workflow metadata."
    return True, "Workflow contract endpoint returned workflow metadata."


def _json_payload(response: SmokeHttpResponse) -> dict:
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _http_get(url: str, *, timeout_seconds: float) -> SmokeHttpResponse:
    request = Request(url, headers={"User-Agent": "simval-smoke-evidence"})
    with urlopen(request, timeout=timeout_seconds) as response:
        return SmokeHttpResponse(
            status_code=response.status,
            body=response.read(),
            content_type=response.headers.get("content-type", ""),
        )


def _timestamp(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    normalized = value.removesuffix("Z") + "+00:00" if value.endswith("Z") else value
    timestamp = datetime.fromisoformat(normalized)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise SystemExit("--generated-at must be timezone-aware.")
    return timestamp


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise ValueError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


if __name__ == "__main__":
    raise SystemExit(main())
