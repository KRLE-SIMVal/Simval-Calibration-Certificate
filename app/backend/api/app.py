"""FastAPI application factory for controlled backend services."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
import sqlite3

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict

from app.backend.services.authentication import (
    AuthenticationFailureError,
    AuthenticationServiceError,
    AuthorizationServiceError,
    resolve_actor_for_session,
)
from app.backend.services.certificates import (
    CertificatePreviewGeneration,
    CertificatePreviewServiceError,
    build_certificate_preview_for_session,
)


class ApiError(BaseModel):
    detail: str


class ActorResponse(BaseModel):
    user_id: str
    display_name: str
    roles: tuple[str, ...]


class CertificatePreviewRequest(BaseModel):
    job_id: str
    template_version: str
    software_version: str


class CertificatePreviewRowResponse(BaseModel):
    point_id: str
    dut_id: str
    measurement_window_id: str
    reference: float
    indication: float
    error_of_indication: float
    display_error_of_indication: str
    reported_expanded_uncertainty: str
    unit: str


class CertificatePreviewResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"regulated_response": True})

    job_id: str
    generated_by: str
    generated_at: str
    software_version: str
    calculation_engine_version: str
    constant_set_version: str
    budget_version: str
    template_version: str
    summary_ids: tuple[str, ...]
    rows: tuple[CertificatePreviewRowResponse, ...]
    audit_event_id: int


def create_app(
    *,
    connection: sqlite3.Connection,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    """Create the backend API with an injected SQLite connection."""
    app = FastAPI(title="SIMVal Calibration Certificate API")
    clock_fn = clock or _utc_now

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        "/me",
        response_model=ActorResponse,
        responses={401: {"model": ApiError}},
    )
    def me(x_session_id: str = Header(alias="X-Session-Id")) -> ActorResponse:
        try:
            actor = resolve_actor_for_session(
                connection=connection,
                session_id=x_session_id,
                timestamp=clock_fn(),
            )
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        return ActorResponse(
            user_id=actor.user_id,
            display_name=actor.display_name,
            roles=tuple(role.value for role in actor.roles),
        )

    @app.post(
        "/certificate-previews",
        response_model=CertificatePreviewResponse,
        responses={
            401: {"model": ApiError},
            403: {"model": ApiError},
            409: {"model": ApiError},
        },
    )
    def certificate_preview(
        request: CertificatePreviewRequest,
        x_session_id: str = Header(alias="X-Session-Id"),
    ) -> CertificatePreviewResponse:
        try:
            result = build_certificate_preview_for_session(
                connection=connection,
                session_id=x_session_id,
                job_id=request.job_id,
                template_version=request.template_version,
                software_version=request.software_version,
                timestamp=clock_fn(),
            )
        except AuthenticationFailureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except AuthorizationServiceError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AuthenticationServiceError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except CertificatePreviewServiceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _preview_response(result)

    return app


def _preview_response(
    result: CertificatePreviewGeneration,
) -> CertificatePreviewResponse:
    preview = result.preview
    return CertificatePreviewResponse(
        job_id=preview.job_id,
        generated_by=preview.generated_by,
        generated_at=preview.generated_at.isoformat(),
        software_version=preview.software_version,
        calculation_engine_version=preview.calculation_engine_version,
        constant_set_version=preview.constant_set_version,
        budget_version=preview.budget_version,
        template_version=preview.template_version,
        summary_ids=preview.summary_ids,
        rows=tuple(
            CertificatePreviewRowResponse(
                point_id=row.point_id,
                dut_id=row.dut_id,
                measurement_window_id=row.measurement_window_id,
                reference=row.reference,
                indication=row.indication,
                error_of_indication=row.error_of_indication,
                display_error_of_indication=_decimal_to_text(
                    row.display_error_of_indication
                ),
                reported_expanded_uncertainty=_decimal_to_text(
                    row.reported_expanded_uncertainty
                ),
                unit=row.unit,
            )
            for row in preview.rows
        ),
        audit_event_id=result.audit_event_id,
    )


def _decimal_to_text(value: Decimal) -> str:
    return format(value, "f")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
