"""Tests for infrastructure.identity dependency injection integration."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from infrastructure.services import IdentityServiceDep, get_identity_service
from infrastructure.identity import IdentityService


def test_identity_service_provider_caching():
    """Test that get_identity_service returns cached instance."""
    service1 = get_identity_service()
    service2 = get_identity_service()

    assert service1 is service2


def test_identity_service_dep_in_route():
    """Test IdentityServiceDep works in FastAPI route."""
    app = FastAPI()

    @app.get("/test-identity")
    def test_identity(identity: IdentityServiceDep) -> dict:
        user = identity.resolve_from_jwt(
            {"sub": "test123", "email": "test@example.com"}
        )
        return {"user_id": user.user_id, "email": user.email}

    with TestClient(app) as client:
        response = client.get("/test-identity")

        assert response.status_code == 200
        assert response.json()["user_id"] == "test123"
        assert response.json()["email"] == "test@example.com"


def test_identity_service_dep_override():
    """Test IdentityServiceDep can be overridden in tests."""
    app = FastAPI()

    @app.get("/test-identity")
    def test_identity(identity: IdentityServiceDep) -> dict:
        user = identity.resolve_from_jwt(
            {"sub": "test123", "email": "test@example.com"}
        )
        return {"user_id": user.user_id}

    # Create mock service
    from unittest.mock import Mock

    mock_settings = Mock()
    mock_service = IdentityService(settings=mock_settings)

    # Override dependency
    app.dependency_overrides[get_identity_service] = lambda: mock_service

    try:
        with TestClient(app) as client:
            response = client.get("/test-identity")

            assert response.status_code == 200
            assert response.json()["user_id"] == "test123"
    finally:
        app.dependency_overrides.clear()


def test_identity_service_multiple_routes():
    """Test IdentityServiceDep works across multiple routes."""
    app = FastAPI()

    @app.get("/jwt-resolve")
    def resolve_jwt(identity: IdentityServiceDep) -> dict:
        user = identity.resolve_from_jwt({"sub": "user1"})
        return {"user_id": user.user_id, "source": user.source.value}

    @app.get("/system-resolve")
    def resolve_system(identity: IdentityServiceDep) -> dict:
        user = identity.resolve_system_identity()
        return {"user_id": user.user_id, "source": user.source.value}

    @app.post("/webhook-resolve")
    def resolve_webhook(identity: IdentityServiceDep) -> dict:
        user = identity.resolve_from_webhook({"user_id": "webhook_user"})
        return {"user_id": user.user_id, "source": user.source.value}

    with TestClient(app) as client:
        # Test JWT resolution
        jwt_response = client.get("/jwt-resolve")
        assert jwt_response.status_code == 200
        assert jwt_response.json()["source"] == "api_jwt"

        # Test system resolution
        system_response = client.get("/system-resolve")
        assert system_response.status_code == 200
        assert system_response.json()["user_id"] == "system"

        # Test webhook resolution
        webhook_response = client.post("/webhook-resolve")
        assert webhook_response.status_code == 200
        assert webhook_response.json()["user_id"] == "webhook_user"
