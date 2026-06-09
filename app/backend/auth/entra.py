"""Microsoft Entra ID token verification boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol


class EntraTokenValidationError(ValueError):
    """Raised when an Entra ID token cannot be trusted."""


class EntraTokenVerifier(Protocol):
    """Protocol for verifiers that validate Entra bearer tokens."""

    def verify(
        self,
        token: str,
        *,
        timestamp: datetime,
    ) -> "VerifiedEntraToken":
        """Return verified identity claims or raise EntraTokenValidationError."""


@dataclass(frozen=True, slots=True)
class EntraIdConfiguration:
    tenant_id: str
    client_id: str
    audience: str
    issuer: str
    jwks_url: str
    allowed_algorithms: tuple[str, ...] = ("RS256",)
    clock_skew_seconds: int = 300

    @classmethod
    def for_tenant(
        cls,
        *,
        tenant_id: str,
        client_id: str,
        audience: str | None = None,
        issuer: str | None = None,
        jwks_url: str | None = None,
    ) -> "EntraIdConfiguration":
        _require_text(tenant_id, "Entra tenant id")
        _require_text(client_id, "Entra client id")
        return cls(
            tenant_id=tenant_id,
            client_id=client_id,
            audience=audience or client_id,
            issuer=issuer or f"https://login.microsoftonline.com/{tenant_id}/v2.0",
            jwks_url=(
                jwks_url
                or f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
            ),
        )

    def __post_init__(self) -> None:
        _require_text(self.tenant_id, "Entra tenant id")
        _require_text(self.client_id, "Entra client id")
        _require_text(self.audience, "Entra audience")
        _require_text(self.issuer, "Entra issuer")
        _require_text(self.jwks_url, "Entra JWKS URL")
        if len(self.allowed_algorithms) == 0:
            raise EntraTokenValidationError(
                "At least one Entra token algorithm must be allowed."
            )
        if any(algorithm.strip() == "" for algorithm in self.allowed_algorithms):
            raise EntraTokenValidationError(
                "Entra token algorithms must not be blank."
            )
        if self.clock_skew_seconds < 0:
            raise EntraTokenValidationError("Entra clock skew must not be negative.")


@dataclass(frozen=True, slots=True)
class VerifiedEntraToken:
    subject_id: str
    tenant_id: str
    email: str
    display_name: str
    expires_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.subject_id, "Entra subject id")
        _require_text(self.tenant_id, "Entra tenant id")
        _require_text(self.email, "Entra email")
        _require_text(self.display_name, "Entra display name")
        _require_timezone_aware(self.expires_at, "Entra token expiry")


class PyJwtEntraTokenVerifier:
    """Validate Entra ID access tokens with JWKS signature verification."""

    def __init__(self, configuration: EntraIdConfiguration) -> None:
        self._configuration = configuration
        self._jwks_client = None

    def verify(
        self,
        token: str,
        *,
        timestamp: datetime,
    ) -> VerifiedEntraToken:
        _require_text(token, "Entra bearer token")
        _require_timezone_aware(timestamp, "Entra verification timestamp")
        try:
            import jwt
            from jwt import PyJWKClient, PyJWTError
        except ImportError as exc:
            raise EntraTokenValidationError(
                "PyJWT[crypto] is required for Entra ID token verification."
            ) from exc

        try:
            if self._jwks_client is None:
                self._jwks_client = PyJWKClient(self._configuration.jwks_url)
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(self._configuration.allowed_algorithms),
                audience=self._configuration.audience,
                issuer=self._configuration.issuer,
                options={"require": ["aud", "exp", "iss"]},
                leeway=self._configuration.clock_skew_seconds,
            )
        except PyJWTError as exc:
            raise EntraTokenValidationError("Entra token validation failed.") from exc
        return verified_entra_token_from_claims(
            claims,
            expected_tenant_id=self._configuration.tenant_id,
            timestamp=timestamp,
        )


def verified_entra_token_from_claims(
    claims: dict[str, Any],
    *,
    expected_tenant_id: str,
    timestamp: datetime,
) -> VerifiedEntraToken:
    """Build verified identity data after JWT signature/issuer/audience checks."""
    _require_text(expected_tenant_id, "Expected Entra tenant id")
    _require_timezone_aware(timestamp, "Entra claim validation timestamp")
    _require_claim_value(claims, "ver")
    if claims["ver"] != "2.0":
        raise EntraTokenValidationError("Only Entra ID v2.0 access tokens are accepted.")

    tenant_id = _require_claim_value(claims, "tid")
    if tenant_id.lower() != expected_tenant_id.lower():
        raise EntraTokenValidationError("Entra token tenant does not match deployment.")

    expires_at = _expires_at_from_claims(claims)
    if expires_at <= timestamp:
        raise EntraTokenValidationError("Entra token is expired.")

    email = _first_claim_value(claims, ("preferred_username", "email", "upn"))
    display_name = _optional_claim_value(claims, "name") or email
    return VerifiedEntraToken(
        subject_id=_require_claim_value(claims, "oid"),
        tenant_id=tenant_id,
        email=email.lower(),
        display_name=display_name,
        expires_at=expires_at,
    )


def _expires_at_from_claims(claims: dict[str, Any]) -> datetime:
    raw_expires_at = claims.get("exp")
    if not isinstance(raw_expires_at, int):
        raise EntraTokenValidationError("Entra token exp claim is required.")
    return datetime.fromtimestamp(raw_expires_at, timezone.utc)


def _first_claim_value(claims: dict[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = _optional_claim_value(claims, name)
        if value is not None:
            return value
    joined_names = ", ".join(names)
    raise EntraTokenValidationError(f"Entra token requires one of: {joined_names}.")


def _require_claim_value(claims: dict[str, Any], name: str) -> str:
    value = _optional_claim_value(claims, name)
    if value is None:
        raise EntraTokenValidationError(f"Entra token {name} claim is required.")
    return value


def _optional_claim_value(claims: dict[str, Any], name: str) -> str | None:
    value = claims.get(name)
    if not isinstance(value, str) or value.strip() == "":
        return None
    return value.strip()


def _require_text(value: str, field_name: str) -> None:
    if value.strip() == "":
        raise EntraTokenValidationError(f"{field_name} is required.")


def _require_timezone_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise EntraTokenValidationError(f"{field_name} must be timezone-aware.")
