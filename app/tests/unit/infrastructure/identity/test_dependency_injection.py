"""Tests for infrastructure.identity dependency injection integration."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from infrastructure.services import IdentityResolverDep, get_identity_resolver
from infrastructure.identity import IdentityResolver


def test_identity_resolver_provider_caching():
    """Test that get_identity_resolver returns cached instance."""
    resolver1 = get_identity_resolver()
    resolver2 = get_identity_resolver()

    assert resolver1 is resolver2


def test_identity_resolver_dep_in_route():
    """Test IdentityResolverDep works in FastAPI route."""
    app = FastAPI()

    @app.get("/test-identity")
    def test_identity(resolver: IdentityResolverDep) -> dict:
        user = resolver.resolve_from_jwt(
            {"sub": "test123", "email": "test@example.com"}
        )
        return {"user_id": user.user_id, "email": user.email}

    client = TestClient(app)
    response = client.get("/test-identity")

    assert response.status_code == 200
    assert response.json()["user_id"] == "test123"
    assert response.json()["email"] == "test@example.com"


def test_identity_resolver_dep_override():
    """Test IdentityResolverDep can be overridden in tests."""
    app = FastAPI()

    @app.get("/test-identity")
    def test_identity(resolver: IdentityResolverDep) -> dict:
        user = resolver.resolve_from_jwt(
            {"sub": "test123", "email": "test@example.com"}
        )
        return {"user_id": user.user_id}

    # Create mock resolver
    mock_resolver = IdentityResolver()

    # Override dependency
    app.dependency_overrides[get_identity_resolver] = lambda: mock_resolver

    try:
        client = TestClient(app)
        response = client.get("/test-identity")

        assert response.status_code == 200
        assert response.json()["user_id"] == "test123"
    finally:
        app.dependency_overrides.clear()


def test_identity_resolver_multiple_routes():
    """Test IdentityResolverDep works across multiple routes."""
    app = FastAPI()

    @app.get("/jwt-resolve")
    def resolve_jwt(resolver: IdentityResolverDep) -> dict:
        user = resolver.resolve_from_jwt({"sub": "user1"})
        return {"user_id": user.user_id, "source": user.source.value}

    @app.get("/system-resolve")
    def resolve_system(resolver: IdentityResolverDep) -> dict:
        user = resolver.resolve_system_identity()
        return {"user_id": user.user_id, "source": user.source.value}

    @app.post("/webhook-resolve")
    def resolve_webhook(resolver: IdentityResolverDep) -> dict:
        user = resolver.resolve_from_webhook({"user_id": "webhook_user"})
        return {"user_id": user.user_id, "source": user.source.value}

    client = TestClient(app)

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
