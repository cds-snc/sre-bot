"""Fixtures for infrastructure security tests."""

import json
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_issuer_config():
    """Factory fixture for creating mock issuer configuration."""
    return {
        "test_issuer": {
            "jwks_uri": "https://test.example.com/.well-known/jwks.json",
            "audience": "test_audience",
            "algorithms": ["RS256"],
        },
        "second_issuer": {
            "jwks_uri": "https://second.example.com/.well-known/jwks.json",
            "audience": "second_audience",
            "algorithms": ["RS256"],
        },
    }


@pytest.fixture
def mock_jwks_response():
    """Factory fixture for creating mock JWKS response."""
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": "test_key_1",
                "n": "test_n_value",
                "e": "AQAB",
                "alg": "RS256",
            }
        ]
    }


@pytest.fixture
def valid_jwt_payload():
    """Factory fixture for creating valid JWT payload."""
    return {
        "iss": "test_issuer",
        "sub": "user_123",
        "email": "test@example.com",
        "aud": "test_audience",
        "exp": 9999999999,
        "iat": 1000000000,
    }


@pytest.fixture
def minimal_jwt_payload():
    """Factory fixture for minimal JWT payload."""
    return {
        "iss": "test_issuer",
        "sub": "test/user_123",
        "exp": 9999999999,
        "iat": 1000000000,
    }


@pytest.fixture
def mock_http_credentials():
    """Factory fixture for creating mock HTTP authorization credentials."""

    def _make(token="valid_token", scheme="Bearer"):
        from fastapi.security import HTTPAuthorizationCredentials

        return HTTPAuthorizationCredentials(scheme=scheme, credentials=token)

    return _make
