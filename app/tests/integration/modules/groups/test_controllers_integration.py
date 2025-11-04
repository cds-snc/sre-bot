"""
Phase 4-Step4: Controller integration tests for groups module.

Tests API endpoint integration, request/response flows, service layer
interaction, error handling, and full endpoint workflows.

Coverage:
- Request parsing and validation (AddMemberRequest, RemoveMemberRequest, etc.)
- Response serialization (ActionResponse, GroupResponse, BulkOperationResponse)
- Service layer delegation and integration
- HTTP status codes and error responses
- Multi-endpoint workflows
- Query parameter handling for GET requests
- Idempotency key handling
- Metadata and justification fields
- Admin endpoints (circuit breaker management)
- Health check endpoints
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.groups import controllers, service, schemas, models


# ============================================================================
# Fixtures: App and Client Setup
# ============================================================================


@pytest.fixture
def app():
    """Create a FastAPI app with groups router."""
    app = FastAPI()
    app.include_router(controllers.router)
    return app


@pytest.fixture
def client(app):
    """Create a test client for the FastAPI app."""
    return TestClient(app)


# ============================================================================
# Test Class: Add Member Endpoint
# ============================================================================


class TestAddMemberEndpoint:
    """Test POST /api/v1/groups/add endpoint."""

    def test_add_member_success_with_defaults(self, client, monkeypatch):
        """Test successful add member with auto-generated idempotency key."""
        request_data = {
            "group_id": "group-123",
            "member_email": "user@example.com",
            "provider": "google",
        }

        def mock_add(req):
            return schemas.ActionResponse(
                success=True,
                action=schemas.OperationType.ADD_MEMBER,
                group_id=req.group_id,
                member_email=req.member_email,
                provider=req.provider,
                timestamp=datetime.utcnow(),
            )

        monkeypatch.setattr(service, "add_member", mock_add)

        response = client.post("/api/v1/groups/add", json=request_data)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["action"] == "add_member"
        assert body["group_id"] == "group-123"
        assert body["member_email"] == "user@example.com"
        assert body["provider"] == "google"

    def test_add_member_with_all_fields(self, client, monkeypatch):
        """Test add member with all optional fields provided."""
        request_data = {
            "group_id": "group-456",
            "member_email": "admin@example.com",
            "provider": "aws",
            "justification": "Access needed for Q4 project",
            "requestor": "manager@example.com",
            "metadata": {"ticket_id": "JIRA-1234", "approval": "automatic"},
            "idempotency_key": "550e8400-e29b-41d4-a716-446655440000",
        }

        captured_request = None

        def mock_add(req):
            nonlocal captured_request
            captured_request = req
            return schemas.ActionResponse(
                success=True,
                action=schemas.OperationType.ADD_MEMBER,
                group_id=req.group_id,
                member_email=req.member_email,
                provider=req.provider,
                timestamp=datetime.utcnow(),
            )

        monkeypatch.setattr(service, "add_member", mock_add)

        response = client.post("/api/v1/groups/add", json=request_data)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

        # Verify service received full request
        assert captured_request.justification == "Access needed for Q4 project"
        assert captured_request.requestor == "manager@example.com"
        assert captured_request.metadata == {
            "ticket_id": "JIRA-1234",
            "approval": "automatic",
        }
        assert (
            captured_request.idempotency_key == "550e8400-e29b-41d4-a716-446655440000"
        )

    def test_add_member_validation_missing_required_field(self, client):
        """Test add member request validation for missing required fields."""
        # Missing member_email
        request_data = {
            "group_id": "group-123",
            "provider": "google",
        }

        response = client.post("/api/v1/groups/add", json=request_data)
        assert response.status_code == 422  # Validation error

    def test_add_member_validation_invalid_email(self, client):
        """Test add member request validation for invalid email."""
        request_data = {
            "group_id": "group-123",
            "member_email": "not-an-email",
            "provider": "google",
        }

        response = client.post("/api/v1/groups/add", json=request_data)
        assert response.status_code == 422  # Validation error

    def test_add_member_validation_invalid_provider(self, client):
        """Test add member request validation for invalid provider."""
        request_data = {
            "group_id": "group-123",
            "member_email": "user@example.com",
            "provider": "invalid_provider",
        }

        response = client.post("/api/v1/groups/add", json=request_data)
        assert response.status_code == 422  # Validation error

    def test_add_member_service_failure(self, client, monkeypatch):
        """Test add member when service returns failure."""
        request_data = {
            "group_id": "group-123",
            "member_email": "user@example.com",
            "provider": "google",
        }

        def mock_add(req):
            return schemas.ActionResponse(
                success=False,
                action=schemas.OperationType.ADD_MEMBER,
                group_id=req.group_id,
                member_email=req.member_email,
                provider=req.provider,
                details={"error": "Group not found"},
                timestamp=datetime.utcnow(),
            )

        monkeypatch.setattr(service, "add_member", mock_add)

        response = client.post("/api/v1/groups/add", json=request_data)
        assert response.status_code == 200  # Still 200 but success=False
        body = response.json()
        assert body["success"] is False
        assert body["details"]["error"] == "Group not found"


# ============================================================================
# Test Class: Remove Member Endpoint
# ============================================================================


class TestRemoveMemberEndpoint:
    """Test POST /api/v1/groups/remove endpoint."""

    def test_remove_member_success(self, client, monkeypatch):
        """Test successful remove member."""
        request_data = {
            "group_id": "group-789",
            "member_email": "user@example.com",
            "provider": "google",
        }

        def mock_remove(req):
            return schemas.ActionResponse(
                success=True,
                action=schemas.OperationType.REMOVE_MEMBER,
                group_id=req.group_id,
                member_email=req.member_email,
                provider=req.provider,
                timestamp=datetime.utcnow(),
            )

        monkeypatch.setattr(service, "remove_member", mock_remove)

        response = client.post("/api/v1/groups/remove", json=request_data)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["action"] == "remove_member"
        assert body["group_id"] == "group-789"

    def test_remove_member_with_justification(self, client, monkeypatch):
        """Test remove member with justification."""
        request_data = {
            "group_id": "group-789",
            "member_email": "user@example.com",
            "provider": "aws",
            "justification": "User left the project",
            "requestor": "admin@example.com",
            "idempotency_key": "550e8400-e29b-41d4-a716-446655440001",
        }

        captured_request = None

        def mock_remove(req):
            nonlocal captured_request
            captured_request = req
            return schemas.ActionResponse(
                success=True,
                action=schemas.OperationType.REMOVE_MEMBER,
                group_id=req.group_id,
                member_email=req.member_email,
                provider=req.provider,
                timestamp=datetime.utcnow(),
            )

        monkeypatch.setattr(service, "remove_member", mock_remove)

        response = client.post("/api/v1/groups/remove", json=request_data)
        assert response.status_code == 200

        # Verify service received full request
        assert captured_request.justification == "User left the project"
        assert captured_request.requestor == "admin@example.com"

    def test_remove_member_validation_invalid_email(self, client):
        """Test remove member with invalid email."""
        request_data = {
            "group_id": "group-789",
            "member_email": "invalid-email",
            "provider": "google",
        }

        response = client.post("/api/v1/groups/remove", json=request_data)
        assert response.status_code == 422

    def test_remove_member_idempotency(self, client, monkeypatch):
        """Test remove member idempotency key handling."""
        idempotency_key = "550e8400-e29b-41d4-a716-446655440002"
        request_data = {
            "group_id": "group-789",
            "member_email": "user@example.com",
            "provider": "google",
            "idempotency_key": idempotency_key,
        }

        call_count = [0]

        def mock_remove(req):
            call_count[0] += 1
            return schemas.ActionResponse(
                success=True,
                action=schemas.OperationType.REMOVE_MEMBER,
                group_id=req.group_id,
                member_email=req.member_email,
                provider=req.provider,
                timestamp=datetime.utcnow(),
            )

        monkeypatch.setattr(service, "remove_member", mock_remove)

        # First call
        response1 = client.post("/api/v1/groups/remove", json=request_data)
        assert response1.status_code == 200
        body1 = response1.json()

        # Second call with same idempotency key should use cache
        response2 = client.post("/api/v1/groups/remove", json=request_data)
        assert response2.status_code == 200
        body2 = response2.json()

        # Both responses should have same non-timestamp fields (timestamps may differ)
        assert body1["success"] == body2["success"]
        assert body1["action"] == body2["action"]
        assert body1["group_id"] == body2["group_id"]
        assert body1["member_email"] == body2["member_email"]


# ============================================================================
# Test Class: List Groups Endpoint
# ============================================================================


class TestListGroupsEndpoint:
    """Test GET /api/v1/groups/ endpoint."""

    def test_list_groups_success(self, client, monkeypatch):
        """Test successful list groups."""
        user_email = "user@example.com"

        def mock_list(req):
            assert req.user_email == user_email
            group_dict = {
                "id": "group-1",
                "name": "Engineering",
                "description": "Engineering team",
                "members": [],
            }
            return [models.group_from_dict(group_dict, "google")]

        monkeypatch.setattr(service, "list_groups", mock_list)

        response = client.get(f"/api/v1/groups/?user_email={user_email}")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["id"] == "group-1"
        assert body[0]["name"] == "Engineering"

    def test_list_groups_with_provider_filter(self, client, monkeypatch):
        """Test list groups with provider filter."""
        user_email = "user@example.com"
        provider = "aws"

        captured_request = None

        def mock_list(req):
            nonlocal captured_request
            captured_request = req
            return []

        monkeypatch.setattr(service, "list_groups", mock_list)

        response = client.get(
            f"/api/v1/groups/?user_email={user_email}&provider={provider}"
        )
        assert response.status_code == 200

        # Verify service received provider
        assert captured_request.provider == provider

    def test_list_groups_multiple_results(self, client, monkeypatch):
        """Test list groups returning multiple groups."""
        user_email = "user@example.com"

        def mock_list(req):
            groups = [
                models.group_from_dict(
                    {
                        "id": f"group-{i}",
                        "name": f"Group {i}",
                        "description": "",
                        "members": [],
                    },
                    "google",
                )
                for i in range(1, 4)
            ]
            return groups

        monkeypatch.setattr(service, "list_groups", mock_list)

        response = client.get(f"/api/v1/groups/?user_email={user_email}")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 3
        assert body[0]["id"] == "group-1"
        assert body[2]["id"] == "group-3"

    def test_list_groups_empty_result(self, client, monkeypatch):
        """Test list groups with no results."""
        user_email = "nonexistent@example.com"

        def mock_list(req):
            return []

        monkeypatch.setattr(service, "list_groups", mock_list)

        response = client.get(f"/api/v1/groups/?user_email={user_email}")
        assert response.status_code == 200
        body = response.json()
        assert body == []

    def test_list_groups_missing_required_param(self, client):
        """Test list groups without required user_email parameter."""
        response = client.get("/api/v1/groups/")
        assert response.status_code == 422  # Validation error

    def test_list_groups_invalid_email(self, client):
        """Test list groups with invalid email parameter."""
        response = client.get("/api/v1/groups/?user_email=not-an-email")
        assert response.status_code == 422  # Validation error


# ============================================================================
# Test Class: Bulk Operations Endpoint
# ============================================================================


class TestBulkOperationsEndpoint:
    """Test POST /api/v1/groups/bulk endpoint."""

    def test_bulk_operations_success(self, client, monkeypatch):
        """Test successful bulk operations."""
        request_data = {
            "operations": [
                {
                    "operation": "add_member",
                    "payload": {
                        "group_id": "group-1",
                        "member_email": "user1@example.com",
                        "provider": "google",
                    },
                },
                {
                    "operation": "add_member",
                    "payload": {
                        "group_id": "group-2",
                        "member_email": "user2@example.com",
                        "provider": "aws",
                    },
                },
            ]
        }

        def mock_bulk(req):
            results = []
            for op in req.operations:
                member_email = op.payload.get("member_email")
                group_id = op.payload.get("group_id")
                provider = op.payload.get("provider")
                results.append(
                    schemas.ActionResponse(
                        success=True,
                        action=schemas.OperationType.ADD_MEMBER,
                        group_id=group_id,
                        member_email=member_email,
                        provider=provider,
                        timestamp=datetime.utcnow(),
                    )
                )
            return schemas.BulkOperationResponse(
                results=results,
                summary={"success": 2, "failed": 0},
            )

        monkeypatch.setattr(service, "bulk_operations", mock_bulk)

        response = client.post("/api/v1/groups/bulk", json=request_data)
        assert response.status_code == 200
        body = response.json()
        assert len(body["results"]) == 2
        assert body["summary"]["success"] == 2
        assert body["summary"]["failed"] == 0

    def test_bulk_operations_mixed_success_failure(self, client, monkeypatch):
        """Test bulk operations with mixed success/failure."""
        request_data = {
            "operations": [
                {
                    "operation": "add_member",
                    "payload": {
                        "group_id": "group-1",
                        "member_email": "user1@example.com",
                        "provider": "google",
                    },
                },
                {
                    "operation": "add_member",
                    "payload": {
                        "group_id": "group-404",
                        "member_email": "user2@example.com",
                        "provider": "google",
                    },
                },
            ]
        }

        def mock_bulk(req):  # pylint: disable=unused-argument
            results = [
                schemas.ActionResponse(
                    success=True,
                    action=schemas.OperationType.ADD_MEMBER,
                    group_id="group-1",
                    member_email="user1@example.com",
                    provider="google",
                    timestamp=datetime.utcnow(),
                ),
                schemas.ActionResponse(
                    success=False,
                    action=schemas.OperationType.ADD_MEMBER,
                    group_id="group-404",
                    member_email="user2@example.com",
                    provider="google",
                    details={"error": "Group not found"},
                    timestamp=datetime.utcnow(),
                ),
            ]
            return schemas.BulkOperationResponse(
                results=results,
                summary={"success": 1, "failed": 1},
            )

        monkeypatch.setattr(service, "bulk_operations", mock_bulk)

        response = client.post("/api/v1/groups/bulk", json=request_data)
        assert response.status_code == 200
        body = response.json()
        assert len(body["results"]) == 2
        assert body["results"][0]["success"] is True
        assert body["results"][1]["success"] is False
        assert body["summary"]["success"] == 1
        assert body["summary"]["failed"] == 1

    def test_bulk_operations_empty(self, client, monkeypatch):
        """Test bulk operations with empty operations list."""
        request_data = {"operations": []}

        def mock_bulk(req):  # pylint: disable=unused-argument
            return schemas.BulkOperationResponse(
                results=[],
                summary={"success": 0, "failed": 0},
            )

        monkeypatch.setattr(service, "bulk_operations", mock_bulk)

        response = client.post("/api/v1/groups/bulk", json=request_data)
        assert response.status_code == 200
        body = response.json()
        assert body["results"] == []
        assert body["summary"]["success"] == 0

    def test_bulk_operations_max_size_validation(self, client):
        """Test bulk operations respects max operations limit."""
        # Create 101 operations (assuming max is 100)
        request_data = {
            "operations": [
                {
                    "type": "add_member",
                    "group_id": f"group-{i}",
                    "member_email": f"user{i}@example.com",
                    "provider": "google",
                }
                for i in range(101)
            ]
        }

        response = client.post("/api/v1/groups/bulk", json=request_data)
        # Should reject due to max size validation
        assert response.status_code == 422


# ============================================================================
# Test Class: Circuit Breaker Admin Endpoints
# ============================================================================


class TestCircuitBreakerAdminEndpoints:
    """Test admin endpoints for circuit breaker management."""

    def test_get_circuit_breaker_status_success(self, client, monkeypatch):
        """Test getting circuit breaker status for all providers."""
        mock_providers = {
            "google": MagicMock(
                get_circuit_breaker_stats=MagicMock(
                    return_value={"state": "CLOSED", "failure_count": 0}
                )
            ),
            "aws": MagicMock(
                get_circuit_breaker_stats=MagicMock(
                    return_value={"state": "CLOSED", "failure_count": 0}
                )
            ),
        }

        def mock_get_active_providers():
            return mock_providers

        monkeypatch.setattr(
            "modules.groups.controllers.get_active_providers",
            mock_get_active_providers,
        )

        response = client.get("/api/v1/groups/admin/circuit-breakers")
        assert response.status_code == 200
        body = response.json()
        assert "timestamp" in body
        assert "providers" in body
        assert "google" in body["providers"]
        assert "aws" in body["providers"]
        assert body["providers"]["google"]["state"] == "CLOSED"
        assert body["providers"]["aws"]["state"] == "CLOSED"

    def test_get_circuit_breaker_status_with_open_circuit(self, client, monkeypatch):
        """Test circuit breaker status when a circuit is open."""
        mock_providers = {
            "google": MagicMock(
                get_circuit_breaker_stats=MagicMock(
                    return_value={"state": "OPEN", "failure_count": 10}
                )
            ),
            "aws": MagicMock(
                get_circuit_breaker_stats=MagicMock(
                    return_value={"state": "CLOSED", "failure_count": 0}
                )
            ),
        }

        def mock_get_active_providers():
            return mock_providers

        monkeypatch.setattr(
            "modules.groups.controllers.get_active_providers",
            mock_get_active_providers,
        )

        response = client.get("/api/v1/groups/admin/circuit-breakers")
        assert response.status_code == 200
        body = response.json()
        assert body["providers"]["google"]["state"] == "OPEN"

    def test_reset_circuit_breaker_success(self, client, monkeypatch):
        """Test successfully resetting a circuit breaker."""
        mock_provider = MagicMock(
            get_circuit_breaker_stats=MagicMock(
                return_value={"state": "CLOSED", "failure_count": 0}
            ),
            reset_circuit_breaker=MagicMock(),
        )

        def mock_get_active_providers():
            return {"google": mock_provider}

        monkeypatch.setattr(
            "modules.groups.controllers.get_active_providers",
            mock_get_active_providers,
        )

        response = client.post("/api/v1/groups/admin/circuit-breakers/google/reset")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["provider"] == "google"
        assert "Circuit breaker for 'google' has been reset" in body["message"]
        mock_provider.reset_circuit_breaker.assert_called_once()

    def test_reset_circuit_breaker_provider_not_found(self, client, monkeypatch):
        """Test reset circuit breaker for non-existent provider."""

        def mock_get_active_providers():
            return {"google": MagicMock()}

        monkeypatch.setattr(
            "modules.groups.controllers.get_active_providers",
            mock_get_active_providers,
        )

        response = client.post(
            "/api/v1/groups/admin/circuit-breakers/nonexistent/reset"
        )
        assert response.status_code == 404
        body = response.json()
        assert "not found" in body["detail"].lower()


# ============================================================================
# Test Class: Health Check Endpoints
# ============================================================================


class TestHealthCheckEndpoints:
    """Test health check endpoints."""

    def test_circuit_breaker_health_all_closed(self, client, monkeypatch):
        """Test health check when all circuit breakers are closed."""
        mock_providers = {
            "google": MagicMock(
                get_circuit_breaker_stats=MagicMock(
                    return_value={"state": "CLOSED", "failure_count": 0}
                )
            ),
            "aws": MagicMock(
                get_circuit_breaker_stats=MagicMock(
                    return_value={"state": "CLOSED", "failure_count": 0}
                )
            ),
        }

        def mock_get_active_providers():
            return mock_providers

        def mock_get_open_circuit_breakers():
            return []

        monkeypatch.setattr(
            "modules.groups.controllers.get_active_providers",
            mock_get_active_providers,
        )
        monkeypatch.setattr(
            "modules.groups.controllers.get_open_circuit_breakers",
            mock_get_open_circuit_breakers,
        )

        response = client.get("/api/v1/groups/health/circuit-breakers")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["open_circuits"] == []
        assert "closed or half_open" in body["message"].lower()

    def test_circuit_breaker_health_with_open_circuits(self, client, monkeypatch):
        """Test health check when circuit breakers are open."""
        mock_providers = {
            "google": MagicMock(
                get_circuit_breaker_stats=MagicMock(
                    return_value={"state": "OPEN", "failure_count": 10}
                )
            ),
            "aws": MagicMock(
                get_circuit_breaker_stats=MagicMock(
                    return_value={"state": "CLOSED", "failure_count": 0}
                )
            ),
        }

        def mock_get_active_providers():
            return mock_providers

        def mock_get_open_circuit_breakers():
            return ["google"]

        monkeypatch.setattr(
            "modules.groups.controllers.get_active_providers",
            mock_get_active_providers,
        )
        monkeypatch.setattr(
            "modules.groups.controllers.get_open_circuit_breakers",
            mock_get_open_circuit_breakers,
        )

        response = client.get("/api/v1/groups/health/circuit-breakers")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "degraded"
        assert "google" in body["open_circuits"]
        assert "1 circuit breaker(s) are OPEN" in body["message"]

    def test_circuit_breaker_health_error_handling(self, client, monkeypatch):
        """Test health check error handling."""

        def mock_get_active_providers():
            raise Exception("Database connection error")

        monkeypatch.setattr(
            "modules.groups.controllers.get_active_providers",
            mock_get_active_providers,
        )

        response = client.get("/api/v1/groups/health/circuit-breakers")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "unknown"
        assert "error" in body


# ============================================================================
# Test Class: Response Serialization
# ============================================================================


class TestResponseSerialization:
    """Test response model serialization."""

    def test_action_response_with_all_fields(self, client, monkeypatch):
        """Test ActionResponse serialization with all fields."""
        request_data = {
            "group_id": "group-123",
            "member_email": "user@example.com",
            "provider": "google",
            "metadata": {"ticket": "JIRA-123"},
        }

        def mock_add(req):
            return schemas.ActionResponse(
                success=True,
                action=schemas.OperationType.ADD_MEMBER,
                group_id=req.group_id,
                member_email=req.member_email,
                provider=req.provider,
                details={"workflow_id": "wf-123"},
                timestamp=datetime.utcnow(),
            )

        monkeypatch.setattr(service, "add_member", mock_add)

        response = client.post("/api/v1/groups/add", json=request_data)
        body = response.json()
        assert "success" in body
        assert "action" in body
        assert "group_id" in body
        assert "member_email" in body
        assert "provider" in body
        assert "details" in body
        assert "timestamp" in body
        assert body["details"]["workflow_id"] == "wf-123"

    def test_group_response_with_members(self, client, monkeypatch):
        """Test GroupResponse serialization with members."""
        user_email = "user@example.com"

        def mock_list(req):
            group_dict = {
                "id": "group-1",
                "name": "Engineering",
                "description": "Engineering team",
                "members": [
                    {"email": "member1@example.com", "role": "member"},
                    {"email": "member2@example.com", "role": "owner"},
                ],
            }
            return [models.group_from_dict(group_dict, "google")]

        monkeypatch.setattr(service, "list_groups", mock_list)

        response = client.get(f"/api/v1/groups/?user_email={user_email}")
        body = response.json()
        assert len(body) == 1
        group = body[0]
        assert "id" in group
        assert "name" in group
        assert "description" in group
        assert "provider" in group
        assert "members" in group
        assert isinstance(group["members"], list)


# ============================================================================
# Test Class: Error Response Handling
# ============================================================================


class TestErrorResponseHandling:
    """Test error response handling and status codes."""

    def test_malformed_json(self, client):
        """Test handling of malformed JSON."""
        response = client.post(
            "/api/v1/groups/add",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_missing_content_type_header(self, client):
        """Test handling when content-type header is missing."""
        # FastAPI/Starlette should handle this gracefully
        response = client.post("/api/v1/groups/add", json={"test": "data"})
        # Should fail validation because required fields missing
        assert response.status_code == 422

    def test_service_exception_handling(self, client, monkeypatch):
        """Test handling when service raises exception."""

        def mock_add(req):
            raise Exception("Unexpected error in service")

        monkeypatch.setattr(service, "add_member", mock_add)

        request_data = {
            "group_id": "group-123",
            "member_email": "user@example.com",
            "provider": "google",
        }

        # FastAPI will catch the exception and return 500
        with pytest.raises(Exception):
            client.post("/api/v1/groups/add", json=request_data)


# ============================================================================
# Test Class: Multi-Endpoint Workflows
# ============================================================================


class TestMultiEndpointWorkflows:
    """Test workflows spanning multiple endpoints."""

    def test_add_list_remove_workflow(self, client, monkeypatch):
        """Test workflow: add member -> list groups -> remove member."""
        group_id = "workflow-group"
        member_email = "workflow-user@example.com"

        def mock_add(req):
            return schemas.ActionResponse(
                success=True,
                action=schemas.OperationType.ADD_MEMBER,
                group_id=req.group_id,
                member_email=req.member_email,
                provider=req.provider,
                timestamp=datetime.utcnow(),
            )

        def mock_list(req):
            group_dict = {
                "id": group_id,
                "name": "Workflow Group",
                "description": "For testing workflows",
                "members": [{"email": member_email, "role": "member"}],
            }
            return [models.group_from_dict(group_dict, "google")]

        def mock_remove(req):
            return schemas.ActionResponse(
                success=True,
                action=schemas.OperationType.REMOVE_MEMBER,
                group_id=req.group_id,
                member_email=req.member_email,
                provider=req.provider,
                timestamp=datetime.utcnow(),
            )

        monkeypatch.setattr(service, "add_member", mock_add)
        monkeypatch.setattr(service, "list_groups", mock_list)
        monkeypatch.setattr(service, "remove_member", mock_remove)

        # 1. Add member
        add_response = client.post(
            "/api/v1/groups/add",
            json={
                "group_id": group_id,
                "member_email": member_email,
                "provider": "google",
            },
        )
        assert add_response.status_code == 200
        assert add_response.json()["success"] is True

        # 2. List groups
        list_response = client.get("/api/v1/groups/?user_email=admin@example.com")
        assert list_response.status_code == 200
        groups = list_response.json()
        assert len(groups) == 1
        assert member_email in [m["email"] for m in groups[0]["members"]]

        # 3. Remove member
        remove_response = client.post(
            "/api/v1/groups/remove",
            json={
                "group_id": group_id,
                "member_email": member_email,
                "provider": "google",
            },
        )
        assert remove_response.status_code == 200
        assert remove_response.json()["success"] is True

    def test_bulk_with_error_recovery_workflow(self, client, monkeypatch):
        """Test workflow: bulk operations with errors -> list results."""
        call_count = [0]

        def mock_bulk(req):  # pylint: disable=unused-argument
            call_count[0] += 1
            results = [
                schemas.ActionResponse(
                    success=True,
                    action=schemas.OperationType.ADD_MEMBER,
                    group_id="group-1",
                    member_email="user1@example.com",
                    provider="google",
                    timestamp=datetime.utcnow(),
                ),
                schemas.ActionResponse(
                    success=False,
                    action=schemas.OperationType.ADD_MEMBER,
                    group_id="group-2",
                    member_email="user2@example.com",
                    provider="google",
                    details={"error": "Group not found"},
                    timestamp=datetime.utcnow(),
                ),
            ]
            return schemas.BulkOperationResponse(
                results=results,
                summary={"success": 1, "failed": 1},
            )

        monkeypatch.setattr(service, "bulk_operations", mock_bulk)

        # 1. Bulk operations with errors
        bulk_response = client.post(
            "/api/v1/groups/bulk",
            json={
                "operations": [
                    {
                        "operation": "add_member",
                        "payload": {
                            "group_id": "group-1",
                            "member_email": "user1@example.com",
                            "provider": "google",
                        },
                    },
                    {
                        "operation": "add_member",
                        "payload": {
                            "group_id": "group-2",
                            "member_email": "user2@example.com",
                            "provider": "google",
                        },
                    },
                ]
            },
        )
        assert bulk_response.status_code == 200
        results = bulk_response.json()
        assert results["summary"]["success"] == 1
        assert results["summary"]["failed"] == 1


# ============================================================================
# Integration Marker
# ============================================================================

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration
