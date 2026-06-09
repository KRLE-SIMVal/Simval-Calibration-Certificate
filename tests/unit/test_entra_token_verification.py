from datetime import datetime, timezone

import pytest

from app.backend.auth.entra import (
    EntraIdConfiguration,
    EntraTokenValidationError,
    verified_entra_token_from_claims,
)


def test_entra_configuration_builds_v2_issuer_and_jwks_url():
    configuration = EntraIdConfiguration.for_tenant(
        tenant_id="tenant-001",
        client_id="client-001",
    )

    assert configuration.audience == "client-001"
    assert configuration.issuer == "https://login.microsoftonline.com/tenant-001/v2.0"
    assert configuration.jwks_url == (
        "https://login.microsoftonline.com/tenant-001/discovery/v2.0/keys"
    )
    assert configuration.allowed_algorithms == ("RS256",)


def test_verified_entra_token_from_claims_returns_controlled_identity():
    token = verified_entra_token_from_claims(
        {
            "ver": "2.0",
            "tid": "tenant-001",
            "oid": "subject-001",
            "preferred_username": "Operator@Example.com",
            "name": "Operator User",
            "exp": 1780304400,
        },
        expected_tenant_id="tenant-001",
        timestamp=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
    )

    assert token.subject_id == "subject-001"
    assert token.tenant_id == "tenant-001"
    assert token.email == "operator@example.com"
    assert token.display_name == "Operator User"
    assert token.expires_at == datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)


def test_verified_entra_token_from_claims_rejects_wrong_tenant():
    with pytest.raises(EntraTokenValidationError):
        verified_entra_token_from_claims(
            {
                "ver": "2.0",
                "tid": "other-tenant",
                "oid": "subject-001",
                "preferred_username": "operator@example.com",
                "exp": 1780304400,
            },
            expected_tenant_id="tenant-001",
            timestamp=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        )


def test_verified_entra_token_from_claims_rejects_expired_token():
    with pytest.raises(EntraTokenValidationError):
        verified_entra_token_from_claims(
            {
                "ver": "2.0",
                "tid": "tenant-001",
                "oid": "subject-001",
                "preferred_username": "operator@example.com",
                "exp": 1780300800,
            },
            expected_tenant_id="tenant-001",
            timestamp=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        )


def test_verified_entra_token_from_claims_rejects_v1_token():
    with pytest.raises(EntraTokenValidationError):
        verified_entra_token_from_claims(
            {
                "ver": "1.0",
                "tid": "tenant-001",
                "oid": "subject-001",
                "preferred_username": "operator@example.com",
                "exp": 1780304400,
            },
            expected_tenant_id="tenant-001",
            timestamp=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
        )
