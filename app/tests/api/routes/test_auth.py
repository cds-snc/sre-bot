"""Tests for authentication endpoints.

All OAuth-based authentication (login, logout, callback) has been deprecated
in favor of JWT-based authentication via Backstage issuer configuration.
"""

import pytest
from fastapi.testclient import TestClient
from api.routes import auth
from utils.tests import create_test_app, rate_limiting_helper

middlewares: list = []
test_app = create_test_app(auth.router, middlewares)
client = TestClient(test_app)


# Test the user info endpoint with valid JWT token
def test_user_info_endpoint_with_valid_token():
    """Test /auth/me endpoint with valid JWT token."""
    # Mock the JWT validation to return test user data
    mock_token_data = {
        "sub": "user123",
        "email": "test@example.com",
        "name": "Test User",
        "iss": "https://example.com",
    }

    # Override the dependency at the app level
    def override_validate_jwt():
        return mock_token_data

    test_app.dependency_overrides[auth.validate_jwt_token] = override_validate_jwt

    try:
        # Make the request to /auth/me
        response = client.get("/auth/me")

        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["sub"] == "user123"
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"
        assert data["issuer"] == "https://example.com"
    finally:
        # Clean up dependency override
        test_app.dependency_overrides.clear()


# Test the user info endpoint without token (should fail with 401)
def test_user_info_endpoint_without_token():
    """Test /auth/me endpoint without Bearer token."""
    response = client.get("/auth/me")
    # Should get 401 Unauthorized because Bearer token is required
    assert response.status_code == 401


# Test the user info endpoint with missing claims
def test_user_info_endpoint_partial_claims():
    """Test /auth/me endpoint with JWT missing some optional claims."""
    # Mock JWT with minimal claims
    mock_token_data = {
        "sub": "user456",
        "iss": "https://example.com",
    }

    def override_validate_jwt():
        return mock_token_data

    test_app.dependency_overrides[auth.validate_jwt_token] = override_validate_jwt

    try:
        response = client.get("/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["sub"] == "user456"
        assert data["email"] is None
        assert data["name"] is None
        assert data["issuer"] == "https://example.com"
    finally:
        # Clean up dependency override
        test_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_user_rate_limiting():
    """Test rate limiting on the /auth/me endpoint."""
    mock_token_data = {
        "sub": "user123",
        "email": "test@example.com",
        "iss": "https://example.com",
    }

    def override_validate_jwt():
        return mock_token_data

    test_app.dependency_overrides[auth.validate_jwt_token] = override_validate_jwt

    try:
        await rate_limiting_helper(
            app=test_app,
            endpoint="/auth/me",
            request_limit=10,
            expected_status=200,
        )
    finally:
        # Clean up dependency override
        test_app.dependency_overrides.clear()
